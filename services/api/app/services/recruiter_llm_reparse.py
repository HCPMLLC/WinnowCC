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

        # Auto-trigger matching when all reparses for this recruiter are done
        _trigger_matching_if_all_done(session, cp.profile_json)

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


def _trigger_matching_if_all_done(session, profile_json: dict) -> None:
    """If no more pending/running reparses remain for this recruiter,
    enqueue job matching for all their active jobs."""
    try:
        from sqlalchemy import select, func

        from app.models.recruiter_job import RecruiterJob
        from app.services.job_pipeline import populate_recruiter_job_candidates
        from app.services.queue import get_queue

        sourced_by = profile_json.get("sourced_by_user_id")
        if not sourced_by:
            return

        # Count remaining pending/running reparses for this recruiter
        remaining = (
            session.execute(
                select(func.count(CandidateProfile.id)).where(
                    CandidateProfile.profile_json["sourced_by_user_id"].astext
                    == str(sourced_by),
                    CandidateProfile.llm_parse_status.in_(("pending", "running")),
                )
            ).scalar()
            or 0
        )

        if remaining > 0:
            return

        # Find the recruiter profile id from user_id
        from app.models.recruiter import RecruiterProfile

        rp = session.execute(
            select(RecruiterProfile.id).where(
                RecruiterProfile.user_id == int(sourced_by)
            )
        ).scalar_one_or_none()
        if not rp:
            return

        active_jobs = (
            session.execute(
                select(RecruiterJob.id).where(
                    RecruiterJob.recruiter_profile_id == rp,
                    RecruiterJob.status == "active",
                )
            )
            .scalars()
            .all()
        )

        if not active_jobs:
            return

        q = get_queue()
        for job_id in active_jobs:
            q.enqueue(populate_recruiter_job_candidates, job_id)

        logger.info(
            "All LLM reparses done for recruiter user %s — enqueued matching for %d jobs",
            sourced_by,
            len(active_jobs),
        )
    except Exception:
        logger.warning(
            "Failed to trigger post-enrichment matching", exc_info=True
        )
