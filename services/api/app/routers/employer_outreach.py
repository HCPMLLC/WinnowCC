"""Employer outreach sequence endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse

from app.db.session import get_session
from app.models.employer import EmployerProfile
from app.models.employer_outreach import EmployerOutreachEnrollment
from app.schemas.employer import (
    EmployerOutreachEnrollmentResponse,
    EmployerOutreachEnrollRequest,
    EmployerOutreachSequenceCreate,
    EmployerOutreachSequenceResponse,
    EmployerOutreachSequenceUpdate,
    EmployerOutreachUnenrollRequest,
)
from app.services.auth import get_employer_profile
from app.services.employer_outreach import (
    create_sequence,
    delete_sequence,
    enroll_candidates,
    get_sequence,
    list_enrollments,
    list_sequences,
    unenroll,
    update_sequence,
)

router = APIRouter(prefix="/api/employer/outreach", tags=["employer-outreach"])
unsubscribe_router = APIRouter(tags=["employer-outreach-unsubscribe"])


# ---------------------------------------------------------------------------
# Sequence CRUD
# ---------------------------------------------------------------------------


@router.post("/sequences", response_model=EmployerOutreachSequenceResponse)
def create_outreach_sequence(
    data: EmployerOutreachSequenceCreate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerOutreachSequenceResponse:
    """Create a new employer outreach sequence."""
    seq = create_sequence(session, employer, data)
    session.commit()
    return EmployerOutreachSequenceResponse(
        id=seq.id,
        employer_profile_id=seq.employer_profile_id,
        employer_job_id=seq.employer_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.get(
    "/sequences", response_model=list[EmployerOutreachSequenceResponse]
)
def list_outreach_sequences(
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[EmployerOutreachSequenceResponse]:
    """List all outreach sequences for the employer."""
    rows = list_sequences(session, employer)
    return [EmployerOutreachSequenceResponse(**r) for r in rows]


@router.get(
    "/sequences/{sequence_id}",
    response_model=EmployerOutreachSequenceResponse,
)
def get_outreach_sequence(
    sequence_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerOutreachSequenceResponse:
    """Get a single outreach sequence."""
    seq = get_sequence(session, employer, sequence_id)
    return EmployerOutreachSequenceResponse(
        id=seq.id,
        employer_profile_id=seq.employer_profile_id,
        employer_job_id=seq.employer_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.put(
    "/sequences/{sequence_id}",
    response_model=EmployerOutreachSequenceResponse,
)
def update_outreach_sequence(
    sequence_id: int,
    data: EmployerOutreachSequenceUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerOutreachSequenceResponse:
    """Update an outreach sequence."""
    seq = update_sequence(session, employer, sequence_id, data)
    session.commit()
    return EmployerOutreachSequenceResponse(
        id=seq.id,
        employer_profile_id=seq.employer_profile_id,
        employer_job_id=seq.employer_job_id,
        name=seq.name,
        description=seq.description,
        is_active=seq.is_active,
        steps=seq.steps or [],
        created_at=seq.created_at,
        updated_at=seq.updated_at,
    )


@router.delete("/sequences/{sequence_id}", status_code=204)
def delete_outreach_sequence(
    sequence_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> None:
    """Delete an outreach sequence."""
    delete_sequence(session, employer, sequence_id)
    session.commit()


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


@router.post("/sequences/{sequence_id}/enroll")
def enroll_in_sequence(
    sequence_id: int,
    data: EmployerOutreachEnrollRequest,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Enroll candidates in an outreach sequence."""
    result = enroll_candidates(
        session, employer, sequence_id, data.candidate_profile_ids
    )
    session.commit()
    return result


@router.post("/sequences/{sequence_id}/unenroll")
def unenroll_from_sequence(
    sequence_id: int,
    data: EmployerOutreachUnenrollRequest,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Unenroll candidates from an outreach sequence."""
    result = unenroll(session, employer, data.enrollment_ids)
    session.commit()
    return result


@router.get(
    "/sequences/{sequence_id}/enrollments",
    response_model=list[EmployerOutreachEnrollmentResponse],
)
def list_sequence_enrollments(
    sequence_id: int,
    status_filter: str | None = Query(None),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[EmployerOutreachEnrollmentResponse]:
    """List enrollments for a sequence."""
    rows = list_enrollments(session, employer, sequence_id, status_filter)
    return [EmployerOutreachEnrollmentResponse(**r) for r in rows]


# ---------------------------------------------------------------------------
# Public unsubscribe (CAN-SPAM compliance)
# ---------------------------------------------------------------------------


@unsubscribe_router.get(
    "/api/employer-outreach/{enrollment_id}/unsubscribe/{token}",
    response_class=HTMLResponse,
)
def employer_outreach_unsubscribe(
    enrollment_id: int,
    token: str,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """One-click unsubscribe from employer outreach."""
    enrollment = session.get(EmployerOutreachEnrollment, enrollment_id)
    if not enrollment or enrollment.unsubscribe_token != token:
        return HTMLResponse(
            "<html><body><h2>Invalid unsubscribe link.</h2></body></html>",
            status_code=400,
        )

    enrollment.status = "unenrolled"
    session.commit()

    return HTMLResponse(
        "<html><body>"
        "<h2>You have been unsubscribed.</h2>"
        "<p>You will no longer receive emails from this sequence.</p>"
        "</body></html>"
    )
