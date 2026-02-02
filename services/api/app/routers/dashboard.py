"""Dashboard metrics API.

Provides aggregated metrics for the user's job search dashboard.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.match import Match
from app.models.user import User
from app.services.auth import get_current_user, require_onboarded_user
from app.services.profile_parser import default_profile_json
from app.services.profile_scoring import compute_profile_completeness

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_onboarded_user)],
)


class DashboardMetricsResponse(BaseModel):
    """Dashboard metrics for the current user."""

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
    # Profile completeness
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

    # Qualified jobs count (total matches for user)
    qualified_jobs_count = session.execute(
        select(func.count(Match.id)).where(Match.user_id == user.id)
    ).scalar() or 0

    # Application status counts
    submitted_applications_count = session.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user.id, Match.application_status == "applied"
        )
    ).scalar() or 0

    interviews_requested_count = session.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user.id, Match.application_status == "interviewing"
        )
    ).scalar() or 0

    offers_received_count = session.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user.id, Match.application_status == "offer"
        )
    ).scalar() or 0

    return DashboardMetricsResponse(
        profile_completeness_score=profile_completeness_score,
        qualified_jobs_count=qualified_jobs_count,
        submitted_applications_count=submitted_applications_count,
        interviews_requested_count=interviews_requested_count,
        offers_received_count=offers_received_count,
    )
