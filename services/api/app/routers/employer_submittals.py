"""Employer submittal package endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.employer import EmployerJob, EmployerProfile
from app.models.employer_submittal_package import EmployerSubmittalPackage
from app.schemas.employer import (
    EmployerSubmittalPackageCreate,
    EmployerSubmittalPackageResponse,
)
from app.services.auth import get_employer_profile
from app.services.queue import get_queue

router = APIRouter(prefix="/api/employer", tags=["employer-submittals"])


def _verify_job_ownership(
    session: Session, employer: EmployerProfile, job_id: int
) -> EmployerJob:
    """Verify the employer owns the job; raise 404 otherwise."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    return job


@router.post(
    "/jobs/{job_id}/submittals",
    response_model=EmployerSubmittalPackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submittal_package(
    job_id: int,
    data: EmployerSubmittalPackageCreate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerSubmittalPackageResponse:
    """Create a submittal package and enqueue PDF build."""
    job = _verify_job_ownership(session, employer, job_id)

    pkg = EmployerSubmittalPackage(
        employer_profile_id=employer.id,
        employer_job_id=job.id,
        recipient_name=data.recipient_name,
        recipient_email=data.recipient_email,
        recipient_company=data.recipient_company,
        candidate_profile_ids=data.candidate_profile_ids,
        filled_form_ids=data.filled_form_ids,
        package_options=data.package_options,
        cover_email_subject=data.cover_email_subject,
        cover_email_body=data.cover_email_body,
        status="building",
    )
    session.add(pkg)
    session.commit()
    session.refresh(pkg)

    # Enqueue build task
    from app.services.employer_submittal import (
        build_employer_submittal_package_task,
    )

    q = get_queue("default")
    q.safe_enqueue(build_employer_submittal_package_task, pkg.id)

    return EmployerSubmittalPackageResponse(
        id=pkg.id,
        employer_profile_id=pkg.employer_profile_id,
        employer_job_id=pkg.employer_job_id,
        recipient_name=pkg.recipient_name,
        recipient_email=pkg.recipient_email,
        recipient_company=pkg.recipient_company,
        candidate_profile_ids=pkg.candidate_profile_ids,
        filled_form_ids=pkg.filled_form_ids,
        package_options=pkg.package_options,
        status=pkg.status,
        candidate_count=len(pkg.candidate_profile_ids or []),
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
    )


@router.get(
    "/jobs/{job_id}/submittals",
    response_model=list[EmployerSubmittalPackageResponse],
)
def list_submittal_packages(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[EmployerSubmittalPackageResponse]:
    """List submittal packages for an employer job."""
    _verify_job_ownership(session, employer, job_id)

    packages = list(
        session.execute(
            select(EmployerSubmittalPackage)
            .where(
                EmployerSubmittalPackage.employer_profile_id == employer.id,
                EmployerSubmittalPackage.employer_job_id == job_id,
            )
            .order_by(EmployerSubmittalPackage.created_at.desc())
        )
        .scalars()
        .all()
    )

    return [
        EmployerSubmittalPackageResponse(
            id=p.id,
            employer_profile_id=p.employer_profile_id,
            employer_job_id=p.employer_job_id,
            recipient_name=p.recipient_name,
            recipient_email=p.recipient_email,
            recipient_company=p.recipient_company,
            candidate_profile_ids=p.candidate_profile_ids,
            filled_form_ids=p.filled_form_ids,
            package_options=p.package_options,
            merged_pdf_url=p.merged_pdf_url,
            cover_email_subject=p.cover_email_subject,
            cover_email_body=p.cover_email_body,
            status=p.status,
            error_message=p.error_message,
            sent_at=p.sent_at,
            candidate_count=len(p.candidate_profile_ids or []),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in packages
    ]


@router.get(
    "/jobs/{job_id}/submittals/{package_id}",
    response_model=EmployerSubmittalPackageResponse,
)
def get_submittal_package(
    job_id: int,
    package_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerSubmittalPackageResponse:
    """Get submittal package status/detail."""
    _verify_job_ownership(session, employer, job_id)

    pkg = session.execute(
        select(EmployerSubmittalPackage).where(
            EmployerSubmittalPackage.id == package_id,
            EmployerSubmittalPackage.employer_profile_id == employer.id,
            EmployerSubmittalPackage.employer_job_id == job_id,
        )
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submittal package not found.",
        )

    return EmployerSubmittalPackageResponse(
        id=pkg.id,
        employer_profile_id=pkg.employer_profile_id,
        employer_job_id=pkg.employer_job_id,
        recipient_name=pkg.recipient_name,
        recipient_email=pkg.recipient_email,
        recipient_company=pkg.recipient_company,
        candidate_profile_ids=pkg.candidate_profile_ids,
        filled_form_ids=pkg.filled_form_ids,
        package_options=pkg.package_options,
        merged_pdf_url=pkg.merged_pdf_url,
        cover_email_subject=pkg.cover_email_subject,
        cover_email_body=pkg.cover_email_body,
        status=pkg.status,
        error_message=pkg.error_message,
        sent_at=pkg.sent_at,
        candidate_count=len(pkg.candidate_profile_ids or []),
        created_at=pkg.created_at,
        updated_at=pkg.updated_at,
    )


@router.post("/jobs/{job_id}/submittals/{package_id}/send")
def send_submittal_package(
    job_id: int,
    package_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Send a ready submittal package via email."""
    _verify_job_ownership(session, employer, job_id)

    pkg = session.execute(
        select(EmployerSubmittalPackage).where(
            EmployerSubmittalPackage.id == package_id,
            EmployerSubmittalPackage.employer_profile_id == employer.id,
            EmployerSubmittalPackage.employer_job_id == job_id,
        )
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submittal package not found.",
        )

    if pkg.status not in ("ready", "sent"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Package is not ready (status={pkg.status}).",
        )

    from app.services.employer_submittal import send_employer_submittal_email

    result = send_employer_submittal_email(session, package_id)
    return result
