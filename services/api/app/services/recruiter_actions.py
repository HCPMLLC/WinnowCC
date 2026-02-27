"""Recruiter action queue — prioritized daily to-do list."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.distribution import JobDistribution
from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)


def generate_daily_actions(
    employer_id: int,
    session: Session,
) -> list[dict]:
    """Generate a prioritized action queue for today.

    Priority 1 = most urgent, 5 = informational.
    """
    actions: list[dict] = []

    actions.extend(_check_pending_responses(employer_id, session))
    actions.extend(_check_underperforming_jobs(employer_id, session))
    actions.extend(_check_distribution_errors(employer_id, session))
    actions.extend(_check_expiring_jobs(employer_id, session))

    # Sort by priority (lower = more urgent)
    actions.sort(key=lambda a: a["priority"])
    return actions


def _check_pending_responses(employer_id: int, session: Session) -> list[dict]:
    """Find candidates awaiting response for 48+ hours."""
    from app.models.match import Match

    cutoff = datetime.now(UTC) - timedelta(hours=48)

    stmt = (
        select(func.count())
        .select_from(Match)
        .join(
            EmployerJob,
            Match.job_id == EmployerJob.id,
        )
        .where(
            EmployerJob.employer_id == employer_id,
            Match.application_status == "applied",
            Match.applied_at < cutoff,
        )
    )

    try:
        count = session.execute(stmt).scalar() or 0
    except Exception:
        count = 0

    if count > 0:
        return [
            {
                "priority": 1,
                "type": "pending_responses",
                "title": f"{count} candidates awaiting response",
                "description": (
                    f"{count} candidates have been waiting 48+ hours "
                    "for a status update on their applications."
                ),
                "action_url": "/employer/candidates",
                "due_by": datetime.now(UTC).isoformat(),
            }
        ]
    return []


def _check_underperforming_jobs(employer_id: int, session: Session) -> list[dict]:
    """Find active jobs with below-average application rates."""
    # Get active jobs with their distribution metrics
    stmt = (
        select(
            EmployerJob.id,
            EmployerJob.title,
            func.sum(JobDistribution.applications).label("apps"),
            func.sum(JobDistribution.impressions).label("impr"),
        )
        .outerjoin(
            JobDistribution,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(
            EmployerJob.employer_id == employer_id,
            EmployerJob.status == "active",
        )
        .group_by(EmployerJob.id, EmployerJob.title)
    )

    try:
        rows = session.execute(stmt).all()
    except Exception:
        return []

    if not rows:
        return []

    # Compute average
    app_counts = [int(r.apps or 0) for r in rows]
    if not app_counts:
        return []
    avg_apps = sum(app_counts) / len(app_counts) if app_counts else 0

    actions = []
    for row in rows:
        apps = int(row.apps or 0)
        impr = int(row.impr or 0)
        if apps < avg_apps * 0.5 and impr > 100:
            actions.append(
                {
                    "priority": 3,
                    "type": "underperforming_job",
                    "title": f'"{row.title}" is underperforming',
                    "description": (
                        f"This job has {impr} impressions but only "
                        f"{apps} applications. Consider optimizing "
                        "the posting content."
                    ),
                    "action_url": f"/employer/jobs/{row.id}",
                    "due_by": None,
                }
            )

    return actions


def _check_distribution_errors(employer_id: int, session: Session) -> list[dict]:
    """Find distributions with errors needing attention."""
    stmt = (
        select(func.count())
        .select_from(JobDistribution)
        .join(
            EmployerJob,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(
            EmployerJob.employer_id == employer_id,
            JobDistribution.status == "failed",
        )
    )

    try:
        count = session.execute(stmt).scalar() or 0
    except Exception:
        count = 0

    if count > 0:
        return [
            {
                "priority": 2,
                "type": "distribution_errors",
                "title": f"{count} distribution errors",
                "description": (
                    f"{count} job distribution(s) have failed. "
                    "Review and retry from the connections page."
                ),
                "action_url": "/employer/connections",
                "due_by": None,
            }
        ]
    return []


def _check_expiring_jobs(employer_id: int, session: Session) -> list[dict]:
    """Find jobs expiring within 7 days."""
    cutoff = datetime.now(UTC) + timedelta(days=7)

    stmt = select(EmployerJob).where(
        EmployerJob.employer_id == employer_id,
        EmployerJob.status == "active",
        EmployerJob.close_date.isnot(None),
        EmployerJob.close_date <= cutoff.date(),
    )

    try:
        jobs = list(session.execute(stmt).scalars().all())
    except Exception:
        return []

    actions = []
    for job in jobs:
        days_left = (job.close_date - datetime.now(UTC).date()).days
        actions.append(
            {
                "priority": 2 if days_left <= 2 else 4,
                "type": "expiring_job",
                "title": f'"{job.title}" expires in {days_left} days',
                "description": (
                    f"This job closes on {job.close_date}. "
                    "Extend or close it as needed."
                ),
                "action_url": f"/employer/jobs/{job.id}",
                "due_by": job.close_date.isoformat(),
            }
        )

    return actions


# ---------------------------------------------------------------------------
# Recruiter-specific action queue
# ---------------------------------------------------------------------------


def generate_recruiter_actions(
    recruiter_profile_id: int,
    session: Session,
) -> list[dict]:
    """Generate a prioritized action queue for a recruiter."""
    actions: list[dict] = []

    actions.extend(_check_stale_pipeline(recruiter_profile_id, session))
    actions.extend(_check_draft_jobs(recruiter_profile_id, session))
    actions.extend(_check_idle_clients(recruiter_profile_id, session))

    actions.sort(key=lambda a: a["priority"])
    return actions


def _check_stale_pipeline(recruiter_profile_id: int, session: Session) -> list[dict]:
    """Find pipeline candidates stuck in a stage for 7+ days."""
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

    cutoff = datetime.now(UTC) - timedelta(days=7)

    try:
        count = (
            session.execute(
                select(func.count())
                .select_from(RecruiterPipelineCandidate)
                .where(
                    RecruiterPipelineCandidate.recruiter_profile_id
                    == recruiter_profile_id,
                    RecruiterPipelineCandidate.stage.in_(
                        ["contacted", "screening", "interviewing"]
                    ),
                    RecruiterPipelineCandidate.updated_at < cutoff,
                )
            ).scalar()
            or 0
        )
    except Exception:
        count = 0

    if count > 0:
        return [
            {
                "priority": 1,
                "type": "stale_pipeline",
                "title": f"{count} candidates need follow-up",
                "description": (
                    f"{count} pipeline candidates haven't been updated in 7+ days. "
                    "Advance or remove them to keep your pipeline healthy."
                ),
                "action_url": "/recruiter/pipeline",
                "due_by": datetime.now(UTC).isoformat(),
            }
        ]
    return []


def _check_draft_jobs(recruiter_profile_id: int, session: Session) -> list[dict]:
    """Find draft jobs that haven't been published."""
    from app.models.recruiter_job import RecruiterJob as RJ

    try:
        count = (
            session.execute(
                select(func.count())
                .select_from(RJ)
                .where(
                    RJ.recruiter_profile_id == recruiter_profile_id,
                    RJ.status == "draft",
                )
            ).scalar()
            or 0
        )
    except Exception:
        count = 0

    if count > 0:
        return [
            {
                "priority": 3,
                "type": "draft_jobs",
                "title": f"{count} draft job(s) ready to publish",
                "description": (
                    f"You have {count} unpublished job(s). "
                    "Activate them to start matching candidates."
                ),
                "action_url": "/recruiter/jobs",
                "due_by": None,
            }
        ]
    return []


