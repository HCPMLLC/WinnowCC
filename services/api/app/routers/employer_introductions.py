"""Employer introduction request endpoints."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.employer import EmployerProfile
from app.services.auth import get_employer_profile
from app.services.billing import get_employer_limit, get_employer_tier

router = APIRouter(
    prefix="/api/employer/introductions",
    tags=["employer-introductions"],
)


class EmployerIntroductionCreate(BaseModel):
    candidate_profile_id: int
    employer_job_id: int | None = None
    message: str = Field(..., min_length=20, max_length=1000)


@router.post("")
def send_introduction(
    payload: EmployerIntroductionCreate,
    profile: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Send an introduction request to a candidate."""
    from app.services.employer_introductions import create_employer_introduction

    intro = create_employer_introduction(
        session=session,
        employer_profile=profile,
        candidate_profile_id=payload.candidate_profile_id,
        message=payload.message,
        employer_job_id=payload.employer_job_id,
    )
    session.commit()
    return {
        "id": intro.id,
        "status": intro.status,
        "created_at": intro.created_at.isoformat() if intro.created_at else None,
        "expires_at": intro.expires_at.isoformat() if intro.expires_at else None,
    }


@router.get("")
def list_introductions(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    profile: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """List sent introduction requests."""
    from app.services.employer_introductions import get_employer_introductions

    return get_employer_introductions(
        session=session,
        employer_profile_id=profile.id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.get("/usage")
def get_introduction_usage(
    profile: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),  # noqa: ARG001
):
    """Get current usage vs monthly limit for introduction requests."""
    tier = get_employer_tier(profile)
    limit = get_employer_limit(tier, "intro_requests_per_month")
    return {
        "used": profile.intro_requests_used or 0,
        "limit": limit,
        "tier": tier,
    }


@router.get("/{intro_id}")
def get_introduction(
    intro_id: int,
    profile: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """Get a single introduction request detail."""
    from app.services.employer_introductions import get_employer_introduction_detail

    return get_employer_introduction_detail(
        session=session,
        employer_profile_id=profile.id,
        intro_id=intro_id,
    )
