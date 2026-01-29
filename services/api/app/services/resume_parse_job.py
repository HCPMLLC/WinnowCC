from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job_run import JobRun
from app.models.resume_document import ResumeDocument
from app.services.profile_parser import extract_text, parse_profile_from_text
from app.services.trust_scoring import evaluate_trust_for_resume


def parse_resume_job(resume_document_id: int, job_run_id: int) -> None:
    session = get_session_factory()()
    try:
        _set_job_status(session, job_run_id, "running")
        resume = session.get(ResumeDocument, resume_document_id)
        if resume is None:
            _set_job_status(session, job_run_id, "failed", "Resume document not found.")
            return

        text = extract_text(Path(resume.path))
        if not text.strip():
            _set_job_status(session, job_run_id, "failed", "No text could be extracted.")
            return

        profile_json = parse_profile_from_text(text)
        next_version = _get_next_version(session, resume.user_id)

        profile = CandidateProfile(
            user_id=resume.user_id,
            resume_document_id=resume.id,
            version=next_version,
            profile_json=profile_json,
        )
        session.add(profile)
        session.commit()
        evaluate_trust_for_resume(
            session,
            resume,
            profile_json=profile_json,
            action="recompute_after_parse",
        )
        _set_job_status(session, job_run_id, "succeeded")
    except Exception as exc:
        session.rollback()
        _set_job_status(session, job_run_id, "failed", _safe_error_message(exc))
    finally:
        session.close()


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
