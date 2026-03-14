from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job_run import JobRun
from app.models.resume_document import ResumeDocument
from app.services.resume_pipeline import (
    ParseOptions,
    extract_and_parse,
    merge_with_existing_profile,
)
from app.services.storage import download_to_tempfile, is_gcs_path
from app.services.trust_scoring import evaluate_trust_for_resume

logger = logging.getLogger(__name__)


def parse_resume_job(resume_document_id: int, job_run_id: int) -> None:
    session = get_session_factory()()
    try:
        _set_job_status(session, job_run_id, "running")
        resume = session.get(ResumeDocument, resume_document_id)
        if resume is None or resume.deleted_at is not None:
            _set_job_status(session, job_run_id, "failed", "Resume document not found.")
            return

        suffix = Path(resume.path).suffix if resume.path else ""
        local_path = download_to_tempfile(resume.path, suffix=suffix)
        try:
            result = extract_and_parse(
                local_path,
                ParseOptions(parser_strategy="llm_then_regex"),
            )
        except ValueError:
            _set_job_status(
                session, job_run_id, "failed", "No text could be extracted."
            )
            return
        finally:
            if is_gcs_path(resume.path):
                local_path.unlink(missing_ok=True)

        logger.info(
            "Resume %s parsed with %s parser",
            resume_document_id,
            result.parser_used,
        )
        profile_json = result.profile_json

        # Merge parsed data with existing profile to preserve manual edits
        profile_json = merge_with_existing_profile(
            session, resume.user_id, profile_json
        )

        next_version = _get_next_version(session, resume.user_id)

        profile = CandidateProfile(
            user_id=resume.user_id,
            resume_document_id=resume.id,
            version=next_version,
            profile_json=profile_json,
        )
        session.add(profile)
        session.commit()

        # Trust eval is best-effort — don't fail the job if it errors
        try:
            evaluate_trust_for_resume(
                session,
                resume,
                profile_json=profile_json,
                action="recompute_after_parse",
            )
        except Exception:
            session.rollback()

        # Enqueue post-parse jobs (embed, match, refresh) to match manual save behavior
        try:
            from app.services.job_pipeline import embed_profile
            from app.services.queue import get_queue

            get_queue().safe_enqueue(embed_profile, resume.user_id, next_version)
        except Exception:
            pass

        try:
            from app.services.job_pipeline import refresh_candidates_for_profile
            from app.services.queue import get_queue

            get_queue().safe_enqueue(refresh_candidates_for_profile, resume.user_id)
        except Exception:
            pass

        try:
            from app.services.job_pipeline import ingest_jobs_job, match_jobs_job
            from app.services.queue import get_queue

            ingest_query = _build_ingest_query_from_profile(profile_json)
            queue = get_queue("critical")
            ingest_rq_job = queue.enqueue(ingest_jobs_job, ingest_query, job_timeout="30m")
            queue.enqueue(
                match_jobs_job,
                resume.user_id,
                next_version,
                depends_on=ingest_rq_job,
            )
        except Exception:
            pass

        # Enqueue profile enhancement suggestions (low priority)
        try:
            from app.services.profile_enhancement import (
                generate_enhancement_suggestions,
            )
            from app.services.queue import get_queue

            get_queue("low").safe_enqueue(
                generate_enhancement_suggestions,
                resume.user_id,
                next_version,
            )
        except Exception:
            pass

        _set_job_status(session, job_run_id, "succeeded")
    except Exception as exc:
        session.rollback()
        _set_job_status(session, job_run_id, "failed", _safe_error_message(exc))
    finally:
        session.close()


def _build_ingest_query_from_profile(profile_json: dict) -> dict:
    """Build a job ingestion query from parsed profile data."""
    preferences = (
        profile_json.get("preferences", {}) if isinstance(profile_json, dict) else {}
    )
    search_terms = preferences.get("target_titles") or []
    search = search_terms[0] if search_terms else ""
    if not search:
        experience = (
            profile_json.get("experience", []) if isinstance(profile_json, dict) else []
        )
        if experience and isinstance(experience[0], dict):
            search = experience[0].get("title", "")

    locations = preferences.get("locations") or []
    location = locations[0] if locations else ""
    if not location:
        basics = (
            profile_json.get("basics", {}) if isinstance(profile_json, dict) else {}
        )
        location = basics.get("location", "") if isinstance(basics, dict) else ""

    return {"search": search, "location": location}


def _get_next_version(session: Session, user_id: int | None) -> int:
    if user_id is None:
        user_filter = CandidateProfile.user_id.is_(None)
    else:
        user_filter = CandidateProfile.user_id == user_id
    stmt = select(func.max(CandidateProfile.version)).where(user_filter)
    current = session.execute(stmt).scalar()
    return int(current or 0) + 1


def _set_job_status(
    session: Session, job_run_id: int, status: str, error_message: str | None = None
) -> None:
    job_run = session.get(JobRun, job_run_id)
    if job_run is None:
        return
    job_run.status = status
    job_run.error_message = error_message
    session.commit()


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        message = "Resume parsing failed."
    return message[:500]
