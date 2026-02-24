"""Async LLM re-parse job for recruiter-uploaded resumes.

Called by RQ worker after initial regex-based upload.  Updates the existing
CandidateProfile.profile_json with richer LLM-parsed data, matching the
quality of candidate-flow parsing.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.resume_document import ResumeDocument
from app.services.profile_parser import extract_text
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
        if resume is None:
            logger.warning(
                "LLM reparse: ResumeDocument %d not found",
                resume_document_id,
            )
            cp.llm_parse_status = "failed"
            session.commit()
            return

        cp.llm_parse_status = "running"
        session.commit()

        # Extract text from saved file
        suffix = Path(resume.path).suffix if resume.path else ""
        local_path = download_to_tempfile(resume.path, suffix=suffix)
        try:
            text = extract_text(local_path)
        finally:
            if is_gcs_path(resume.path):
                local_path.unlink(missing_ok=True)

        if not text or len(text.strip()) < 20:
            cp.llm_parse_status = "failed"
            session.commit()
            logger.warning(
                "LLM reparse: No text extracted for profile %d",
                candidate_profile_id,
            )
            return

        # Call LLM parser (same as candidate flow)
        from app.services.llm_parser import is_llm_parser_available, parse_with_llm

        if not is_llm_parser_available():
            cp.llm_parse_status = "failed"
            session.commit()
            logger.warning("LLM reparse: LLM parser not available")
            return

        llm_profile_json = parse_with_llm(text)

        # Merge: preserve regex-extracted email/name (critical for pipeline
        # matching) and recruiter metadata; upgrade everything else.
        existing = cp.profile_json or {}
        existing_basics = existing.get("basics", {})
        llm_basics = llm_profile_json.get("basics", {})

        for key in ("email", "name", "first_name", "last_name"):
            if existing_basics.get(key) and not llm_basics.get(key):
                llm_basics[key] = existing_basics[key]

        llm_profile_json["basics"] = llm_basics

        # Preserve recruiter metadata
        for key in ("source", "sourced_by_user_id"):
            if existing.get(key):
                llm_profile_json[key] = existing[key]

        cp.profile_json = llm_profile_json
        cp.llm_parse_status = "succeeded"
        session.commit()

        logger.info(
            "LLM reparse succeeded for profile %d (skills: %d, experience: %d)",
            candidate_profile_id,
            len(llm_profile_json.get("skills", [])),
            len(llm_profile_json.get("experience", [])),
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
