"""Bulk resume attach service for recruiters.

Matches uploaded resume files to existing pipeline candidates by email, ID,
or name, then parses and attaches them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.upload_batch import UploadBatch, UploadBatchFile

logger = logging.getLogger(__name__)

RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_ZIP_FILES = 500


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize a name for fuzzy comparison."""
    return " ".join(name.lower().replace("_", " ").replace("-", " ").split())


def _extract_candidate_key(filename: str) -> dict:
    """Extract potential matching keys from a filename.

    Supports patterns like:
    - email@example.com.pdf -> email match
    - candidate_123.pdf or 123.pdf -> ID match
    - John_Smith.pdf or John Smith.pdf -> name match
    """
    stem = Path(filename).stem

    # Check for email pattern
    if "@" in stem and "." in stem.split("@")[-1]:
        return {"type": "email", "value": stem.lower()}

    # Check for numeric ID
    # Strip common prefixes like "candidate_", "cand_", "id_"
    id_stem = stem
    for prefix in ("candidate_", "cand_", "id_", "pipeline_"):
        if id_stem.lower().startswith(prefix):
            id_stem = id_stem[len(prefix):]
            break

    if id_stem.isdigit():
        return {"type": "id", "value": int(id_stem)}

    # Fall back to name match
    return {"type": "name", "value": _normalize_name(stem)}


def _match_file_to_candidates(
    file_key: dict,
    candidates: list,
) -> list[dict]:
    """Match a file key to pipeline candidates.

    Returns list of matches with confidence.
    """
    matches = []

    for cand in candidates:
        if file_key["type"] == "email" and cand.external_email:
            if cand.external_email.strip().lower() == file_key["value"]:
                matches.append({
                    "candidate_id": cand.id,
                    "matched_by": "email",
                    "confidence": "high",
                    "candidate_name": cand.external_name or "Unknown",
                    "candidate_email": cand.external_email,
                })

        elif file_key["type"] == "id":
            if cand.id == file_key["value"]:
                matches.append({
                    "candidate_id": cand.id,
                    "matched_by": "id",
                    "confidence": "high",
                    "candidate_name": cand.external_name or "Unknown",
                    "candidate_email": cand.external_email,
                })

        elif file_key["type"] == "name" and cand.external_name:
            cand_normalized = _normalize_name(cand.external_name)
            if cand_normalized == file_key["value"]:
                matches.append({
                    "candidate_id": cand.id,
                    "matched_by": "name",
                    "confidence": "medium",
                    "candidate_name": cand.external_name,
                    "candidate_email": cand.external_email,
                })

    return matches


# ---------------------------------------------------------------------------
# 1. preview_bulk_attach — called from HTTP endpoint
# ---------------------------------------------------------------------------


def preview_bulk_attach(
    *,
    recruiter_profile_id: int,
    user_id: int,
    zip_bytes: bytes,
    session,
) -> dict:
    """Extract ZIP, match files to pipeline candidates, return preview.

    Returns dict with file_matches (list of match previews) and
    batch metadata for confirmation.
    """
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
    from app.services.storage import upload_bytes

    # Load all pipeline candidates for this recruiter
    candidates = (
        session.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id
            )
        )
        .scalars()
        .all()
    )

    if not candidates:
        raise ValueError("No pipeline candidates found. Import candidates first.")

    # Extract and match ZIP contents
    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file.") from None

    entries = [
        info
        for info in zf.infolist()
        if not info.is_dir()
        and not info.filename.startswith("__MACOSX")
        and not Path(info.filename).name.startswith(".")
        and Path(info.filename).suffix.lower() in RESUME_EXTENSIONS
        and info.file_size <= MAX_FILE_SIZE
    ]

    if not entries:
        raise ValueError("ZIP contains no PDF or DOCX resume files.")
    if len(entries) > MAX_ZIP_FILES:
        raise ValueError(
            f"ZIP contains {len(entries)} files, max is {MAX_ZIP_FILES}."
        )

    # Stage ZIP to storage for later processing
    zip_hash = hashlib.sha256(zip_bytes).hexdigest()[:16]
    batch_id = str(uuid4())
    zip_staged_path = upload_bytes(
        zip_bytes, f"staging/{batch_id}/", f"bulk_attach_{zip_hash}.zip"
    )

    # Match each file to candidates
    file_matches = []
    for info in entries:
        base_name = Path(info.filename).name
        file_key = _extract_candidate_key(base_name)
        matches = _match_file_to_candidates(file_key, candidates)

        file_matches.append({
            "filename": base_name,
            "file_size": info.file_size,
            "match_key": file_key,
            "matches": matches,
            "matched": len(matches) > 0,
        })

    zf.close()

    # Store preview metadata for the confirmation step
    preview_data = {
        "batch_id": batch_id,
        "zip_staged_path": zip_staged_path,
        "recruiter_profile_id": recruiter_profile_id,
        "user_id": user_id,
        "file_matches": file_matches,
        "total_files": len(entries),
        "matched_files": sum(1 for f in file_matches if f["matched"]),
        "unmatched_files": sum(1 for f in file_matches if not f["matched"]),
    }

    return preview_data


