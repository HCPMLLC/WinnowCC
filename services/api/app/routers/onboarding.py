from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.user import User
from app.schemas.onboarding import CandidateResponse, CandidateUpsertRequest
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/me", response_model=CandidateResponse)
def get_candidate_profile(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateResponse:
    record = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding not found.")
    return CandidateResponse.model_validate(record)


@router.post("/complete", response_model=CandidateResponse)
def complete_onboarding(
    payload: CandidateUpsertRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateResponse:
    # Required consents for onboarding (billing consents are NOT required here)
    if not payload.consent_terms:
        raise HTTPException(status_code=400, detail="Terms consent is required.")
    if not payload.consent_privacy:
        raise HTTPException(status_code=400, detail="Privacy consent is required.")

    record = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()

    data = payload.model_dump()
    data["desired_job_types"] = data.get("desired_job_types") or []
    data["desired_locations"] = data.get("desired_locations") or []
    data["communication_channels"] = data.get("communication_channels") or []

    if record is None:
        record = Candidate(user_id=user.id, **data)
        session.add(record)
    else:
        for field, value in data.items():
            setattr(record, field, value)

    user.onboarding_completed_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(record)

    return CandidateResponse.model_validate(record)
