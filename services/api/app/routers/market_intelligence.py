"""Market intelligence router (P54)."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/api/employer/intelligence",
    tags=["market-intelligence"],
)
logger = logging.getLogger(__name__)


def _require_employer(user=Depends(get_current_user)):
    if user.role not in ("employer", "both", "admin"):
        from fastapi import HTTPException

        raise HTTPException(403, "Employer role required")
    return user


def _get_employer_id(user, db: Session) -> int:
    from app.models.employer import EmployerProfile

    profile = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if not profile:
        from fastapi import HTTPException

        raise HTTPException(404, "Employer profile not found")
    return profile.id


@router.get("/salary")
def salary_benchmarks(
    title: str = Query(..., min_length=2),
    location: str | None = Query(None),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Get salary benchmarks for a role."""
    from app.services.market_intelligence import (
        get_salary_benchmarks,
    )

    return get_salary_benchmarks(title, location, db)


@router.get("/time-to-fill")
def time_to_fill(
    title: str = Query(..., min_length=2),
    location: str | None = Query(None),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Get time-to-fill benchmarks for a role."""
    from app.services.market_intelligence import (
        get_time_to_fill_benchmarks,
    )

    return get_time_to_fill_benchmarks(title, location, db)


@router.get("/competitive/{job_id}")
def competitive_landscape(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Get competitive landscape for a specific job."""
    from app.services.market_intelligence import (
        get_competitive_landscape,
    )

    employer_id = _get_employer_id(user, db)
    return get_competitive_landscape(employer_id, job_id, db)
