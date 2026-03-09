"""Async LLM re-parse job for recruiter-uploaded resumes.

Called by RQ worker after initial regex-based upload.  Updates the existing
CandidateProfile.profile_json with richer LLM-parsed data, matching the
quality of candidate-flow parsing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.resume_document import ResumeDocument
from app.services.resume_pipeline import (
    ParseOptions,
    extract_and_parse,
    merge_recruiter_reparse,
)
from app.services.storage import download_to_tempfile, is_gcs_path

logger = logging.getLogger(__name__)


def recruiter_llm_reparse_job(
    candidate_profile_id: int,
    resume_document_id: int,
) -> None:
    """Re-parse a recruiter-uploaded resume with LLM and update the profile."""
    session = get_session_factory()()
    try:
        cp = session.get(CandidateProfile, candidate_profile_id)
        if cp is None:
            logger.warning(
                "LLM reparse: CandidateProfile %d not found",
                candidate_profile_id,
            )
            return

        resume = session.get(ResumeDocument, resume_document_id)
        if resume is None or resume.deleted_at is not None:
            logger.warning(
                "LLM reparse: ResumeDocument %d not found or deleted",
                resume_document_id,
            )
            cp.llm_parse_status = "failed"
            session.commit()
            return

        cp.llm_parse_status = "running"
        session.commit()

        # Resolve file path — legacy uploads used local paths that may not
        # exist on the current container.  Fall back to GCS if available.
        stored_path = resume.path or ""
        if not is_gcs_path(stored_path) and not Path(stored_path).exists():
            gcs_bucket = os.environ.get("GCS_BUCKET", "")
            if gcs_bucket:
                # Derive GCS path from the local path filename
                fname = Path(stored_path).name
                gcs_path = f"gs://{gcs_bucket}/recruiter_resumes/{fname}"
                logger.info(
                    "LLM reparse: local path missing, trying GCS: %s",
                    gcs_path,
                )
                stored_path = gcs_path
                # Update the DB record so future lookups use GCS directly
                resume.path = gcs_path

        # Extract text and parse with LLM
        suffix = Path(resume.path).suffix if resume.path else ""
        local_path = download_to_tempfile(stored_path, suffix=suffix)
        try:
            result = extract_and_parse(
                local_path,
                ParseOptions(parser_strategy="llm_only", min_text_length=20),
            )
        except (ValueError, RuntimeError) as exc:
            cp.llm_parse_status = "failed"
            session.commit()
            logger.warning(
                "LLM reparse failed for profile %d: %s",
                candidate_profile_id,
                exc,
            )
            return
        finally:
            if is_gcs_path(stored_path):
                local_path.unlink(missing_ok=True)

        # Merge: preserve regex-extracted email/name and recruiter metadata
        existing = cp.profile_json or {}
        cp.profile_json = merge_recruiter_reparse(existing, result.profile_json)
        cp.llm_parse_status = "succeeded"
        session.commit()

        logger.info(
            "LLM reparse succeeded for profile %d (skills: %d, experience: %d)",
            candidate_profile_id,
            len(cp.profile_json.get("skills", [])),
            len(cp.profile_json.get("experience", [])),
        )

    except Exception as exc:
        session.rollback()
        try:
            cp = session.get(CandidateProfile, candidate_profile_id)
            if cp:
                cp.llm_parse_status = "failed"
                session.commit()
        except Exception:
            session.rollback()
        logger.exception(
            "LLM reparse failed for profile %d: %s",
            candidate_profile_id,
            exc,
        )
    finally:
        session.close()