# ---------------------------------------------------------------------------
# 2. process_bulk_attach — confirm and process selected matches
# ---------------------------------------------------------------------------


def process_bulk_attach(
    *,
    recruiter_profile_id: int,
    user_id: int,
    batch_id: str,
    zip_staged_path: str,
    selected_matches: list[dict],  # [{filename, candidate_id, matched_by}]
    session,
) -> dict:
    """Process confirmed matches — create batch, stage files, enqueue workers.

    Returns dict with batch_id and status_url.
    """
    from app.services.queue import get_queue
    from app.services.storage import download_to_tempfile, upload_bytes

    if not selected_matches:
        raise ValueError("No matches selected for processing.")

    # Build lookup: filename -> match info
    match_lookup = {m["filename"]: m for m in selected_matches}

    # Download ZIP and extract selected files
    zip_local = download_to_tempfile(zip_staged_path, suffix=".zip")

    try:
        with zipfile.ZipFile(str(zip_local)) as zf:
            files_to_process = []
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base_name = Path(info.filename).name
                if base_name in match_lookup:
                    contents = zf.read(info.filename)
                    files_to_process.append(
                        (base_name, contents, match_lookup[base_name])
                    )

        if not files_to_process:
            raise ValueError("No matching files found in ZIP.")

        # Create UploadBatch
        batch = UploadBatch(
            batch_id=batch_id,
            user_id=user_id,
            batch_type="bulk_attach",
            owner_profile_id=recruiter_profile_id,
            status="pending",
            total_files=len(files_to_process),
        )
        session.add(batch)
        session.flush()

        bulk_queue = get_queue("bulk")
        batch_file_ids = []

        for idx, (filename, contents, match_info) in enumerate(files_to_process):
            file_hash = hashlib.sha256(contents).hexdigest()
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
                result_json=json.dumps({
                    "candidate_id": match_info["candidate_id"],
                    "matched_by": match_info["matched_by"],
                }),
            )
            session.add(bf)
            session.flush()
            batch_file_ids.append(bf.id)
            del contents

        session.commit()

        # Enqueue worker jobs
        for bf_id in batch_file_ids:
            bulk_queue.enqueue(
                process_bulk_attach_file,
                bf_id,
                batch_id,
                recruiter_profile_id,
                job_timeout="10m",
            )

        batch.status = "processing"
        session.commit()

        return {
            "batch_id": batch_id,
            "status_url": f"/api/upload-batches/{batch_id}/status",
            "total_files": len(files_to_process),
        }

    finally:
        from app.services.storage import is_gcs_path

        if is_gcs_path(zip_staged_path) and zip_local.exists():
            try:
                zip_local.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 3. process_bulk_attach_file — RQ worker job
# ---------------------------------------------------------------------------