def _check_idle_clients(recruiter_profile_id: int, session: Session) -> list[dict]:
    """Find active clients with no recent activity."""
    from app.models.recruiter_activity import RecruiterActivity
    from app.models.recruiter_client import RecruiterClient

    cutoff = datetime.now(UTC) - timedelta(days=14)

    try:
        # Active clients with no activity in 14 days
        active_clients = (
            session.execute(
                select(func.count())
                .select_from(RecruiterClient)
                .where(
                    RecruiterClient.recruiter_profile_id == recruiter_profile_id,
                    RecruiterClient.status == "active",
                )
            ).scalar()
            or 0
        )

        if active_clients == 0:
            return []

        recent_client_activity = (
            session.execute(
                select(func.count())
                .select_from(RecruiterActivity)
                .where(
                    RecruiterActivity.recruiter_profile_id == recruiter_profile_id,
                    RecruiterActivity.client_id.isnot(None),
                    RecruiterActivity.created_at > cutoff,
                )
            ).scalar()
            or 0
        )

        if recent_client_activity == 0 and active_clients > 0:
            return [
                {
                    "priority": 2,
                    "type": "idle_clients",
                    "title": "No client activity in 14 days",
                    "description": (
                        f"You have {active_clients} active client(s) but no "
                        "logged activity in the last 2 weeks. Touch base to "
                        "maintain relationships."
                    ),
                    "action_url": "/recruiter/clients",
                    "due_by": None,
                }
            ]
    except Exception:
        pass

    return []
