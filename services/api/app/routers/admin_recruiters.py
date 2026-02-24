"""Admin recruiter management router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.user import User
from app.schemas.admin_recruiters import (
    AdminRecruiterClientResponse,
    AdminRecruiterJobResponse,
    AdminRecruiterResponse,
    DeleteRecruitersRequest,
    DeleteRecruitersResponse,
    RecruiterTierOverrideRequest,
    RecruiterTierOverrideResponse,
)
from app.services.auth import require_admin_user
from app.services.cascade_delete import cascade_delete_user

router = APIRouter(prefix="/api/admin/recruiters", tags=["admin-recruiters"])


@router.get("", response_model=list[AdminRecruiterResponse])
def list_recruiters(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterResponse]:
    """List all recruiters with profile data, counts, and usage."""
    # Subquery: pipeline candidate count per recruiter
    pipeline_sq = (
        select(
            RecruiterPipelineCandidate.recruiter_profile_id,
            func.count(RecruiterPipelineCandidate.id).label("cnt"),
        )
        .group_by(RecruiterPipelineCandidate.recruiter_profile_id)
        .subquery()
    )

    # Subquery: jobs count per recruiter
    jobs_sq = (
        select(
            RecruiterJob.recruiter_profile_id,
            func.count(RecruiterJob.id).label("cnt"),
        )
        .group_by(RecruiterJob.recruiter_profile_id)
        .subquery()
    )

    # Subquery: clients count per recruiter
    clients_sq = (
        select(
            RecruiterClient.recruiter_profile_id,
            func.count(RecruiterClient.id).label("cnt"),
        )
        .group_by(RecruiterClient.recruiter_profile_id)
        .subquery()
    )

    stmt = (
        select(
            RecruiterProfile,
            User,
            func.coalesce(pipeline_sq.c.cnt, 0).label("pipeline_count"),
            func.coalesce(jobs_sq.c.cnt, 0).label("jobs_count"),
            func.coalesce(clients_sq.c.cnt, 0).label("clients_count"),
        )
        .join(User, RecruiterProfile.user_id == User.id)
        .outerjoin(
            pipeline_sq,
            RecruiterProfile.id == pipeline_sq.c.recruiter_profile_id,
        )
        .outerjoin(
            jobs_sq,
            RecruiterProfile.id == jobs_sq.c.recruiter_profile_id,
        )
        .outerjoin(
            clients_sq,
            RecruiterProfile.id == clients_sq.c.recruiter_profile_id,
        )
        .order_by(RecruiterProfile.company_name.asc())
    )

    rows = session.execute(stmt).all()

    return [
        AdminRecruiterResponse(
            id=rp.id,
            user_id=user.id,
            email=user.email,
            company_name=rp.company_name,
            company_type=rp.company_type,
            company_website=rp.company_website,
            subscription_tier=rp.subscription_tier,
            subscription_status=rp.subscription_status,
            billing_interval=rp.billing_interval,
            billing_exempt=rp.billing_exempt,
            seats_purchased=rp.seats_purchased,
            seats_used=rp.seats_used,
            is_trial_active=rp.is_trial_active,
            trial_days_remaining=rp.trial_days_remaining,
            candidate_briefs_used=rp.candidate_briefs_used,
            salary_lookups_used=rp.salary_lookups_used,
            job_uploads_used=rp.job_uploads_used,
            intro_requests_used=rp.intro_requests_used,
            resume_imports_used=rp.resume_imports_used,
            outreach_enrollments_used=rp.outreach_enrollments_used,
            pipeline_count=pipeline_count,
            jobs_count=jobs_count,
            clients_count=clients_count,
            created_at=rp.created_at,
        )
        for rp, user, pipeline_count, jobs_count, clients_count in rows
    ]


@router.get("/{recruiter_id}/jobs", response_model=list[AdminRecruiterJobResponse])
def list_recruiter_jobs(
    recruiter_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterJobResponse]:
    """List all job orders for a specific recruiter."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    stmt = (
        select(RecruiterJob)
        .where(RecruiterJob.recruiter_profile_id == recruiter_id)
        .order_by(RecruiterJob.created_at.desc())
    )
    jobs = session.execute(stmt).scalars().all()

    return [
        AdminRecruiterJobResponse(
            id=j.id,
            title=j.title,
            status=j.status,
            client_company_name=j.client_company_name,
            location=j.location,
            priority=j.priority,
            positions_to_fill=j.positions_to_fill,
            positions_filled=j.positions_filled,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get(
    "/{recruiter_id}/clients",
    response_model=list[AdminRecruiterClientResponse],
)
def list_recruiter_clients(
    recruiter_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterClientResponse]:
    """List all clients for a specific recruiter."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    stmt = (
        select(RecruiterClient)
        .where(RecruiterClient.recruiter_profile_id == recruiter_id)
        .order_by(RecruiterClient.company_name.asc())
    )
    clients = session.execute(stmt).scalars().all()

    return [
        AdminRecruiterClientResponse(
            id=c.id,
            company_name=c.company_name,
            industry=c.industry,
            contact_name=c.contact_name,
            contact_email=c.contact_email,
            status=c.status,
            contract_type=c.contract_type,
            fee_percentage=c.fee_percentage,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.post("/delete", response_model=DeleteRecruitersResponse)
def delete_recruiters(
    payload: DeleteRecruitersRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> DeleteRecruitersResponse:
    """Delete one or more recruiters and all their associated data."""
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    deleted_count = 0
    for user_id in payload.user_ids:
        if cascade_delete_user(session, user_id):
            deleted_count += 1

    session.commit()

    return DeleteRecruitersResponse(
        deleted_count=deleted_count,
        message=f"Successfully deleted {deleted_count} recruiter(s).",
    )


@router.post(
    "/{recruiter_id}/tier-override",
    response_model=RecruiterTierOverrideResponse,
)
def override_recruiter_tier(
    recruiter_id: int,
    body: RecruiterTierOverrideRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> RecruiterTierOverrideResponse:
    """Override a recruiter's subscription tier (admin only)."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    valid_tiers = {"trial", "solo", "team", "agency"}
    if body.subscription_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be one of: {', '.join(sorted(valid_tiers))}",
        )

    recruiter.subscription_tier = body.subscription_tier
    recruiter.subscription_status = body.subscription_status
    if body.billing_exempt is not None:
        recruiter.billing_exempt = body.billing_exempt
    # Clear trial dates if moving from trial to a paid tier
    if body.subscription_tier != "trial":
        recruiter.trial_started_at = None
        recruiter.trial_ends_at = None
    session.commit()

    return RecruiterTierOverrideResponse(
        id=recruiter.id,
        subscription_tier=recruiter.subscription_tier,
        subscription_status=recruiter.subscription_status,
        billing_exempt=recruiter.billing_exempt,
    )
