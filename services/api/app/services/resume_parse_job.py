from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job_run import JobRun
from app.models.resume_document import ResumeDocument
from app.services.profile_parser import extract_text, parse_profile_from_text
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
            text = extract_text(local_path)
        finally:
            if is_gcs_path(resume.path):
                local_path.unlink(missing_ok=True)
        if not text.strip():
            _set_job_status(
                session, job_run_id, "failed", "No text could be extracted."
            )
            return

        # Try LLM parser first (rich extraction), fall back to regex
        profile_json = None
        try:
            from app.services.llm_parser import is_llm_parser_available, parse_with_llm

            avail = is_llm_parser_available()
            if avail:
                logger.warning(
                    "LLM_PARSE: using LLM parser for resume %s", resume_document_id
                )
                profile_json = parse_with_llm(text)
                logger.warning("LLM_PARSE: succeeded for resume %s", resume_document_id)
            else:
                import os

                from app.services.llm_parser import PROMPT9_PATH

                logger.warning(
                    "LLM_PARSE: not available — "
                    "OPENAI_KEY=%s ANTHROPIC_KEY=%s PROMPT9=%s ENABLED=%s",
                    bool(os.getenv("OPENAI_API_KEY", "").strip()),
                    bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
                    PROMPT9_PATH.exists(),
                    os.getenv("LLM_PARSER_ENABLED", "true"),
                )
        except Exception as exc:
            logger.warning(
                "LLM_PARSE: failed — %s: %s",
                type(exc).__name__,
                exc,
            )

        if profile_json is None:
            logger.info("Using regex parser for resume %s", resume_document_id)
            profile_json = parse_profile_from_text(text)

        # Merge parsed data with existing profile to preserve manual edits
        profile_json = _merge_with_existing_profile(
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

            get_queue().enqueue(embed_profile, resume.user_id, next_version)
        except Exception:
            pass

        try:
            from app.services.job_pipeline import refresh_candidates_for_profile
            from app.services.queue import get_queue

            get_queue().enqueue(refresh_candidates_for_profile, resume.user_id)
        except Exception:
            pass

        try:
            from app.services.job_pipeline import ingest_jobs_job, match_jobs_job
            from app.services.queue import get_queue

            ingest_query = _build_ingest_query_from_profile(profile_json)
            queue = get_queue("critical")
            ingest_rq_job = queue.enqueue(ingest_jobs_job, ingest_query)
            queue.enqueue(
                match_jobs_job,
                resume.user_id,
                next_version,
                depends_on=ingest_rq_job,
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


def _merge_with_existing_profile(
    session: Session, user_id: int | None, parsed: dict
) -> dict:
    """Merge parsed resume data with the user's latest existing profile.

    - Overwrite from parse: experience, skills, education, certifications
    - Preserve from existing (if populated): basics fields, preferences,
      skill_years, llm_enrichment
    - Always update summary from parse (it comes from resume text)
    """
    if user_id is None:
        return parsed

    # Fetch the latest existing profile for this user
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    existing_profile = session.execute(stmt).scalar_one_or_none()
    if existing_profile is None:
        return parsed

    existing = existing_profile.profile_json or {}
    existing_basics = existing.get("basics") or {}
    parsed_basics = parsed.get("basics") or {}

    # For basics: keep existing values if they're populated; only fill blanks
    # from parsed data. Always take summary from parse.
    _BASICS_PRESERVE_KEYS = (
        "first_name",
        "last_name",
        "name",
        "email",
        "phone",
        "location",
        "work_authorization",
        "total_years_experience",
    )
    merged_basics = dict(parsed_basics)
    for key in _BASICS_PRESERVE_KEYS:
        existing_val = existing_basics.get(key)
        if existing_val:
            merged_basics[key] = existing_val

    # Always overwrite summary from parsed data (it comes from resume text)
    if parsed_basics.get("summary"):
        merged_basics["summary"] = parsed_basics["summary"]

    parsed["basics"] = merged_basics

    # Preserve preferences entirely from existing profile
    existing_prefs = existing.get("preferences")
    if existing_prefs:
        parsed["preferences"] = existing_prefs

    # Preserve skill_years if existing has it and parsed doesn't
    if existing.get("skill_years") and not parsed.get("skill_years"):
        parsed["skill_years"] = existing["skill_years"]

    # Preserve llm_enrichment if existing has it and parsed doesn't
    if existing.get("llm_enrichment") and not parsed.get("llm_enrichment"):
        parsed["llm_enrichment"] = existing["llm_enrichment"]

    return parsed


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
