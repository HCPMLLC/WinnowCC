"""Admin employer management router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.employer import EmployerJob, EmployerProfile
from app.models.user import User
from app.schemas.admin_employers import (
    AdminEmployerJobResponse,
    AdminEmployerResponse,
    DeleteEmployersRequest,
    DeleteEmployersResponse,
    EmployerTierOverrideRequest,
    EmployerTierOverrideResponse,
)
from app.services.auth import require_admin_user
from app.services.cascade_delete import cascade_delete_user

router = APIRouter(prefix="/api/admin/employers", tags=["admin-employers"])


@router.get("", response_model=list[AdminEmployerResponse])
def list_employers(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminEmployerResponse]:
    """List all employers with profile data, job counts, and usage."""
    # Subquery: total jobs per employer
    total_jobs_sq = (
        select(
            EmployerJob.employer_id,
            func.count(EmployerJob.id).label("total"),
        )
        .group_by(EmployerJob.employer_id)
        .subquery()
    )

    # Subquery: active jobs per employer (status='active' and not archived)
    active_jobs_sq = (
        select(
            EmployerJob.employer_id,
            func.count(EmployerJob.id).label("active"),
        )
        .where(
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
        )
        .group_by(EmployerJob.employer_id)
        .subquery()
    )

    stmt = (
        select(
            EmployerProfile,
            User,
            func.coalesce(total_jobs_sq.c.total, 0).label("total_jobs"),
            func.coalesce(active_jobs_sq.c.active, 0).label("active_jobs"),
        )
        .join(User, EmployerProfile.user_id == User.id)
        .outerjoin(total_jobs_sq, EmployerProfile.id == total_jobs_sq.c.employer_id)
        .outerjoin(active_jobs_sq, EmployerProfile.id == active_jobs_sq.c.employer_id)
        .order_by(EmployerProfile.company_name.asc())
    )

    rows = session.execute(stmt).all()

    return [
        AdminEmployerResponse(
            id=ep.id,
            user_id=user.id,
            email=user.email,
            company_name=ep.company_name,
            company_size=ep.company_size,
            industry=ep.industry,
            subscription_tier=ep.subscription_tier,
            subscription_status=ep.subscription_status,
            contact_first_name=ep.contact_first_name,
            contact_last_name=ep.contact_last_name,
            contact_email=ep.contact_email,
            active_jobs_count=active_jobs,
            total_jobs_count=total_jobs,
            ai_parsing_used=ep.ai_parsing_used,
            intro_requests_used=ep.intro_requests_used,
            created_at=ep.created_at,
        )
        for ep, user, total_jobs, active_jobs in rows
    ]


@router.get("/{employer_id}/jobs", response_model=list[AdminEmployerJobResponse])
def list_employer_jobs(
    employer_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminEmployerJobResponse]:
    """List all jobs for a specific employer."""
    employer = session.get(EmployerProfile, employer_id)
    if employer is None:
        raise HTTPException(status_code=404, detail="Employer not found.")

    stmt = (
        select(EmployerJob)
        .where(EmployerJob.employer_id == employer_id)
        .order_by(EmployerJob.created_at.desc())
    )
    jobs = session.execute(stmt).scalars().all()

    return [
        AdminEmployerJobResponse(
            id=j.id,
            title=j.title,
            status=j.status,
            location=j.location,
            remote_policy=j.remote_policy,
            application_count=j.application_count,
            view_count=j.view_count,
            posted_at=j.posted_at,
            created_at=j.created_at,
            archived=j.archived,
            archived_reason=j.archived_reason,
        )
        for j in jobs
    ]


@router.post("/delete", response_model=DeleteEmployersResponse)
def delete_employers(
    payload: DeleteEmployersRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> DeleteEmployersResponse:
    """Delete one or more employers and all their associated data."""
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    deleted_count = 0
    for user_id in payload.user_ids:
        if cascade_delete_user(session, user_id):
            deleted_count += 1

    session.commit()

    return DeleteEmployersResponse(
        deleted_count=deleted_count,
        message=f"Successfully deleted {deleted_count} employer(s).",
    )


@router.post(
    "/{employer_id}/tier-override",
    response_model=EmployerTierOverrideResponse,
)
def override_employer_tier(
    employer_id: int,
    body: EmployerTierOverrideRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> EmployerTierOverrideResponse:
    """Override an employer's subscription tier (admin only)."""
    employer = session.get(EmployerProfile, employer_id)
    if employer is None:
        raise HTTPException(status_code=404, detail="Employer not found.")

    valid_tiers = {"free", "starter", "pro"}
    if body.subscription_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be one of: {', '.join(sorted(valid_tiers))}",
        )

    employer.subscription_tier = body.subscription_tier
    employer.subscription_status = body.subscription_status
    session.commit()

    return EmployerTierOverrideResponse(
        id=employer.id,
        subscription_tier=employer.subscription_tier,
        subscription_status=employer.subscription_status,
    )
