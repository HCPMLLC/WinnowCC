"""Candidate-facing career intelligence endpoints (Pro tier only)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.services.auth import get_current_user, require_onboarded_user
from app.services.billing import check_feature_access, get_plan_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _require_career_intelligence(user: User, session: Session) -> str:
    """Return the tier if career intelligence is accessible, else raise 403."""
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    if not check_feature_access(tier, "career_intelligence"):
        raise HTTPException(
            status_code=403,
            detail="Career intelligence requires a Pro plan.",
        )
    return tier


def _latest_profile(session: Session, user_id: int) -> CandidateProfile:
    profile = (
        session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.get("/salary-roles")
def salary_roles() -> list[str]:
    """Return searchable role titles for salary autocomplete (no auth)."""
    from app.services.salary_reference import get_supported_roles

    return get_supported_roles()


@router.get(
    "/market-position/{job_id}",
    dependencies=[Depends(require_onboarded_user)],
)
def market_position(
    job_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Candidate's percentile position among all matches for a specific job."""
    _require_career_intelligence(user, session)
    profile = _latest_profile(session, user.id)

    from app.services.career_intelligence import compute_market_position

    return compute_market_position(
        candidate_profile_id=profile.id,
        employer_job_id=job_id,
        db=session,
    )


@router.get(
    "/salary",
    dependencies=[Depends(require_onboarded_user)],
)
def salary_insights(
    role: str,
    location: str | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Salary percentiles for a role/location from jobs data."""
    _require_career_intelligence(user, session)

    from app.services.career_intelligence import salary_intelligence

    return salary_intelligence(
        role_title=role,
        location=location,
        db=session,
    )


@router.get(
    "/career-trajectory",
    dependencies=[Depends(require_onboarded_user)],
)
def career_trajectory(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """AI-predicted career trajectory based on candidate profile."""
    _require_career_intelligence(user, session)
    profile = _latest_profile(session, user.id)

    from app.services.career_intelligence import predict_career_trajectory

    return predict_career_trajectory(
        candidate_profile_id=profile.id,
        db=session,
    )
