"""Resume migration engine -- bulk-processes a ZIP of PDF/DOCX resumes.

Extracts the ZIP, processes files in batches of 50, creates CandidateProfile
and RecruiterPipelineCandidate records.  Designed to run as an RQ background job.

Dedup strategy (skip-for-migration): if a resume's parsed email already exists
in the recruiter's pipeline, the file is skipped entirely -- no parsing, no
new records.  This makes re-runs and overlapping imports fast.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.migration import MigrationEntityMap, MigrationJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.resume_document import ResumeDocument
from app.models.user import User
from app.services.profile_parser import extract_text, parse_profile_from_text

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per resume


# ---------------------------------------------------------------------------
# RQ entry point
# ---------------------------------------------------------------------------


def run_resume_migration(migration_job_id: int) -> dict:
    """RQ job entry point.  Creates its own DB session (worker runs
    in a separate process)."""
    session = get_session_factory()()
    try:
        return _process_resume_migration(migration_job_id, session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def _process_resume_migration(job_id: int, db: Session) -> dict:
    job = db.execute(
        select(MigrationJob).where(MigrationJob.id == job_id)
    ).scalar_one_or_none()
    if not job:
        raise ValueError(f"Migration job {job_id} not found")

    config = job.config_json or {}
    recruiter_profile_id = config.get("recruiter_profile_id")
    if not recruiter_profile_id:
        raise ValueError("recruiter_profile_id missing from job config")

    job.status = "importing"
    job.started_at = datetime.now(UTC)
    db.commit()

    stats: dict[str, int] = {
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "total_files": 0,
        "processed_files": 0,
    }
    errors: list[dict] = []
    extract_dir: str | None = None

    try:
        src = job.source_file_path
        if not src or not Path(src).exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        # 1. Extract ZIP
        extract_dir = tempfile.mkdtemp(prefix="winnow_resume_migration_")
        with zipfile.ZipFile(src) as zf:
            zf.extractall(extract_dir)

        # 2. Collect resume files
        resume_paths = _collect_resume_files(extract_dir)
        stats["total_files"] = len(resume_paths)
        _update_job_stats(db, job, stats, errors)

        # 3. Permanent storage directory
        upload_dir = Path("data/uploads/recruiter_resumes")
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 4. Pre-load existing pipeline emails for fast dedup
        existing_emails = _load_pipeline_emails(db, recruiter_profile_id)

        # 5. Process in batches
        for batch_start in range(0, len(resume_paths), BATCH_SIZE):
            batch = resume_paths[batch_start : batch_start + BATCH_SIZE]

            for fpath in batch:
                try:
                    result = _process_single_resume(
                        job_id=job_id,
                        recruiter_profile_id=recruiter_profile_id,
                        file_path=fpath,
                        extract_dir=extract_dir,
                        upload_dir=upload_dir,
                        existing_emails=existing_emails,
                        db=db,
                    )
                    stats[result] += 1
                except Exception as exc:
                    stats["errors"] += 1
                    rel = _safe_rel_path(fpath, extract_dir)
                    errors.append({"file": rel, "error": str(exc)[:300]})
                    logger.warning("Resume migration error (%s): %s", rel, exc)
                finally:
                    stats["processed_files"] += 1

            db.commit()
            _update_job_stats(db, job, stats, errors)

        job.status = "completed"
        job.completed_at = datetime.now(UTC)

    except Exception as exc:
        job.status = "failed"
        errors.append({"error": str(exc)[:500], "fatal": True})
        logger.exception("Resume migration job %d failed", job_id)

    _update_job_stats(db, job, stats, errors)

    # Clean up temp files
    if extract_dir and os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)

    # Send completion email
    _send_completion_email(db, job, stats)

    return {"job_id": job_id, "status": job.status, "stats": stats}


# ---------------------------------------------------------------------------
# Single-file processing
# ---------------------------------------------------------------------------


def _process_single_resume(
    *,
    job_id: int,
    recruiter_profile_id: int,
    file_path: Path,
    extract_dir: str,
    upload_dir: Path,
    existing_emails: set[str],
    db: Session,
) -> str:
    """Process one resume.  Returns 'imported' or 'skipped'."""
    filename = file_path.name

    # Quick email pre-check: peek at raw text for an email before full parse.
    # This avoids expensive parsing for duplicates.
    text = extract_text(file_path)
    if not text or len(text.strip()) < 20:
        return "skipped"

    # Fast email extraction (regex only, no full parse yet)
    from app.services.profile_parser import _extract_email  # noqa: E402

    quick_email = _extract_email(text)
    if quick_email and quick_email.strip().lower() in existing_emails:
        return "skipped"

    # Full parse
    profile_json = parse_profile_from_text(text)
    basics = profile_json.get("basics", {})
    parsed_email = basics.get("email")
    parsed_name = basics.get("name")

    # Double-check after full parse (email may differ from quick extract)
    if parsed_email and parsed_email.strip().lower() in existing_emails:
        return "skipped"

    # Save file permanently
    contents = file_path.read_bytes()
    file_hash = hashlib.sha256(contents).hexdigest()
    dest_name = f"{file_hash[:16]}_{filename}"
    dest_path = upload_dir / dest_name
    dest_path.write_bytes(contents)

    # Create ResumeDocument
    resume_doc = ResumeDocument(
        user_id=None,
        filename=filename,
        path=str(dest_path),
        sha256=file_hash,
    )
    db.add(resume_doc)
    db.flush()

    # Create CandidateProfile
    profile_json["source"] = "resume_migration"
    new_cp = CandidateProfile(
        user_id=None,
        resume_document_id=resume_doc.id,
        version=1,
        profile_json=profile_json,
        profile_visibility="private",
        open_to_opportunities=False,
    )
    db.add(new_cp)
    db.flush()

    # Resolve: platform user or new pipeline entry
    pipeline_entry = None

    if parsed_email:
        parsed_email_lower = parsed_email.strip().lower()

        platform_user = db.execute(
            select(User).where(func.lower(User.email) == parsed_email_lower)
        ).scalar_one_or_none()

        if platform_user:
            existing_cp = db.execute(
                select(CandidateProfile)
                .where(CandidateProfile.user_id == platform_user.id)
                .order_by(CandidateProfile.id.desc())
            ).scalar_one_or_none()
            linked_cp_id = existing_cp.id if existing_cp else new_cp.id

            pipeline_entry = RecruiterPipelineCandidate(
                recruiter_profile_id=recruiter_profile_id,
                candidate_profile_id=linked_cp_id,
                external_name=parsed_name,
                external_email=parsed_email,
                source="resume_migration",
                stage="sourced",
            )
        else:
            pipeline_entry = RecruiterPipelineCandidate(
                recruiter_profile_id=recruiter_profile_id,
                candidate_profile_id=new_cp.id,
                external_name=parsed_name,
                external_email=parsed_email,
                source="resume_migration",
                stage="sourced",
            )

        # Add to in-memory set so later files in this batch dedup correctly
        existing_emails.add(parsed_email_lower)
    else:
        pipeline_entry = RecruiterPipelineCandidate(
            recruiter_profile_id=recruiter_profile_id,
            candidate_profile_id=new_cp.id,
            external_name=parsed_name or filename,
            source="resume_migration",
            stage="sourced",
        )

    db.add(pipeline_entry)
    db.flush()

    # Record for rollback support
    _record_entity(job_id, parsed_email or file_hash[:16], pipeline_entry.id, db)

    return "imported"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_resume_files(directory: str) -> list[Path]:
    """Walk directory tree and collect PDF/DOCX files, sorted by name."""
    resume_files: list[Path] = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if fname.startswith(".") or "__MACOSX" in root:
                continue
            if Path(fname).suffix.lower() in RESUME_EXTENSIONS:
                full = Path(root) / fname
                if full.stat().st_size <= MAX_FILE_SIZE:
                    resume_files.append(full)
    resume_files.sort(key=lambda p: p.name.lower())
    return resume_files


def _load_pipeline_emails(db: Session, recruiter_profile_id: int) -> set[str]:
    """Load all existing pipeline candidate emails for fast dedup lookup."""
    rows = db.execute(
        select(RecruiterPipelineCandidate.external_email).where(
            RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
            RecruiterPipelineCandidate.external_email.isnot(None),
        )
    ).all()
    return {r[0].strip().lower() for r in rows if r[0]}


def _record_entity(job_id: int, source_id: str, winnow_id: int, db: Session) -> None:
    db.add(
        MigrationEntityMap(
            migration_job_id=job_id,
            source_entity_type="resume",
            source_entity_id=source_id,
            winnow_entity_type="recruiter_pipeline_candidate",
            winnow_entity_id=winnow_id,
            status="imported",
        )
    )


def _update_job_stats(
    db: Session, job: MigrationJob, stats: dict, errors: list[dict]
) -> None:
    job.stats_json = dict(stats)
    job.error_log = errors if errors else None
    job.updated_at = datetime.now(UTC)
    db.commit()


def _safe_rel_path(fpath: Path, base: str) -> str:
    try:
        return str(fpath.relative_to(base))
    except ValueError:
        return fpath.name


def _send_completion_email(db: Session, job: MigrationJob, stats: dict) -> None:
    """Send email notification to the recruiter when migration finishes."""
    if job.status not in ("completed", "failed"):
        return
    try:
        user = db.get(User, job.user_id)
        if not user or not user.email:
            return
        from app.services.email import send_migration_complete_email

        send_migration_complete_email(
            to_email=user.email,
            imported=stats.get("imported", 0),
            skipped=stats.get("skipped", 0),
            errors=stats.get("errors", 0),
            total=stats.get("total_files", 0),
            job_id=job.id,
        )
    except Exception:
        logger.warning("Failed to send migration completion email", exc_info=True)
