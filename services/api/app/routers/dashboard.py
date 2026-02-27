"""Dashboard metrics API.

Provides aggregated metrics for the user's job search dashboard.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.user import User
from app.services.auth import get_current_user, require_onboarded_user
from app.services.matching import MIN_MATCH_SCORE
from app.services.profile_parser import default_profile_json
from app.services.profile_scoring import compute_profile_completeness
from app.services.submission import get_candidate_submissions

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_onboarded_user)],
)


class DashboardMetricsResponse(BaseModel):
    """Dashboard metrics for the current user."""

    display_name: str | None = None
    profile_completeness_score: int
    qualified_jobs_count: int
    submitted_applications_count: int
    interviews_requested_count: int
    offers_received_count: int


@router.get("/metrics", response_model=DashboardMetricsResponse)
def get_dashboard_metrics(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DashboardMetricsResponse:
    """Get aggregated dashboard metrics for the current user.

    Returns:
        - profile_completeness_score: 0-100 percentage of profile completion
        - qualified_jobs_count: Number of job matches for the user
        - submitted_applications_count: Jobs where user marked status as 'applied'
        - interviews_requested_count: Jobs where user marked status as 'interviewing'
        - offers_received_count: Jobs where user marked status as 'offer'
    """
    # Profile completeness (queried first so we can use it for display_name fallback)
    profile_stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    profile = session.execute(profile_stmt).scalars().first()
    if profile is None:
        profile_json = default_profile_json()
    else:
        profile_json = profile.profile_json

    completeness = compute_profile_completeness(profile_json)
    profile_completeness_score = completeness.score

    # Display name: candidate record → parsed profile → email local part
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    display_name = None
    if candidate:
        parts = [candidate.first_name, candidate.last_name]
        name = " ".join(p for p in parts if p) or None
        # Reject email-like values that may have leaked into name fields
        if name and "@" not in name:
            display_name = name
    if not display_name:
        basics = (profile_json or {}).get("basics") or {}
        parts = [basics.get("first_name"), basics.get("last_name")]
        name = " ".join(p for p in parts if p) or None
        if name and "@" not in name:
            display_name = name
    if not display_name and user.email:
        display_name = user.email.split("@")[0]

    # Qualified jobs count (matches above minimum score with valid jobs)
    qualified_jobs_count = (
        session.execute(
            select(func.count(Match.id))
            .join(Job, Match.job_id == Job.id)
            .where(
                Match.user_id == user.id,
                Match.match_score >= MIN_MATCH_SCORE,
            )
        ).scalar()
        or 0
    )

    # Application status counts
    submitted_applications_count = (
        session.execute(
            select(func.count(Match.id)).where(
                Match.user_id == user.id, Match.application_status == "applied"
            )
        ).scalar()
        or 0
    )

    interviews_requested_count = (
        session.execute(
            select(func.count(Match.id)).where(
                Match.user_id == user.id, Match.application_status == "interviewing"
            )
        ).scalar()
        or 0
    )

    offers_received_count = (
        session.execute(
            select(func.count(Match.id)).where(
                Match.user_id == user.id, Match.application_status == "offer"
            )
        ).scalar()
        or 0
    )

    return DashboardMetricsResponse(
        display_name=display_name,
        profile_completeness_score=profile_completeness_score,
        qualified_jobs_count=qualified_jobs_count,
        submitted_applications_count=submitted_applications_count,
        interviews_requested_count=interviews_requested_count,
        offers_received_count=offers_received_count,
    )


class CandidateSubmissionItem(BaseModel):
    """A single submission visible to the candidate."""

    id: int
    job_title: str | None = None
    company_name: str | None = None
    recruiter_company_name: str | None = None
    submitted_at: datetime | None = None
    status: str


@router.get("/submissions", response_model=list[CandidateSubmissionItem])
def get_my_submissions(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[CandidateSubmissionItem]:
    """Get recruiter submissions where the current user is the candidate."""
    from app.services.billing import get_plan_tier, get_tier_limit

    # Find the latest candidate profile for this user
    profile = (
        session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not profile:
        return []

    # Determine detail level based on candidate tier
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    detail_level = get_tier_limit(tier, "submission_details")

    submissions = get_candidate_submissions(session, profile.id)
    items: list[CandidateSubmissionItem] = []
    for sub in submissions:
        # Resolve job title and company name
        if sub.employer_job_id and sub.employer_job:
            job_title = sub.employer_job.title
            company_name = (
                sub.employer_job.employer.company_name
                if sub.employer_job.employer
                else None
            )
        else:
            job_title = sub.external_job_title
            company_name = sub.external_company_name

        # Recruiter company visible at standard+ detail level
        recruiter_company = None
        if detail_level in ("standard", "full"):
            recruiter_company = (
                sub.recruiter_profile.company_name if sub.recruiter_profile else None
            )

        items.append(
            CandidateSubmissionItem(
                id=sub.id,
                job_title=job_title,
                company_name=company_name,
                recruiter_company_name=recruiter_company,
                submitted_at=sub.submitted_at,
                status=sub.status,
            )
        )
    return items
