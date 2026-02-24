"""Cross-segment job linking service.

Auto-links RecruiterJob to EmployerJob via matching job_id_external.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employer import EmployerJob
from app.models.recruiter_job import RecruiterJob

logger = logging.getLogger(__name__)


def auto_link_recruiter_job(
    session: Session, recruiter_job: RecruiterJob
) -> EmployerJob | None:
    """Find and link matching employer job by job_id_external.

    Returns the matched EmployerJob if found, None otherwise.
    """
    if not recruiter_job.job_id_external:
        return None

    employer_job = session.execute(
        select(EmployerJob).where(
            EmployerJob.job_id_external == recruiter_job.job_id_external,
            EmployerJob.status.in_(["active", "draft"]),
        )
    ).scalar_one_or_none()

    if employer_job:
        recruiter_job.employer_job_id = employer_job.id
        logger.info(
            "Auto-linked recruiter_job %s to employer_job %s via job_id_external=%s",
            recruiter_job.id,
            employer_job.id,
            recruiter_job.job_id_external,
        )

    return employer_job


def manual_link_recruiter_job(
    session: Session,
    recruiter_job: RecruiterJob,
    employer_job_id: int | None,
) -> None:
    """Manually link or unlink a recruiter job to an employer job."""
    if employer_job_id is not None:
        employer_job = session.get(EmployerJob, employer_job_id)
        if not employer_job:
            raise ValueError(f"Employer job {employer_job_id} not found")
    recruiter_job.employer_job_id = employer_job_id
