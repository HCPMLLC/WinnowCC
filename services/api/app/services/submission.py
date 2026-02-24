"""Candidate submission service for cross-segment visibility.

Handles submitting candidates to jobs, duplicate checking, and queries
for employer/recruiter/candidate views.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_submission import CandidateSubmission
from app.models.recruiter_job import RecruiterJob

logger = logging.getLogger(__name__)


def submit_candidate(
    session: Session,
    recruiter_profile_id: int,
    recruiter_job_id: int,
    candidate_profile_id: int,
    pipeline_candidate_id: int | None = None,
) -> tuple[CandidateSubmission, bool]:
    """Submit a candidate to a job.

    Works for both platform and external employers.
    Returns (submission, is_first_submission).
    """
    recruiter_job = session.get(RecruiterJob, recruiter_job_id)
    if not recruiter_job:
        raise ValueError("Recruiter job not found")

    employer_job_id = recruiter_job.employer_job_id

    # Check for duplicate by this recruiter
    own_existing = session.execute(
        select(CandidateSubmission).where(
            CandidateSubmission.recruiter_job_id == recruiter_job_id,
            CandidateSubmission.candidate_profile_id == candidate_profile_id,
        )
    ).scalar_one_or_none()
    if own_existing:
        raise ValueError("You already submitted this candidate for this job")

    # Cross-vendor first-submission check (only for platform employers)
    is_first = True
    if employer_job_id:
        existing = session.execute(
            select(CandidateSubmission).where(
                CandidateSubmission.employer_job_id == employer_job_id,
                CandidateSubmission.candidate_profile_id == candidate_profile_id,
            )
        ).scalar_one_or_none()
        is_first = existing is None

    submission = CandidateSubmission(
        employer_job_id=employer_job_id,
        recruiter_job_id=recruiter_job_id,
        candidate_profile_id=candidate_profile_id,
        recruiter_profile_id=recruiter_profile_id,
        pipeline_candidate_id=pipeline_candidate_id,
        is_first_submission=is_first,
        external_company_name=(
            recruiter_job.client_company_name if not employer_job_id else None
        ),
        external_job_title=recruiter_job.title if not employer_job_id else None,
        external_job_id=(
            recruiter_job.job_id_external if not employer_job_id else None
        ),
    )
    session.add(submission)
    session.flush()

    return submission, is_first


def check_candidate_submitted(
    session: Session,
    employer_job_id: int | None,
    candidate_profile_id: int,
) -> list[CandidateSubmission]:
    """Check if a candidate has been submitted to a platform job by any recruiter."""
    if not employer_job_id:
        return []
    return list(
        session.execute(
            select(CandidateSubmission)
            .where(
                CandidateSubmission.employer_job_id == employer_job_id,
                CandidateSubmission.candidate_profile_id == candidate_profile_id,
            )
            .order_by(CandidateSubmission.submitted_at)
        )
        .scalars()
        .all()
    )


def check_own_submissions(
    session: Session,
    recruiter_profile_id: int,
    recruiter_job_id: int,
    candidate_profile_id: int,
) -> list[CandidateSubmission]:
    """Check if this recruiter already submitted a candidate to this job (own only)."""
    return list(
        session.execute(
            select(CandidateSubmission)
            .where(
                CandidateSubmission.recruiter_profile_id == recruiter_profile_id,
                CandidateSubmission.recruiter_job_id == recruiter_job_id,
                CandidateSubmission.candidate_profile_id == candidate_profile_id,
            )
            .order_by(CandidateSubmission.submitted_at)
        )
        .scalars()
        .all()
    )


def get_submissions_for_employer_job(
    session: Session,
    employer_job_id: int,
) -> list[CandidateSubmission]:
    """Get all submissions for an employer job (employer view)."""
    return list(
        session.execute(
            select(CandidateSubmission)
            .where(CandidateSubmission.employer_job_id == employer_job_id)
            .order_by(CandidateSubmission.submitted_at)
        )
        .scalars()
        .all()
    )


def get_submissions_by_recruiter(
    session: Session,
    recruiter_profile_id: int,
    recruiter_job_id: int | None = None,
) -> list[CandidateSubmission]:
    """Get all submissions by a recruiter, optionally filtered by job."""
    stmt = select(CandidateSubmission).where(
        CandidateSubmission.recruiter_profile_id == recruiter_profile_id,
    )
    if recruiter_job_id:
        stmt = stmt.where(
            CandidateSubmission.recruiter_job_id == recruiter_job_id,
        )
    return list(
        session.execute(stmt.order_by(CandidateSubmission.submitted_at.desc()))
        .scalars()
        .all()
    )


def get_candidate_submissions(
    session: Session,
    candidate_profile_id: int,
) -> list[CandidateSubmission]:
    """Get all submissions for a candidate (candidate view)."""
    return list(
        session.execute(
            select(CandidateSubmission)
            .where(
                CandidateSubmission.candidate_profile_id == candidate_profile_id,
            )
            .order_by(CandidateSubmission.submitted_at.desc())
        )
        .scalars()
        .all()
    )
