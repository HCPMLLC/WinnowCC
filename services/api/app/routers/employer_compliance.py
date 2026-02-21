"""Employer compliance router (P49)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.auth import get_current_user
from app.services.billing import get_employer_limit, get_employer_tier

router = APIRouter(
    prefix="/api/employer/compliance",
    tags=["employer-compliance"],
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


@router.get("/log")
def compliance_log(
    job_id: int | None = Query(None),
    event_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Paginated compliance audit log."""
    from app.services.employer_compliance import get_compliance_log

    employer_id = _get_employer_id(user, db)
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    return get_compliance_log(
        employer_id, job_id, event_type, sd, ed, limit, offset, db
    )


@router.get("/report/ofccp")
def ofccp_report(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Generate OFCCP-ready audit report."""
    from app.services.employer_compliance import generate_ofccp_report

    employer_id = _get_employer_id(user, db)
    sd = datetime.fromisoformat(start_date) if start_date else None
    ed = datetime.fromisoformat(end_date) if end_date else None
    return generate_ofccp_report(employer_id, sd, ed, db)


@router.get("/job/{job_id}/status")
def job_compliance_status(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Compliance checklist for a specific job."""
    from app.services.employer_compliance import (
        get_posting_compliance_status,
    )

    return get_posting_compliance_status(job_id, db)


@router.get("/dei-recommendations/{job_id}")
def dei_recommendations(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """DEI sourcing recommendations for a job."""
    from app.models.employer import EmployerProfile
    from app.services.dei_sourcing import (
        analyze_candidate_pool_diversity,
    )

    profile = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if not profile:
        raise HTTPException(404, "Employer profile not found")

    # Gate by bias_detection tier feature
    tier = get_employer_tier(profile)
    bias_level = get_employer_limit(tier, "bias_detection")
    if not bias_level:
        raise HTTPException(
            403,
            "DEI recommendations require Starter or Pro plan.",
        )

    return analyze_candidate_pool_diversity(profile.id, job_id, db)
