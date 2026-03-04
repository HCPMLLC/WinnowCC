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

from sqlalchemy import func, select, update

from app.db.session import get_session_factory
from app.models.upload_batch import UploadBatch, UploadBatchFile

logger = logging.getLogger(__name__)

MAX_ACTIVE_BATCHES = 3
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_RETRIES = 2
MAX_ZIP_FILES = 10_000
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

    for idx, (filename, contents) in enumerate(files):
        file_hash = hashlib.sha256(contents).hexdigest()

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
    """Stream files from a ZIP in storage one at a time, stage each to
    cloud storage, create tracking rows with chunked commits, and enqueue
    per-file worker jobs.

    Peak memory: ~200KB (one file at a time) instead of ~2GB for 10K files.
    Returns dict with ``batch_id`` and ``status_url``.
    """
    from app.services.queue import get_queue
    from app.services.storage import (
        delete_file,
        download_to_tempfile,
        upload_bytes,
    )

    CHUNK_COMMIT_SIZE = 500  # commit DB rows every N files

    # Download ZIP to a local temp file
    zip_local = download_to_tempfile(zip_stored_path, suffix=".zip")

    try:
        with zipfile.ZipFile(str(zip_local)) as zf:
            # Enumerate entries without extracting — names only
            entries = [
                info
                for info in zf.infolist()
                if not info.is_dir()
                and not info.filename.startswith("__MACOSX")
                and not Path(info.filename).name.startswith(".")
                and Path(info.filename).suffix.lower() in RESUME_EXTENSIONS
                and info.file_size <= MAX_FILE_SIZE
            ]
            entries.sort(key=lambda info: info.filename.lower())

            if not entries:
                raise ValueError("ZIP contains no PDF or DOCX resume files.")
            if len(entries) > MAX_ZIP_FILES:
                raise ValueError(
                    f"ZIP contains {len(entries)} resume files, "
                    f"exceeding the limit of {MAX_ZIP_FILES}."
                )

            batch_id = str(uuid4())
            batch = UploadBatch(
                batch_id=batch_id,
                user_id=user_id,
                batch_type="recruiter_resume_zip",
                owner_profile_id=owner_profile_id,
                status="pending",
                total_files=len(entries),
            )
            session.add(batch)
            session.flush()

            bulk_queue = get_queue("bulk")
            batch_file_ids: list[int] = []

            for idx, info in enumerate(entries):
                # Read one file at a time — peak memory ~200KB
                contents = zf.read(info.filename)
                file_hash = hashlib.sha256(contents).hexdigest()
                base_name = Path(info.filename).name

                staged_name = f"{idx}_{file_hash[:12]}_{base_name}"
                staged_path = upload_bytes(
                    contents, f"staging/{batch_id}/", staged_name
                )

                bf = UploadBatchFile(
                    batch_id=batch_id,
                    file_index=idx,
                    original_filename=base_name,
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

                # Chunked commit every CHUNK_COMMIT_SIZE files
                if (idx + 1) % CHUNK_COMMIT_SIZE == 0:
                    session.commit()
                    logger.info(
                        "ZIP batch %s: staged %d/%d files",
                        batch_id,
                        idx + 1,
                        len(entries),
                    )

            # Final commit for remaining rows
            session.commit()

        # Enqueue per-file worker jobs (after all rows committed)
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
        # Clean up the local ZIP temp file only (no extract_dir needed)
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
        from app.services.resume_pipeline import ParseOptions, extract_and_parse
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

        filename = bf.original_filename
        ext = Path(filename).suffix.lower()

        # Download staged file
        tmp_path = download_to_tempfile(bf.staged_path, suffix=ext)
        try:
            # Extract text and parse with regex (fast path for batch)
            try:
                result = extract_and_parse(
                    tmp_path,
                    ParseOptions(parser_strategy="regex_only", min_text_length=20),
                )
            except ValueError:
                _fail_file(session, bf, "Could not extract meaningful text from file.")
                _finalize_batch(session, batch_id, "failed")
                return

            profile_json = result.profile_json
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


def _finalize_batch(session, batch_id: str, file_status: str = "succeeded") -> None:
    """Atomically increment batch counters. Mark completed when all files are done.

    ``file_status`` must be one of ``"succeeded"``, ``"failed"``, or ``"skipped"``.
    Each call is O(1) — no COUNT(*) over all batch files.
    """
    # Build the SET clause based on file_status
    set_clause = {"files_completed": UploadBatch.files_completed + 1}
    if file_status == "succeeded":
        set_clause["files_succeeded"] = UploadBatch.files_succeeded + 1
    elif file_status == "failed":
        set_clause["files_failed"] = UploadBatch.files_failed + 1
    # "skipped" only increments files_completed

    result = session.execute(
        update(UploadBatch)
        .where(UploadBatch.batch_id == batch_id)
        .values(**set_clause)
        .returning(
            UploadBatch.total_files,
            UploadBatch.files_completed,
            UploadBatch.files_succeeded,
            UploadBatch.files_failed,
            UploadBatch.batch_type,
            UploadBatch.status,
        )
    )
    row = result.fetchone()
    if row is None:
        session.commit()
        return

    (
        total_files,
        files_completed,
        files_succeeded,
        files_failed,
        batch_type,
        status,
    ) = row

    if files_completed >= total_files and status != "completed":
        session.execute(
            update(UploadBatch)
            .where(UploadBatch.batch_id == batch_id)
            .values(status="completed", completed_at=datetime.now(UTC))
        )

    session.commit()

    # Send completion email for large ZIP-originated batches
    if files_completed >= total_files and batch_type == "recruiter_resume_zip":
        batch = session.execute(
            select(UploadBatch).where(UploadBatch.batch_id == batch_id)
        ).scalar_one_or_none()
        if batch:
            _send_zip_batch_email(
                session,
                batch,
                type(
                    "C",
                    (),
                    {
                        "succeeded": files_succeeded,
                        "failed": files_failed,
                    },
                )(),
            )
            # Trigger next queued import when a ZIP batch finishes
            _start_next_queued_import(session)


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


def _start_next_queued_import(session) -> None:
    """Start the next queued import if no large import is active.

    Called after a ZIP batch completes and by the scheduler every 2 minutes.
    """
    from app.models.migration import MigrationJob

    # Check for any active large import
    active = session.execute(
        select(MigrationJob).where(
            MigrationJob.status == "importing",
            MigrationJob.source_platform == "resume_archive",
        )
    ).scalar_one_or_none()
    if active:
        return

    # Also check for active ZIP upload batches not linked to a migration
    active_batch = session.execute(
        select(UploadBatch).where(
            UploadBatch.batch_type == "recruiter_resume_zip",
            UploadBatch.status.in_(["pending", "processing"]),
        )
    ).scalar_one_or_none()
    if active_batch:
        return

    # Find the oldest queued import
    next_job = session.execute(
        select(MigrationJob)
        .where(MigrationJob.status == "queued")
        .order_by(MigrationJob.queued_at.asc())
    ).scalar_one_or_none()
    if not next_job:
        return

    # Start it
    from app.services.queue import get_queue

    next_job.status = "importing"
    next_job.started_at = datetime.now(UTC)
    session.commit()

    try:
        config = next_job.config_json or {}
        queue = get_queue("low")
        queue.enqueue(
            expand_zip_batch_job,
            user_id=next_job.user_id,
            owner_profile_id=config.get("recruiter_profile_id"),
            zip_stored_path=next_job.source_file_path,
            migration_job_id=next_job.id,
            job_timeout="30m",
        )
        logger.info("Auto-started queued import job %d", next_job.id)
    except Exception:
        logger.exception("Failed to auto-start queued import job %d", next_job.id)
        next_job.status = "queued"
        session.commit()


def reconcile_stale_batches() -> None:
    """Safety net: fix counters for batches stuck in 'processing' for >2 hours.

    Runs a COUNT(*) only for stale batches — not on every file completion.
    Called by the scheduler every 2 minutes.
    """
    from datetime import timedelta

    session = get_session_factory()()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=2)

        stale_batches = (
            session.execute(
                select(UploadBatch).where(
                    UploadBatch.status == "processing",
                    UploadBatch.created_at < cutoff,
                )
            )
            .scalars()
            .all()
        )

        for batch in stale_batches:
            counts = session.execute(
                select(
                    func.count(UploadBatchFile.id)
                    .filter(
                        UploadBatchFile.status.in_(["succeeded", "failed", "skipped"])
                    )
                    .label("completed"),
                    func.count(UploadBatchFile.id)
                    .filter(UploadBatchFile.status == "succeeded")
                    .label("succeeded"),
                    func.count(UploadBatchFile.id)
                    .filter(UploadBatchFile.status == "failed")
                    .label("failed"),
                ).where(UploadBatchFile.batch_id == batch.batch_id)
            ).one()

            batch.files_completed = counts.completed
            batch.files_succeeded = counts.succeeded
            batch.files_failed = counts.failed

            if counts.completed >= batch.total_files:
                batch.status = "completed"
                batch.completed_at = datetime.now(UTC)
                logger.info(
                    "Reconciled stale batch %s: marked completed (%d/%d)",
                    batch.batch_id,
                    counts.completed,
                    batch.total_files,
                )

        session.commit()

        # After reconciling, check if any queued imports can start
        if stale_batches:
            _start_next_queued_import(session)

    except Exception:
        session.rollback()
        logger.exception("Error reconciling stale batches")
    finally:
        session.close()


