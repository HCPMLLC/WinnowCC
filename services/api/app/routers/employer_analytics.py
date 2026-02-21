"""Employer analytics router (P47)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.auth import get_current_user
from app.services.billing import get_employer_limit, get_employer_tier

router = APIRouter(
    prefix="/api/employer/analytics",
    tags=["employer-analytics"],
)
logger = logging.getLogger(__name__)


def _require_employer(user=Depends(get_current_user)):
    """Require the user to have employer role."""
    if user.role not in ("employer", "both", "admin"):
        raise HTTPException(403, "Employer role required")
    return user


def _get_employer_profile(user, db: Session):
    from app.models.employer import EmployerProfile

    profile = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if not profile:
        raise HTTPException(404, "Employer profile not found")
    return profile


def _require_cross_board_analytics(profile):
    """Raise 403 if cross_board_analytics is not available for this tier."""
    tier = get_employer_tier(profile)
    level = get_employer_limit(tier, "cross_board_analytics")
    if not level:
        raise HTTPException(
            403,
            "Cross-board analytics requires Starter or Pro plan.",
        )
    return level


@router.get("/overview")
def analytics_overview(
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Summary analytics for the employer dashboard."""
    from app.services.employer_analytics import get_overview

    profile = _get_employer_profile(user, db)
    return get_overview(profile.id, db)


@router.get("/funnel")
def analytics_funnel(
    job_id: int | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Funnel metrics by board."""
    from app.services.employer_analytics import get_funnel_by_board

    profile = _get_employer_profile(user, db)
    _require_cross_board_analytics(profile)
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    return get_funnel_by_board(profile.id, job_id, sd, ed, db)


@router.get("/cost")
def analytics_cost(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Cost-per-outcome breakdown."""
    from app.services.employer_analytics import get_cost_per_outcome

    profile = _get_employer_profile(user, db)
    _require_cross_board_analytics(profile)
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    return get_cost_per_outcome(profile.id, sd, ed, db)


@router.get("/recommendations")
def analytics_recommendations(
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Board recommendations based on historical performance."""
    from app.services.employer_analytics import (
        get_board_recommendations,
    )

    profile = _get_employer_profile(user, db)
    _require_cross_board_analytics(profile)
    return get_board_recommendations(profile.id, db)
