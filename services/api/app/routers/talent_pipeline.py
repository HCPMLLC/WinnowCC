"""Talent pipeline router (P50)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.auth import get_current_user

router = APIRouter(
    prefix="/api/employer/pipeline",
    tags=["talent-pipeline"],
)
logger = logging.getLogger(__name__)


def _require_employer(user=Depends(get_current_user)):
    if user.role not in ("employer", "both", "admin"):
        raise HTTPException(403, "Employer role required")
    return user


def _get_employer_id(user, db: Session) -> int:
    from app.models.employer import EmployerProfile

    profile = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if not profile:
        raise HTTPException(404, "Employer profile not found")
    return profile.id


class PipelineAddRequest(BaseModel):
    candidate_profile_id: int
    source_job_id: int | None = None
    status: str = "warm_lead"
    tags: list[str] | None = None
    notes: str | None = None


class PipelineUpdateRequest(BaseModel):
    pipeline_status: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    consent_given: bool | None = None


@router.get("")
def list_pipeline(
    status: str | None = Query(None),
    min_score: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """List pipeline candidates with filters."""
    from app.services.talent_pipeline import search_pipeline

    employer_id = _get_employer_id(user, db)
    filters = {}
    if status:
        filters["status"] = status
    if min_score is not None:
        filters["min_score"] = min_score
    return search_pipeline(employer_id, filters, limit, offset, db)


@router.post("")
def add_to_pipeline(
    body: PipelineAddRequest,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Add a candidate to the talent pipeline."""
    from app.services.talent_pipeline import add_to_pipeline as _add

    employer_id = _get_employer_id(user, db)
    result = _add(
        employer_id,
        body.candidate_profile_id,
        body.source_job_id,
        body.status,
        body.tags,
        body.notes,
        db,
    )
    db.commit()
    return result


@router.put("/{pipeline_id}")
def update_pipeline_entry(
    pipeline_id: int,
    body: PipelineUpdateRequest,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Update a pipeline entry's status, tags, or notes."""
    from app.services.talent_pipeline import (
        update_pipeline_entry as _update,
    )

    employer_id = _get_employer_id(user, db)
    updates = body.model_dump(exclude_unset=True)
    result = _update(pipeline_id, employer_id, updates, db)
    if not result:
        raise HTTPException(404, "Pipeline entry not found")
    db.commit()
    return result


@router.delete("/{pipeline_id}")
def remove_from_pipeline(
    pipeline_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Remove a candidate from the pipeline."""
    from app.services.talent_pipeline import (
        remove_from_pipeline as _remove,
    )

    employer_id = _get_employer_id(user, db)
    if not _remove(pipeline_id, employer_id, db):
        raise HTTPException(404, "Pipeline entry not found")
    db.commit()
    return {"status": "removed"}


@router.get("/suggestions/{job_id}")
def pipeline_suggestions(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Get pipeline candidates matching a new job."""
    from app.services.talent_pipeline import (
        suggest_pipeline_candidates,
    )

    employer_id = _get_employer_id(user, db)
    return suggest_pipeline_candidates(employer_id, job_id, db)


@router.post("/auto-add/{job_id}")
def auto_add_silver_medalists(
    job_id: int,
    user=Depends(_require_employer),
    db: Session = Depends(get_session),
):
    """Auto-add silver medalists from a filled job."""
    from app.services.talent_pipeline import (
        auto_add_silver_medalists as _auto_add,
    )

    employer_id = _get_employer_id(user, db)
    result = _auto_add(employer_id, job_id, db)
    db.commit()
    return result