def process_bulk_attach_file(
    batch_file_id: int,
    batch_id: str,
    recruiter_profile_id: int,
) -> None:
    """Worker job: parse a resume and attach it to a pipeline candidate."""
    from app.services.batch_upload import (
        MAX_RETRIES,
        _fail_file,
        _finalize_batch,
        _is_transient,
    )

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
        from app.services.resume_pipeline import ParseOptions, extract_and_parse
        from app.services.storage import delete_file, download_to_tempfile, upload_bytes

        # Read match metadata from result_json
        match_meta = json.loads(bf.result_json or "{}")
        candidate_id = match_meta.get("candidate_id")
        matched_by = match_meta.get("matched_by", "unknown")

        if not candidate_id:
            _fail_file(session, bf, "No candidate_id in match metadata")
            _finalize_batch(session, batch_id, "failed")
            return

        profile = session.get(RecruiterProfile, recruiter_profile_id)
        if profile is None:
            _fail_file(session, bf, "Recruiter profile not found")
            _finalize_batch(session, batch_id, "failed")
            return

        pipeline_cand = session.get(RecruiterPipelineCandidate, candidate_id)
        if pipeline_cand is None:
            _fail_file(session, bf, f"Pipeline candidate {candidate_id} not found")
            _finalize_batch(session, batch_id, "failed")
            return

        filename = bf.original_filename
        ext = Path(filename).suffix.lower()

        # Download staged file
        tmp_path = download_to_tempfile(bf.staged_path, suffix=ext)
        try:
            # Extract text and parse
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

            # Create or update CandidateProfile
            profile_json["source"] = "bulk_attach"
            profile_json["sourced_by_user_id"] = profile.user_id

            if pipeline_cand.candidate_profile_id:
                # Update existing profile's resume
                existing_cp = session.get(
                    CandidateProfile, pipeline_cand.candidate_profile_id
                )
                if existing_cp:
                    existing_cp.resume_document_id = resume_doc.id
                    existing_cp.llm_parse_status = "pending"
                    cp_id = existing_cp.id
                else:
                    # Profile was deleted, create new
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
                    pipeline_cand.candidate_profile_id = new_cp.id
                    cp_id = new_cp.id
            else:
                # Dedup: check if a sourced profile with this email already
                # exists before creating a new one.  This prevents duplicates
                # when multiple pipeline candidates share the same email.
                email = (
                    (profile_json.get("basics") or {}).get("email") or ""
                ).strip().lower()
                existing_by_email = None
                if email:
                    from sqlalchemy import cast, select
                    from sqlalchemy.types import String

                    existing_by_email = session.execute(
                        select(CandidateProfile).where(
                            CandidateProfile.user_id.is_(None),
                            cast(
                                CandidateProfile.profile_json["basics"]["email"],
                                String,
                            ).ilike(email),
                        )
                    ).scalar_one_or_none()

                if existing_by_email:
                    existing_by_email.resume_document_id = resume_doc.id
                    existing_by_email.llm_parse_status = "pending"
                    pipeline_cand.candidate_profile_id = existing_by_email.id
                    cp_id = existing_by_email.id
                else:
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
                    pipeline_cand.candidate_profile_id = new_cp.id
                    cp_id = new_cp.id

            # Update pipeline candidate bulk attach tracking
            pipeline_cand.bulk_attach_batch_id = batch_id
            pipeline_cand.bulk_attach_status = "attached"
            pipeline_cand.bulk_attach_matched_by = matched_by
            pipeline_cand.external_resume_url = stored_path

            # Increment usage counter
            from app.services.billing import increment_recruiter_counter

            increment_recruiter_counter(profile, "resume_imports_used", session)

            # Queue LLM reparse
            try:
                from app.services.queue import get_queue
                from app.services.recruiter_llm_reparse import recruiter_llm_reparse_job

                get_queue("low").enqueue(
                    recruiter_llm_reparse_job,
                    cp_id,
                    resume_doc.id,
                    job_timeout="10m",
                )
            except Exception:
                logger.warning(
                    "Failed to enqueue LLM reparse for profile %d", cp_id, exc_info=True
                )

            # Mark file succeeded
            bf.status = "succeeded"
            bf.result_json = json.dumps({
                "status": "attached",
                "candidate_id": candidate_id,
                "matched_by": matched_by,
                "candidate_profile_id": cp_id,
                "resume_document_id": resume_doc.id,
            })
            bf.processed_at = datetime.now(UTC)
            session.commit()

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
        logger.exception("Error processing bulk attach file %d", batch_file_id)
        bf = session.get(UploadBatchFile, batch_file_id)
        if bf is not None:
            if bf.retry_count < MAX_RETRIES and _is_transient(exc):
                bf.retry_count += 1
                bf.status = "pending"
                session.commit()
                from app.services.queue import get_queue

                get_queue("bulk").enqueue(
                    process_bulk_attach_file,
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
