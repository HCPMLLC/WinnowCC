"""Outreach sequence router — automated multi-step email campaigns for recruiters."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.recruiter import RecruiterProfile
from app.schemas.outreach import (
    EnrollCandidatesRequest,
    OutreachEnrollmentResponse,
    OutreachSequenceCreate,
    OutreachSequenceResponse,
    OutreachSequenceUpdate,
    UnenrollRequest,
)
from app.services.auth import get_recruiter_profile
from app.services.outreach import (
    create_sequence,
    delete_sequence,
    enroll_candidates,
    get_sequence,
    list_enrollments,
    list_sequences,
    unenroll,
    update_sequence,
)

router = APIRouter(
    prefix="/api/recruiter/sequences",
    tags=["recruiter-outreach"],
)
logger = logging.getLogger(__name__)


@router.post("", response_model=OutreachSequenceResponse)
def create_outreach_sequence(
    data: OutreachSequenceCreate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Create a new outreach sequence."""
    seq = create_sequence(db, profile, data)
    db.commit()
    db.refresh(seq)
    return OutreachSequenceResponse(
        id=seq.id,
        recruiter_profile_id=seq.recruiter_profile_id,
        recruiter_job_id=seq.recruiter_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        enrolled_count=0,
        sent_count=0,
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.get("", response_model=list[OutreachSequenceResponse])
def list_outreach_sequences(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """List all outreach sequences for the recruiter."""
    return list_sequences(db, profile)


@router.get("/{sequence_id}", response_model=OutreachSequenceResponse)
def get_outreach_sequence(
    sequence_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Get a single outreach sequence."""
    seq = get_sequence(db, profile, sequence_id)
    return OutreachSequenceResponse(
        id=seq.id,
        recruiter_profile_id=seq.recruiter_profile_id,
        recruiter_job_id=seq.recruiter_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.patch("/{sequence_id}", response_model=OutreachSequenceResponse)
def update_outreach_sequence(
    sequence_id: int,
    data: OutreachSequenceUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Update an outreach sequence."""
    seq = update_sequence(db, profile, sequence_id, data)
    db.commit()
    db.refresh(seq)
    return OutreachSequenceResponse(
        id=seq.id,
        recruiter_profile_id=seq.recruiter_profile_id,
        recruiter_job_id=seq.recruiter_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.delete("/{sequence_id}", status_code=204)
def delete_outreach_sequence(
    sequence_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Delete an outreach sequence."""
    delete_sequence(db, profile, sequence_id)
    db.commit()


@router.post("/{sequence_id}/enroll")
def enroll_in_sequence(
    sequence_id: int,
    data: EnrollCandidatesRequest,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Enroll pipeline candidates in a sequence."""
    result = enroll_candidates(db, profile, sequence_id, data.pipeline_candidate_ids)
    db.commit()
    return result


@router.post("/{sequence_id}/unenroll")
def unenroll_from_sequence(
    sequence_id: int,
    data: UnenrollRequest,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Unenroll candidates from a sequence."""
    result = unenroll(db, profile, data.enrollment_ids)
    db.commit()
    return result


@router.get("/{sequence_id}/enrollments", response_model=list[OutreachEnrollmentResponse])
def get_enrollments(
    sequence_id: int,
    status: Optional[str] = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """List enrollments for a sequence."""
    return list_enrollments(db, profile, sequence_id, status_filter=status)
