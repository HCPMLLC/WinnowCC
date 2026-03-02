"""Async-first batch upload service.

Implements the Accept-Stage-Queue-Process pattern:
1. HTTP handler validates, stages files to storage, creates tracking rows,
   enqueues per-file worker jobs, returns batch_id immediately.
2. Worker processes each file independently (text extraction, LLM parsing,
   DB writes) and updates tracking rows.
3. Finalize function marks the batch complete when all files are done.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.db.session import get_session_factory
from app.models.upload_batch import UploadBatch, UploadBatchFile

logger = logging.getLogger(__name__)

MAX_ACTIVE_BATCHES = 3
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_RETRIES = 2
MAX_ZIP_FILES = 10_000
CHUNK_COMMIT_SIZE = 500  # rows committed per chunk during ZIP streaming
PROCESSING_RATE = 960  # estimated files/hour for ETA calculations
RESUME_EXTENSIONS = {".pdf", ".docx"}


# ---------------------------------------------------------------------------
# 1. create_upload_batch — called from HTTP endpoints
# ---------------------------------------------------------------------------


def create_upload_batch(
    *,
    user_id: int,
    owner_profile_id: int | None,
    batch_type: str,
    files: list[tuple[str, bytes]],  # (filename, raw_bytes)
    session,
) -> dict:
    """Stage files, create tracking rows, enqueue worker jobs.

    Returns dict with batch_id and status_url.
    Raises ValueError on validation errors.
    """
    from app.services.queue import get_queue
    from app.services.storage import upload_bytes

    # Check concurrent batch limit
    active_count = (
        session.execute(
            select(func.count(UploadBatch.id)).where(
                UploadBatch.user_id == user_id,
                UploadBatch.status.in_(["pending", "processing"]),
            )
        ).scalar()
        or 0
    )
    if active_count >= MAX_ACTIVE_BATCHES:
        raise ValueError(
            f"You already have {active_count} active upload(s). "
            "Please wait for them to complete before uploading more."
        )

    batch_id = str(uuid4())
    batch = UploadBatch(
        batch_id=batch_id,
        user_id=user_id,
        batch_type=batch_type,
        owner_profile_id=owner_profile_id,
        status="pending",
        total_files=len(files),
    )
    session.add(batch)
    session.flush()

    bulk_queue = get_queue("bulk")
    batch_files = []
    seen_hashes: set[str] = set()
    duplicates_skipped = 0

    for idx, (filename, contents) in enumerate(files):
        file_hash = hashlib.sha256(contents).hexdigest()

        # Within-batch dedup: skip files with identical content
        if file_hash in seen_hashes:
            duplicates_skipped += 1
            continue
        seen_hashes.add(file_hash)

        # Stage raw bytes to storage under staging prefix
        staged_name = f"{idx}_{file_hash[:12]}_{filename}"
        staged_path = upload_bytes(contents, f"staging/{batch_id}/", staged_name)

        bf = UploadBatchFile(
            batch_id=batch_id,
            file_index=idx,
            original_filename=filename,
            staged_path=staged_path,
            file_size_bytes=len(contents),
            sha256=file_hash,
            status="pending",
        )
        session.add(bf)
        session.flush()
        batch_files.append(bf)

    # Update total_files to actual deduplicated count
    batch.total_files = len(batch_files)

    if duplicates_skipped:
        logger.info(
            "Batch %s: skipped %d duplicate files",
            batch_id,
            duplicates_skipped,
        )

    session.commit()

    # Enqueue per-file worker jobs (after commit so rows are visible)
    if batch_type == "recruiter_resume":
        for bf in batch_files:
            bulk_queue.enqueue(
                process_batch_resume_file,
                bf.id,
                batch_id,
                owner_profile_id,
                job_timeout="10m",
            )
    elif batch_type in ("employer_job_doc", "recruiter_job_doc"):
        for bf in batch_files:
            bulk_queue.enqueue(
                process_batch_job_document,
                bf.id,
                batch_id,
                batch_type,
                owner_profile_id,
                job_timeout="10m",
            )

    # Update batch status to processing
    batch.status = "processing"
    session.commit()

    return {
        "batch_id": batch_id,
        "status_url": f"/api/upload-batches/{batch_id}/status",
    }


# ---------------------------------------------------------------------------
# 1b. create_upload_batch_from_zip — expand a ZIP into per-file worker jobs
# ---------------------------------------------------------------------------


def create_upload_batch_from_zip(
    *,
    user_id: int,
    owner_profile_id: int,
    zip_stored_path: str,
    session,
) -> dict:
    """Stream files from a ZIP in storage, stage them one-at-a-time,
    create tracking rows (committed every CHUNK_COMMIT_SIZE), and
    enqueue ``process_batch_resume_file`` worker jobs.

    Peak memory: ~one resume file at a time instead of the full ZIP contents.
    Returns dict with ``batch_id`` and ``status_url``.
    """
    from app.services.queue import get_queue
    from app.services.storage import (
        delete_file,
        download_to_tempfile,
        upload_bytes,
    )

    # Download ZIP to a local temp file (only file kept on disk)
    zip_local = download_to_tempfile(zip_stored_path, suffix=".zip")

    try:
        with zipfile.ZipFile(str(zip_local)) as zf:
            # Filter resume entries from the ZIP without extracting
            resume_infos = [
                info
                for info in zf.infolist()
                if not info.is_dir()
                and not info.filename.startswith("__MACOSX")
                and not Path(info.filename).name.startswith(".")
                and Path(info.filename).suffix.lower() in RESUME_EXTENSIONS
                and info.file_size <= MAX_FILE_SIZE
            ]

            if not resume_infos:
                raise ValueError("ZIP contains no PDF or DOCX resume files.")
            if len(resume_infos) > MAX_ZIP_FILES:
                raise ValueError(
                    f"ZIP contains {len(resume_infos)} resume files, "
                    f"exceeding the limit of {MAX_ZIP_FILES:,}."
                )

            # Sort by filename for deterministic ordering
            resume_infos.sort(key=lambda i: Path(i.filename).name.lower())

            batch_id = str(uuid4())
            batch = UploadBatch(
                batch_id=batch_id,
                user_id=user_id,
                batch_type="recruiter_resume_zip",
                owner_profile_id=owner_profile_id,
                status="pending",
                total_files=len(resume_infos),
            )
            session.add(batch)
            session.flush()

            bulk_queue = get_queue("bulk")
            batch_file_ids: list[int] = []
            seen_hashes: set[str] = set()
            duplicates_skipped = 0

            for idx, info in enumerate(resume_infos):
                # Read one file at a time — keeps peak memory low
                contents = zf.read(info)
                file_hash = hashlib.sha256(contents).hexdigest()
                fname = Path(info.filename).name

                # Within-batch dedup: skip files with identical content
                if file_hash in seen_hashes:
                    duplicates_skipped += 1
                    del contents
                    continue
                seen_hashes.add(file_hash)

                staged_name = f"{idx}_{file_hash[:12]}_{fname}"
                staged_path = upload_bytes(
                    contents, f"staging/{batch_id}/", staged_name
                )

                bf = UploadBatchFile(
                    batch_id=batch_id,
                    file_index=idx,
                    original_filename=fname,
                    staged_path=staged_path,
                    file_size_bytes=len(contents),
                    sha256=file_hash,
                    status="pending",
                )
                session.add(bf)
                session.flush()
                batch_file_ids.append(bf.id)

                # Free memory immediately
                del contents

                # Commit in chunks to avoid giant transactions
                if (idx + 1) % CHUNK_COMMIT_SIZE == 0:
                    session.commit()
                    logger.info(
                        "ZIP batch %s: staged %d/%d files",
                        batch_id,
                        idx + 1,
                        len(resume_infos),
                    )

            # Update total_files to actual deduplicated count
            batch.total_files = len(batch_file_ids)

            if duplicates_skipped:
                logger.info(
                    "ZIP batch %s: skipped %d duplicate files within ZIP",
                    batch_id,
                    duplicates_skipped,
                )

            # Final commit for remaining rows
            session.commit()

        # Enqueue per-file worker jobs (after commit so rows are visible)
        for bf_id in batch_file_ids:
            bulk_queue.enqueue(
                process_batch_resume_file,
                bf_id,
                batch_id,
                owner_profile_id,
                job_timeout="10m",
            )

        batch.status = "processing"
        session.commit()

        logger.info(
            "ZIP batch %s: staged %d files, enqueued worker jobs",
            batch_id,
            len(batch_file_ids),
        )

        return {
            "batch_id": batch_id,
            "status_url": f"/api/upload-batches/{batch_id}/status",
        }

    finally:
        from app.services.storage import is_gcs_path

        if is_gcs_path(zip_stored_path) and zip_local.exists():
            try:
                zip_local.unlink()
            except OSError:
                pass
        # Remove the original ZIP from staging
        try:
            delete_file(zip_stored_path)
        except Exception:
            pass


def expand_zip_batch_job(
    user_id: int,
    owner_profile_id: int,
    zip_stored_path: str,
    migration_job_id: int | None = None,
) -> None:
    """RQ job: expand a ZIP into individual batch file jobs.

    Called from the migration router when source_platform == 'resume_archive'.
    Optionally links back to a MigrationJob for frontend status polling.
    """
    session = get_session_factory()()
    try:
        result = create_upload_batch_from_zip(
            user_id=user_id,
            owner_profile_id=owner_profile_id,
            zip_stored_path=zip_stored_path,
            session=session,
        )

        if migration_job_id:
            from app.models.migration import MigrationJob

            job = session.get(MigrationJob, migration_job_id)
            if job:
                job.stats_json = {
                    "batch_id": result["batch_id"],
                    "status": "processing",
                }
                session.commit()

    except Exception as exc:
        session.rollback()
        logger.exception("Failed to expand ZIP batch")
        # Mark migration job as failed if linked
        if migration_job_id:
            try:
                from app.models.migration import MigrationJob

                job = session.get(MigrationJob, migration_job_id)
                if job:
                    job.status = "failed"
                    job.error_log = [{"error": str(exc)[:500], "fatal": True}]
                    session.commit()
            except Exception:
                session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 2. process_batch_resume_file — RQ worker job
# ---------------------------------------------------------------------------


def process_batch_resume_file(
    batch_file_id: int,
    batch_id: str,
    recruiter_profile_id: int,
) -> None:
    """Worker job: process a single resume from a batch upload."""
    session = get_session_factory()()
    try:
        bf = session.get(UploadBatchFile, batch_file_id)
        if bf is None or bf.status not in ("pending", "processing"):
            return

        bf.status = "processing"
        session.commit()

        from app.models.candidate_profile import CandidateProfile
        from app.models.recruiter import RecruiterProfile
        from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
        from app.models.resume_document import ResumeDocument
        from app.models.user import User
        from app.services.profile_parser import extract_text, parse_profile_from_text
        from app.services.storage import (
            delete_file,
            download_to_tempfile,
            upload_bytes,
        )

        profile = session.get(RecruiterProfile, recruiter_profile_id)
        if profile is None:
            _fail_file(session, bf, "Recruiter profile not found")
            _finalize_batch(session, batch_id, "failed")
            return

        # Cross-batch dedup: check if same content already succeeded for this recruiter
        if bf.sha256:
            existing = session.execute(
                select(UploadBatchFile.id)
                .join(UploadBatch, UploadBatchFile.batch_id == UploadBatch.batch_id)
                .where(
                    UploadBatchFile.sha256 == bf.sha256,
                    UploadBatchFile.status == "succeeded",
                    UploadBatch.owner_profile_id == recruiter_profile_id,
                    UploadBatchFile.id != batch_file_id,
                )
                .limit(1)
            ).scalar_one_or_none()

            if existing is not None:
                bf.status = "skipped"
                bf.error_message = "Duplicate resume (already imported)"
                bf.processed_at = datetime.now(UTC)
                session.commit()
                _finalize_batch(session, batch_id, "skipped")
                return

        filename = bf.original_filename
        ext = Path(filename).suffix.lower()

        # Download staged file
        tmp_path = download_to_tempfile(bf.staged_path, suffix=ext)
        try:
            # Extract text
            text = extract_text(tmp_path)
            if not text or len(text.strip()) < 20:
                _fail_file(session, bf, "Could not extract meaningful text from file.")
                _finalize_batch(session, batch_id, "failed")
                return

            # Parse profile (fast regex)
            profile_json = parse_profile_from_text(text)
            basics = profile_json.get("basics", {})
            parsed_email = basics.get("email")
            parsed_name = basics.get("name")

            # Read raw bytes for permanent storage
            raw_bytes = tmp_path.read_bytes()
            file_hash = bf.sha256 or hashlib.sha256(raw_bytes).hexdigest()

            # Save to permanent location
            dest_filename = f"{file_hash[:16]}_{filename}"
            stored_path = upload_bytes(raw_bytes, "recruiter_resumes/", dest_filename)

            # Create ResumeDocument
            resume_doc = ResumeDocument(
                user_id=None,
                filename=filename,
                path=stored_path,
                sha256=file_hash,
            )
            session.add(resume_doc)
            session.flush()

            # Create CandidateProfile
            profile_json["source"] = "recruiter_resume_upload"
            profile_json["sourced_by_user_id"] = profile.user_id
            new_cp = CandidateProfile(
                user_id=None,
                resume_document_id=resume_doc.id,
                version=1,
                profile_json=profile_json,
                profile_visibility="private",
                open_to_opportunities=False,
                llm_parse_status="pending",
            )
            session.add(new_cp)
            session.flush()

            # 3-way email resolution
            result_status = "new"
            pipeline_candidate_id = None

            if parsed_email:
                parsed_email_lower = parsed_email.strip().lower()

                # Check platform users
                platform_user = session.execute(
                    select(User).where(func.lower(User.email) == parsed_email_lower)
                ).scalar_one_or_none()

                if platform_user:
                    existing_cp = session.execute(
                        select(CandidateProfile)
                        .where(CandidateProfile.user_id == platform_user.id)
                        .order_by(CandidateProfile.id.desc())
                    ).scalar_one_or_none()
                    linked_cp_id = existing_cp.id if existing_cp else new_cp.id

                    pipeline_entry = session.execute(
                        select(RecruiterPipelineCandidate).where(
                            RecruiterPipelineCandidate.recruiter_profile_id
                            == profile.id,
                            func.lower(RecruiterPipelineCandidate.external_email)
                            == parsed_email_lower,
                        )
                    ).scalar_one_or_none()

                    if pipeline_entry:
                        pipeline_entry.candidate_profile_id = linked_cp_id
                    else:
                        pipeline_entry = RecruiterPipelineCandidate(
                            recruiter_profile_id=profile.id,
                            candidate_profile_id=linked_cp_id,
                            external_name=parsed_name,
                            external_email=parsed_email,
                            source="recruiter_resume_upload",
                            stage="sourced",
                        )
                        session.add(pipeline_entry)
                        session.flush()

                    pipeline_candidate_id = pipeline_entry.id
                    result_status = "linked_platform"
                else:
                    pipeline_entry = session.execute(
                        select(RecruiterPipelineCandidate).where(
                            RecruiterPipelineCandidate.recruiter_profile_id
                            == profile.id,
                            func.lower(RecruiterPipelineCandidate.external_email)
                            == parsed_email_lower,
                        )
                    ).scalar_one_or_none()

                    if pipeline_entry:
                        pipeline_entry.candidate_profile_id = new_cp.id
                        pipeline_candidate_id = pipeline_entry.id
                        result_status = "matched"
                    else:
                        pipeline_entry = RecruiterPipelineCandidate(
                            recruiter_profile_id=profile.id,
                            candidate_profile_id=new_cp.id,
                            external_name=parsed_name,
                            external_email=parsed_email,
                            source="recruiter_resume_upload",
                            stage="sourced",
                        )
                        session.add(pipeline_entry)
                        session.flush()
                        pipeline_candidate_id = pipeline_entry.id
                        result_status = "new"
            else:
                pipeline_entry = RecruiterPipelineCandidate(
                    recruiter_profile_id=profile.id,
                    candidate_profile_id=new_cp.id,
                    external_name=parsed_name or filename,
                    source="recruiter_resume_upload",
                    stage="sourced",
                )
                session.add(pipeline_entry)
                session.flush()
                pipeline_candidate_id = pipeline_entry.id
                result_status = "new"

            # Increment usage counter
            from app.services.billing import increment_recruiter_counter

            increment_recruiter_counter(profile, "resume_imports_used", session)

            # Queue LLM reparse on bulk queue
            try:
                from app.services.queue import get_queue
                from app.services.recruiter_llm_reparse import (
                    recruiter_llm_reparse_job,
                )

                get_queue("low").enqueue(
                    recruiter_llm_reparse_job,
                    new_cp.id,
                    resume_doc.id,
                    job_timeout="10m",
                )
            except Exception:
                logger.warning(
                    "Failed to enqueue LLM reparse for profile %d",
                    new_cp.id,
                    exc_info=True,
                )

            # Mark file succeeded
            bf.status = "succeeded"
            bf.result_json = json.dumps(
                {
                    "status": result_status,
                    "pipeline_candidate_id": pipeline_candidate_id,
                    "candidate_profile_id": new_cp.id,
                    "matched_email": parsed_email,
                    "parsed_name": parsed_name,
                }
            )
            bf.processed_at = datetime.now(UTC)
            session.commit()

        finally:
            # Clean up temp file (only if it was a GCS download)
            from app.services.storage import is_gcs_path

            if is_gcs_path(bf.staged_path) and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        # Clean up staged file
        try:
            delete_file(bf.staged_path)
        except Exception:
            pass

        _finalize_batch(session, batch_id, "succeeded")

    except Exception as exc:
        session.rollback()
        logger.exception("Error processing batch resume file %d", batch_file_id)
        # Retry or fail
        bf = session.get(UploadBatchFile, batch_file_id)
        if bf is not None:
            if bf.retry_count < MAX_RETRIES and _is_transient(exc):
                bf.retry_count += 1
                bf.status = "pending"
                session.commit()
                from app.services.queue import get_queue

                get_queue("bulk").enqueue(
                    process_batch_resume_file,
                    batch_file_id,
                    batch_id,
                    recruiter_profile_id,
                    job_timeout="10m",
                )
            else:
                _fail_file(session, bf, str(exc))
                _finalize_batch(session, batch_id, "failed")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 3. process_batch_job_document — RQ worker job
# ---------------------------------------------------------------------------


def process_batch_job_document(
    batch_file_id: int,
    batch_id: str,
    batch_type: str,
    owner_profile_id: int,
) -> None:
    """Worker job: process a single job document from a batch upload."""
    session = get_session_factory()()
    try:
        bf = session.get(UploadBatchFile, batch_file_id)
        if bf is None or bf.status not in ("pending", "processing"):
            return

        bf.status = "processing"
        session.commit()

        from app.services.employer_job_parser import parse_job_document
        from app.services.storage import delete_file, download_to_tempfile

        filename = bf.original_filename
        ext = Path(filename).suffix.lower()

        # Download staged file
        tmp_path = download_to_tempfile(bf.staged_path, suffix=ext)
        try:
            parsed = parse_job_document(str(tmp_path))

            if not parsed.get("title"):
                _fail_file(session, bf, "Could not extract job title from document.")
                _finalize_batch(session, batch_id, "failed")
                return

            if batch_type == "employer_job_doc":
                _create_employer_job(session, parsed, owner_profile_id, bf)
            else:
                _create_recruiter_job(session, parsed, owner_profile_id, bf)

            bf.status = "succeeded"
            bf.result_json = json.dumps(
                {
                    "title": parsed.get("title"),
                    "job_id": json.loads(bf.result_json or "{}").get("job_id"),
                }
            )
            bf.processed_at = datetime.now(UTC)
            session.commit()

        except RuntimeError as exc:
            _fail_file(session, bf, str(exc))
            _finalize_batch(session, batch_id, "failed")
            return
        finally:
            from app.services.storage import is_gcs_path

            if is_gcs_path(bf.staged_path) and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        # Clean up staged file
        try:
            delete_file(bf.staged_path)
        except Exception:
            pass

        _finalize_batch(session, batch_id, "succeeded")

    except Exception as exc:
        session.rollback()
        logger.exception("Error processing batch job document %d", batch_file_id)
        bf = session.get(UploadBatchFile, batch_file_id)
        if bf is not None:
            if bf.retry_count < MAX_RETRIES and _is_transient(exc):
                bf.retry_count += 1
                bf.status = "pending"
                session.commit()
                from app.services.queue import get_queue

                get_queue("bulk").enqueue(
                    process_batch_job_document,
                    batch_file_id,
                    batch_id,
                    batch_type,
                    owner_profile_id,
                    job_timeout="10m",
                )
            else:
                _fail_file(session, bf, str(exc))
                _finalize_batch(session, batch_id, "failed")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers — job document creation
# ---------------------------------------------------------------------------


def _create_employer_job(session, parsed, employer_id, bf):
    from app.models.employer import EmployerJob, EmployerProfile
    from app.services.billing import increment_employer_counter

    employer = session.get(EmployerProfile, employer_id)

    job = EmployerJob(
        employer_id=employer_id,
        title=parsed.get("title"),
        description=parsed.get("description", ""),
        requirements=parsed.get("requirements"),
        nice_to_haves=parsed.get("nice_to_haves"),
        location=parsed.get("location"),
        remote_policy=parsed.get("remote_policy"),
        employment_type=parsed.get("employment_type"),
        job_id_external=parsed.get("job_id_external"),
        start_date=parsed.get("start_date"),
        close_date=parsed.get("close_date"),
        job_category=parsed.get("job_category"),
        client_company_name=parsed.get("client_company_name"),
        department=parsed.get("department"),
        certifications_required=parsed.get("certifications_required"),
        job_type=parsed.get("job_type"),
        salary_min=parsed.get("salary_min"),
        salary_max=parsed.get("salary_max"),
        salary_currency=parsed.get("salary_currency") or "USD",
        equity_offered=parsed.get("equity_offered") or False,
        application_email=parsed.get("application_email"),
        application_url=parsed.get("application_url"),
        parsed_from_document=True,
        parsing_confidence=parsed.get("parsing_confidence", 0.0),
        status="draft",
    )
    session.add(job)
    session.flush()

    if employer is not None:
        increment_employer_counter(employer, "ai_parsing_used", session)

    bf.result_json = json.dumps({"job_id": job.id, "title": parsed.get("title")})


def _create_recruiter_job(session, parsed, recruiter_profile_id, bf):
    from datetime import date as _date

    from app.models.recruiter import RecruiterProfile
    from app.models.recruiter_job import RecruiterJob
    from app.services.billing import increment_recruiter_counter
    from app.services.job_linking import auto_link_recruiter_job

    profile = session.get(RecruiterProfile, recruiter_profile_id)

    start_at = None
    closes_at = None
    sd = parsed.get("start_date")
    cd = parsed.get("close_date")
    if isinstance(sd, _date):
        start_at = datetime(sd.year, sd.month, sd.day, tzinfo=UTC)
    if isinstance(cd, _date):
        closes_at = datetime(cd.year, cd.month, cd.day, tzinfo=UTC)

    job = RecruiterJob(
        recruiter_profile_id=recruiter_profile_id,
        title=parsed.get("title"),
        description=parsed.get("description", ""),
        requirements=parsed.get("requirements"),
        nice_to_haves=parsed.get("nice_to_haves"),
        location=parsed.get("location"),
        remote_policy=parsed.get("remote_policy"),
        employment_type=parsed.get("employment_type"),
        salary_min=parsed.get("salary_min"),
        salary_max=parsed.get("salary_max"),
        salary_currency=parsed.get("salary_currency") or "USD",
        department=parsed.get("department"),
        job_id_external=parsed.get("job_id_external"),
        job_category=parsed.get("job_category"),
        client_company_name=parsed.get("client_company_name"),
        application_email=parsed.get("application_email"),
        application_url=parsed.get("application_url"),
        start_at=start_at,
        closes_at=closes_at,
        status="draft",
    )
    session.add(job)
    session.flush()

    auto_link_recruiter_job(session, job)

    if profile is not None:
        increment_recruiter_counter(profile, "job_uploads_used", session)

    bf.result_json = json.dumps({"job_id": job.id, "title": parsed.get("title")})


# ---------------------------------------------------------------------------
# 4. finalize_batch — update batch counters and status
# ---------------------------------------------------------------------------


def _finalize_batch(
    session, batch_id: str, file_status: str = "succeeded"
) -> None:
    """Atomically increment batch counters. Mark completed when all files done.

    ``file_status`` should be ``"succeeded"``, ``"failed"``, or ``"skipped"``.
    Uses a single UPDATE … SET … RETURNING instead of 4× COUNT(*) aggregates,
    making this O(1) per call instead of O(N).
    """
    from sqlalchemy import update

    # Build the increments based on file terminal status
    increments: dict = {
        UploadBatch.files_completed: UploadBatch.files_completed + 1,
    }
    if file_status == "succeeded":
        increments[UploadBatch.files_succeeded] = UploadBatch.files_succeeded + 1
    elif file_status in ("failed", "skipped"):
        increments[UploadBatch.files_failed] = UploadBatch.files_failed + 1

    result = session.execute(
        update(UploadBatch)
        .where(UploadBatch.batch_id == batch_id)
        .values(**increments)
        .returning(
            UploadBatch.files_completed,
            UploadBatch.total_files,
            UploadBatch.files_succeeded,
            UploadBatch.files_failed,
            UploadBatch.batch_type,
            UploadBatch.user_id,
        )
    )
    row = result.fetchone()
    if row is None:
        session.commit()
        return

    completed, total, succeeded, failed, batch_type, user_id = row

    if completed >= total:
        session.execute(
            update(UploadBatch)
            .where(UploadBatch.batch_id == batch_id)
            .values(status="completed", completed_at=datetime.now(UTC))
        )

    session.commit()

    # Post-completion actions
    if completed >= total:
        if batch_type == "recruiter_resume_zip":
            _send_zip_batch_email_simple(session, user_id, succeeded, failed, total)
        _maybe_start_next_queued_import(session)


# ---------------------------------------------------------------------------
# 5. cleanup_stale_staging — scheduled maintenance
# ---------------------------------------------------------------------------


def cleanup_stale_staging() -> None:
    """Delete staged files for completed batches or batches older than 7 days."""
    from app.services.storage import delete_file

    session = get_session_factory()()
    try:
        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        cutoff = cutoff - timedelta(days=7)

        stale_files = (
            session.execute(
                select(UploadBatchFile)
                .join(
                    UploadBatch,
                    UploadBatchFile.batch_id == UploadBatch.batch_id,
                )
                .where(
                    (UploadBatch.status == "completed")
                    | (UploadBatch.created_at < cutoff),
                    UploadBatchFile.staged_path.isnot(None),
                    UploadBatchFile.staged_path != "",
                )
            )
            .scalars()
            .all()
        )

        for bf in stale_files:
            try:
                delete_file(bf.staged_path)
                bf.staged_path = ""
            except Exception:
                logger.warning("Failed to clean staged file %s", bf.staged_path)

        session.commit()
        logger.info("Cleaned up %d stale staged files", len(stale_files))
    except Exception:
        session.rollback()
        logger.exception("Error cleaning stale staging files")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_zip_batch_email_simple(
    session, user_id: int, succeeded: int, failed: int, total: int
) -> None:
    """Best-effort completion email for ZIP resume imports."""
    try:
        from app.models.user import User
        from app.services.email import send_migration_complete_email

        user = session.get(User, user_id)
        if not user or not user.email:
            return
        send_migration_complete_email(
            to_email=user.email,
            imported=succeeded,
            skipped=0,
            errors=failed,
            total=total,
            job_id=0,
        )
    except Exception:
        logger.warning("Failed to send ZIP batch completion email", exc_info=True)


def _fail_file(session, bf: UploadBatchFile, error: str) -> None:
    """Mark a batch file as failed."""
    bf.status = "failed"
    bf.error_message = error[:2000] if error else "Unknown error"
    bf.processed_at = datetime.now(UTC)
    session.commit()


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    transient_types = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    if isinstance(exc, transient_types):
        return True
    msg = str(exc).lower()
    return any(
        kw in msg for kw in ("timeout", "connection", "temporarily", "503", "429")
    )


def _collect_resume_files(directory: str) -> list[Path]:
    """Walk directory tree and collect PDF/DOCX files, sorted by name.

    Skips hidden files, macOS resource forks, and files over MAX_FILE_SIZE.
    """
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


# ---------------------------------------------------------------------------
# Import queue management (Phase E — system-wide import gate)
# ---------------------------------------------------------------------------


def get_import_queue_info(session) -> dict:
    """Return info about the system-wide import queue.

    Returns dict with:
    - active_import_running: bool
    - queue_depth: int (number of queued jobs)
    - files_remaining: int (files left in active import, 0 if none)
    - estimated_wait_minutes: float
    """
    from app.models.migration import MigrationJob

    # Check for active import
    active = session.execute(
        select(MigrationJob).where(MigrationJob.status == "importing")
    ).scalar_one_or_none()

    active_files_remaining = 0
    if active and active.stats_json and active.stats_json.get("batch_id"):
        batch = session.execute(
            select(UploadBatch).where(
                UploadBatch.batch_id == active.stats_json["batch_id"]
            )
        ).scalar_one_or_none()
        if batch:
            active_files_remaining = max(
                0, batch.total_files - batch.files_completed
            )

    # Count queued jobs
    queued_jobs = (
        session.execute(
            select(MigrationJob)
            .where(MigrationJob.status == "queued")
            .order_by(MigrationJob.queued_at.asc())
        )
        .scalars()
        .all()
    )

    # Estimate total files in queued jobs (from config_json if available)
    queued_files = 0
    for qj in queued_jobs:
        cfg = qj.config_json or {}
        detection = cfg.get("detection", {})
        queued_files += detection.get("row_count", 1000)  # default estimate

    total_files = active_files_remaining + queued_files
    estimated_minutes = (total_files / PROCESSING_RATE) * 60 if total_files > 0 else 0

    return {
        "active_import_running": active is not None,
        "queue_depth": len(queued_jobs),
        "files_remaining": active_files_remaining,
        "estimated_wait_minutes": round(estimated_minutes, 1),
    }


def _maybe_start_next_queued_import(session) -> None:
    """If no import is active, start the next queued one (FIFO by queued_at)."""
    from app.models.migration import MigrationJob

    # Check for any active import
    active = session.execute(
        select(MigrationJob).where(MigrationJob.status == "importing")
    ).scalar_one_or_none()
    if active is not None:
        return

    # Find the oldest queued job
    next_job = session.execute(
        select(MigrationJob)
        .where(MigrationJob.status == "queued")
        .order_by(MigrationJob.queued_at.asc())
    ).scalar_one_or_none()
    if next_job is None:
        return

    # Transition to importing and enqueue the ZIP expand job
    next_job.status = "importing"
    next_job.started_at = datetime.now(UTC)
    session.commit()

    config = next_job.config_json or {}
    recruiter_profile_id = config.get("recruiter_profile_id")
    if not recruiter_profile_id or not next_job.source_file_path:
        next_job.status = "failed"
        next_job.error_log = [{"error": "Missing config for queued job", "fatal": True}]
        session.commit()
        return

    try:
        from app.services.queue import get_queue

        queue = get_queue("low")
        queue.enqueue(
            expand_zip_batch_job,
            user_id=next_job.user_id,
            owner_profile_id=recruiter_profile_id,
            zip_stored_path=next_job.source_file_path,
            migration_job_id=next_job.id,
            job_timeout="30m",
        )
        logger.info("Auto-started queued import job %d", next_job.id)
    except Exception:
        logger.exception("Failed to enqueue queued import job %d", next_job.id)
        next_job.status = "failed"
        next_job.error_log = [
            {"error": "Failed to enqueue job from queue", "fatal": True}
        ]
        session.commit()


def reconcile_stale_batches() -> None:
    """Find batches stuck in 'processing' where all files are done, and mark
    them completed. Safety net for missed finalize calls.
    """
    session = get_session_factory()()
    try:
        stuck = (
            session.execute(
                select(UploadBatch).where(
                    UploadBatch.status == "processing",
                    UploadBatch.files_completed >= UploadBatch.total_files,
                    UploadBatch.total_files > 0,
                )
            )
            .scalars()
            .all()
        )
        for batch in stuck:
            batch.status = "completed"
            batch.completed_at = datetime.now(UTC)
            logger.warning(
                "Reconciled stale batch %s: %d/%d completed",
                batch.batch_id,
                batch.files_completed,
                batch.total_files,
            )

        if stuck:
            session.commit()
            # Trigger next queued import in case one was waiting
            _maybe_start_next_queued_import(session)

        logger.info("Reconcile stale batches: fixed %d", len(stuck))
    except Exception:
        session.rollback()
        logger.exception("Error reconciling stale batches")
    finally:
        session.close()


def start_queued_imports() -> None:
    """Safety-net scheduler job: if no import is active, start the next
    queued one. Catches missed triggers from worker crashes.
    """
    session = get_session_factory()()
    try:
        _maybe_start_next_queued_import(session)
    except Exception:
        session.rollback()
        logger.exception("Error in start_queued_imports scheduler job")
    finally:
        session.close()
