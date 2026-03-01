"""Outreach sequence router — automated multi-step email campaigns for recruiters."""

import logging
import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.outreach_enrollment import OutreachEnrollment
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

# Separate router for public unsubscribe (no auth required)
unsubscribe_router = APIRouter(tags=["outreach-unsubscribe"])


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


@router.get(
    "/{sequence_id}/enrollments", response_model=list[OutreachEnrollmentResponse]
)
def get_enrollments(
    sequence_id: int,
    status: str | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """List enrollments for a sequence."""
    return list_enrollments(db, profile, sequence_id, status_filter=status)


# ---------------------------------------------------------------------------
# Public unsubscribe endpoint (no auth required — CAN-SPAM compliance)
# ---------------------------------------------------------------------------

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


@unsubscribe_router.get(
    "/api/outreach/{enrollment_id}/unsubscribe/{token}",
    response_class=HTMLResponse,
)
def unsubscribe_from_outreach(
    enrollment_id: int,
    token: str,
    db: Session = Depends(get_session),
):
    """One-click unsubscribe from an outreach sequence (CAN-SPAM)."""
    enrollment = db.execute(
        select(OutreachEnrollment).where(
            OutreachEnrollment.id == enrollment_id,
            OutreachEnrollment.unsubscribe_token == token,
        )
    ).scalar_one_or_none()

    if enrollment is None:
        return HTMLResponse(
            content=(
                "<html><body style='font-family:sans-serif;padding:40px;'>"
                "<h2>Invalid or expired link</h2>"
                "<p>This unsubscribe link is no longer valid.</p>"
                "</body></html>"
            ),
            status_code=404,
        )

    if enrollment.status not in ("unenrolled", "completed"):
        enrollment.status = "unenrolled"
        db.commit()

    return HTMLResponse(
        content=(
            "<html><body style='font-family:sans-serif;padding:40px;"
            "text-align:center;'>"
            "<h2>You have been unsubscribed</h2>"
            "<p>You will no longer receive emails from this sequence.</p>"
            "<p style='margin-top:24px;color:#666;font-size:14px;'>"
            "Powered by Winnow</p>"
            "</body></html>"
        ),
    )