def get_import_queue_info(session, migration_job_id: int) -> dict:
    """Calculate queue position and estimated start/finish times.

    Returns:
        queue_position: 0 = currently processing, 1 = next, etc.
        estimated_start_utc: ISO string (null if already processing)
        estimated_finish_utc: ISO string
        active_batch_progress: dict with total/completed (null if no active batch)
    """
    from app.models.migration import MigrationJob

    PROCESSING_RATE = 960  # files/hour (8 workers x ~2 per minute)

    job = session.get(MigrationJob, migration_job_id)
    if not job:
        return {
            "queue_position": None,
            "estimated_start_utc": None,
            "estimated_finish_utc": None,
            "active_batch_progress": None,
        }

    # If already importing, position is 0
    if job.status == "importing":
        batch = session.execute(
            select(UploadBatch)
            .where(
                UploadBatch.user_id == job.user_id,
                UploadBatch.batch_type == "recruiter_resume_zip",
                UploadBatch.status.in_(["pending", "processing"]),
            )
            .order_by(UploadBatch.created_at.desc())
        ).scalar_one_or_none()

        progress = None
        est_finish = None
        if batch:
            remaining = batch.total_files - batch.files_completed
            hours_left = remaining / PROCESSING_RATE if PROCESSING_RATE > 0 else 0
            from datetime import timedelta

            est_finish = (datetime.now(UTC) + timedelta(hours=hours_left)).isoformat()
            progress = {
                "total_files": batch.total_files,
                "files_completed": batch.files_completed,
                "files_succeeded": batch.files_succeeded,
                "files_failed": batch.files_failed,
            }

        return {
            "queue_position": 0,
            "estimated_start_utc": None,
            "estimated_finish_utc": est_finish,
            "active_batch_progress": progress,
        }

    # If queued, calculate position
    if job.status == "queued":
        # Count queued jobs ahead (earlier queued_at)
        ahead_count = (
            session.execute(
                select(func.count(MigrationJob.id)).where(
                    MigrationJob.status == "queued",
                    MigrationJob.queued_at < job.queued_at,
                )
            ).scalar()
            or 0
        )

        # Find the currently active import
        active_job = session.execute(
            select(MigrationJob).where(
                MigrationJob.status == "importing",
                MigrationJob.source_platform == "resume_archive",
            )
        ).scalar_one_or_none()

        from datetime import timedelta

        wait_hours = 0.0

        # Time remaining on active import
        if active_job:
            active_batch = session.execute(
                select(UploadBatch)
                .where(
                    UploadBatch.user_id == active_job.user_id,
                    UploadBatch.batch_type == "recruiter_resume_zip",
                    UploadBatch.status.in_(["pending", "processing"]),
                )
                .order_by(UploadBatch.created_at.desc())
            ).scalar_one_or_none()
            if active_batch:
                remaining = active_batch.total_files - active_batch.files_completed
                wait_hours += remaining / PROCESSING_RATE

        # Time for each queued job ahead
        ahead_jobs = (
            session.execute(
                select(MigrationJob)
                .where(
                    MigrationJob.status == "queued",
                    MigrationJob.queued_at < job.queued_at,
                )
                .order_by(MigrationJob.queued_at.asc())
            )
            .scalars()
            .all()
        )
        for aj in ahead_jobs:
            # Estimate files from config_json if available
            aj_config = aj.config_json or {}
            aj_detection = aj_config.get("detection", {})
            est_files = aj_detection.get("row_count", 1000)
            wait_hours += est_files / PROCESSING_RATE

        # This job's own processing time
        own_config = job.config_json or {}
        own_detection = own_config.get("detection", {})
        own_files = own_detection.get("row_count", 1000)
        own_hours = own_files / PROCESSING_RATE

        now = datetime.now(UTC)
        est_start = now + timedelta(hours=wait_hours)
        est_finish = est_start + timedelta(hours=own_hours)

        return {
            "queue_position": ahead_count + 1,
            "estimated_start_utc": est_start.isoformat(),
            "estimated_finish_utc": est_finish.isoformat(),
            "active_batch_progress": None,
        }

    # Completed or failed — no queue info needed
    return {
        "queue_position": None,
        "estimated_start_utc": None,
        "estimated_finish_utc": None,
        "active_batch_progress": None,
    }


def _send_zip_batch_email(session, batch: UploadBatch, counts) -> None:
    """Best-effort completion email for ZIP resume imports."""
    try:
        from app.models.user import User
        from app.services.email import send_migration_complete_email

        user = session.get(User, batch.user_id)
        if not user or not user.email:
            return
        send_migration_complete_email(
            to_email=user.email,
            imported=counts.succeeded,
            skipped=0,
            errors=counts.failed,
            total=batch.total_files,
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
