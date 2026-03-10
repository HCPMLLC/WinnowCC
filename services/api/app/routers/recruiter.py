"""Recruiter API: profile, CRM clients, pipeline, activities, team, jobs, dashboard."""

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import (
    String,
    cast,
    func,
    nulls_last,
    or_,
    select,
)
from sqlalchemy import (
    asc as sa_asc,
)
from sqlalchemy import (
    desc as sa_desc,
)
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_job_candidate import RecruiterJobCandidate
from app.models.user import User
from app.schemas.employer import (
    BulkUploadFileResult,
    BulkUploadResponse,
)
from app.schemas.introduction import (
    IntroductionRequestCreate,
    IntroductionRequestResponse,
)
from app.schemas.recruiter import (
    RecruiterProfileCreate,
    RecruiterProfileResponse,
    RecruiterProfileUpdate,
    SourcedCandidateUpdate,
)
from app.schemas.recruiter_crm import (
    PipelineCandidateCreate,
    PipelineCandidateResponse,
    PipelineCandidateUpdate,
    RecruiterActivityCreate,
    RecruiterActivityResponse,
    RecruiterClientCreate,
    RecruiterClientResponse,
    RecruiterClientUpdate,
    RecruiterDashboardResponse,
    RecruiterTeamInvite,
    RecruiterTeamMemberResponse,
)
from app.schemas.recruiter_job import (
    CandidateMatchedJobResult,
    CandidateMatchedJobsResponse,
    RecruiterJobCandidateResult,
    RecruiterJobCandidatesResponse,
    RecruiterJobCreate,
    RecruiterJobResponse,
    RecruiterJobUpdate,
)
from app.schemas.upload_batch import UploadBatchCreatedResponse
from app.services.auth import get_recruiter_profile, require_recruiter

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

logger = logging.getLogger(__name__)

# Tier-based batch limits for document upload
_RECRUITER_BATCH_LIMITS: dict[str, int] = {
    "trial": 3,
    "solo": 3,
    "team": 5,
    "agency": 10,
}


# ============================================================================
# PROFILE MANAGEMENT
# ============================================================================


@router.post(
    "/profile",
    response_model=RecruiterProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recruiter_profile(
    profile_data: RecruiterProfileCreate,
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> RecruiterProfileResponse:
    """Create recruiter profile and start 14-day free trial."""
    existing = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recruiter profile already exists for this user.",
        )

    profile = RecruiterProfile(user_id=user.id, **profile_data.model_dump())
    profile.start_trial()
    session.add(profile)

    user.onboarding_completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(profile)

    return RecruiterProfileResponse.model_validate(profile)


@router.get("/profile", response_model=RecruiterProfileResponse)
def get_my_recruiter_profile(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
) -> RecruiterProfileResponse:
    """Get current user's recruiter profile."""
    return RecruiterProfileResponse.model_validate(profile)


@router.patch("/profile", response_model=RecruiterProfileResponse)
def update_recruiter_profile(
    profile_data: RecruiterProfileUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterProfileResponse:
    """Update recruiter profile (partial update)."""
    for field, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return RecruiterProfileResponse.model_validate(profile)


# ============================================================================
# PLAN / TIER INFO
# ============================================================================


@router.get("/plan")
def get_plan_info(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Return current plan tier, limits, and CRM level for the frontend."""
    from app.services.billing import (
        RECRUITER_PLAN_LIMITS,
        get_recruiter_tier,
    )

    tier = get_recruiter_tier(profile)
    limits = RECRUITER_PLAN_LIMITS.get(tier, RECRUITER_PLAN_LIMITS["trial"])
    return {
        "tier": tier,
        "subscription_status": profile.subscription_status,
        "trial_days_remaining": profile.trial_days_remaining
        if tier == "trial"
        else None,
        "crm_level": limits.get("client_crm", "basic"),
        "limits": limits,
    }


# ============================================================================
# DASHBOARD
# ============================================================================


@router.get("/dashboard", response_model=RecruiterDashboardResponse)
def get_dashboard(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterDashboardResponse:
    """Get recruiter dashboard stats.

    Solo tier (basic CRM): pipeline_by_stage omitted (totals only).
    Team/Agency (full CRM): full stage breakdown included.
    """
    from app.services.billing import get_recruiter_limit, get_recruiter_tier
    from app.services.recruiter_service import get_dashboard_stats

    stats = get_dashboard_stats(session, profile)

    tier = get_recruiter_tier(profile)
    crm_level = get_recruiter_limit(tier, "client_crm")
    if crm_level == "basic":
        stats["pipeline_by_stage"] = []

    return RecruiterDashboardResponse(**stats)


# ============================================================================
# CLIENTS
# ============================================================================


@router.post(
    "/clients",
    response_model=RecruiterClientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_client(
    data: RecruiterClientCreate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterClientResponse:
    """Create a new client company. Solo tier limited to 5 clients."""
    from app.services.billing import (
        check_recruiter_feature,
        get_recruiter_limit,
        get_recruiter_tier,
    )
    from app.services.recruiter_service import create_client as svc_create
    from app.services.recruiter_service import get_client_job_count

    # Gate hierarchy and contract vehicle features
    if data.parent_client_id and not check_recruiter_feature(
        profile, "client_hierarchy"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Client hierarchy requires a Team or Agency"
                " plan. Upgrade to organize clients under"
                " parent entities."
            ),
        )
    if data.contract_vehicle and not check_recruiter_feature(
        profile, "contract_vehicle_management"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Contract vehicle management requires a Team"
                " or Agency plan. Upgrade to classify clients"
                " by contract vehicle."
            ),
        )

    tier = get_recruiter_tier(profile)
    client_limit = get_recruiter_limit(tier, "clients")
    if isinstance(client_limit, int) and client_limit < 999:
        from app.models.recruiter_client import RecruiterClient

        current_count = (
            session.execute(
                select(func.count(RecruiterClient.id)).where(
                    RecruiterClient.recruiter_profile_id == profile.id
                )
            ).scalar()
            or 0
        )
        if current_count >= client_limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Client limit reached ({client_limit} on {tier} plan). "
                    "Upgrade to Team or Agency for more clients."
                ),
            )

    client = svc_create(session, profile, data.model_dump(exclude_unset=True))
    resp = RecruiterClientResponse.model_validate(client, from_attributes=True)
    resp.job_count = get_client_job_count(session, client.id)
    return resp


@router.get("/clients", response_model=list[RecruiterClientResponse])
def list_clients(
    status_filter: str | None = Query(None, alias="status"),
    contract_vehicle: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("company_name"),
    sort_dir: str = Query("asc"),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[RecruiterClientResponse]:
    """List all clients for this recruiter."""
    from app.services.billing import check_recruiter_feature
    from app.services.recruiter_service import get_client_job_count
    from app.services.recruiter_service import list_clients as svc_list

    if contract_vehicle and not check_recruiter_feature(
        profile, "contract_vehicle_management"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contract vehicle filtering requires a Team or Agency plan.",
        )

    clients = svc_list(
        session,
        profile,
        status_filter,
        contract_vehicle=contract_vehicle,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    results = []
    for c in clients:
        resp = RecruiterClientResponse.model_validate(c, from_attributes=True)
        resp.job_count = get_client_job_count(session, c.id)
        if c.parent_client_id and c.parent:
            resp.parent_company_name = c.parent.company_name
        results.append(resp)
    return results


@router.get("/clients/{client_id}", response_model=RecruiterClientResponse)
def get_client(
    client_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterClientResponse:
    """Get a specific client by ID."""
    from app.services.recruiter_service import get_client as svc_get
    from app.services.recruiter_service import get_client_job_count

    client = svc_get(session, profile, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found."
        )
    resp = RecruiterClientResponse.model_validate(client, from_attributes=True)
    resp.job_count = get_client_job_count(session, client.id)
    return resp


@router.get("/clients/{client_id}/job-summary")
def get_client_job_summary(
    client_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Job summary for a client and its children."""
    from app.services.recruiter_service import (
        get_client_job_summary as svc_summary,
    )

    result = svc_summary(session, profile.id, client_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found.",
        )
    return result.model_dump(mode="json")


@router.put("/clients/{client_id}", response_model=RecruiterClientResponse)
def update_client(
    client_id: int,
    data: RecruiterClientUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterClientResponse:
    """Update a client company."""
    from app.services.billing import check_recruiter_feature
    from app.services.recruiter_service import get_client_job_count
    from app.services.recruiter_service import update_client as svc_update

    # Gate hierarchy and contract vehicle features
    if data.parent_client_id is not None and not check_recruiter_feature(
        profile, "client_hierarchy"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client hierarchy requires a Team or Agency plan.",
        )
    if data.contract_vehicle is not None and not check_recruiter_feature(
        profile, "contract_vehicle_management"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contract vehicle management requires a Team or Agency plan.",
        )

    client = svc_update(
        session, profile, client_id, data.model_dump(exclude_unset=True)
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found."
        )
    resp = RecruiterClientResponse.model_validate(client, from_attributes=True)
    resp.job_count = get_client_job_count(session, client.id)
    return resp


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Delete a client company."""
    from app.services.recruiter_service import delete_client as svc_delete

    if not svc_delete(session, profile, client_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found."
        )


# ============================================================================
# PIPELINE
# ============================================================================


@router.post(
    "/pipeline",
    response_model=PipelineCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_to_pipeline(
    data: PipelineCandidateCreate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> PipelineCandidateResponse:
    """Add a candidate to the recruiter pipeline. Enforces tier pipeline limits."""
    from app.services.billing import get_recruiter_limit, get_recruiter_tier
    from app.services.recruiter_service import add_to_pipeline as svc_add
    from app.services.recruiter_service import resolve_candidate_name

    tier = get_recruiter_tier(profile)
    pipeline_limit = get_recruiter_limit(tier, "pipeline_candidates")
    if isinstance(pipeline_limit, int) and pipeline_limit < 999:
        from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

        current_count = (
            session.execute(
                select(func.count(RecruiterPipelineCandidate.id)).where(
                    RecruiterPipelineCandidate.recruiter_profile_id == profile.id
                )
            ).scalar()
            or 0
        )
        if current_count >= pipeline_limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Pipeline limit reached ({pipeline_limit} on {tier} plan). "
                    "Upgrade for more pipeline capacity."
                ),
            )

    pc = svc_add(session, profile, data.model_dump(exclude_unset=True))
    resp = PipelineCandidateResponse.model_validate(pc, from_attributes=True)
    resp.candidate_name = resolve_candidate_name(session, pc)
    return resp


@router.get("/pipeline")
def list_pipeline(
    stage: str | None = Query(None),
    job_id: int | None = Query(None),
    search: str | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tag filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
):
    """List pipeline candidates with optional filters and total count."""
    from app.models.candidate_profile import CandidateProfile
    from app.services.recruiter_service import count_pipeline as svc_count
    from app.services.recruiter_service import list_pipeline as svc_list
    from app.services.recruiter_service import resolve_candidate_name

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    filter_args = dict(stage=stage, job_id=job_id, search=search, tags=tag_list)
    total = svc_count(session, profile, **filter_args)
    pcs = svc_list(
        session,
        profile,
        **filter_args,
        limit=limit,
        offset=offset,
    )
    # Batch-load linked profiles — select only needed columns to avoid
    # missing-column errors when migrations haven't been applied yet.
    cp_ids = [pc.candidate_profile_id for pc in pcs if pc.candidate_profile_id]
    profiles_map: dict[int, dict] = {}
    if cp_ids:
        cps = session.execute(
            select(
                CandidateProfile.id,
                CandidateProfile.profile_json,
            ).where(CandidateProfile.id.in_(cp_ids))
        ).all()
        for cp_id, cp_profile_json in cps:
            try:
                pj = cp_profile_json or {}
                if not isinstance(pj, dict):
                    pj = {}
                basics = pj.get("basics") or {}
                if not isinstance(basics, dict):
                    basics = {}
                skills_raw = pj.get("skills") or basics.get("top_skills") or []
                skills = []
                for s in skills_raw:
                    if isinstance(s, str):
                        skills.append(s)
                    elif isinstance(s, dict):
                        skills.append(s.get("name", ""))
                is_platform = (
                    not pj.get("sourced_by_user_id")
                    and pj.get("source") != "linkedin_extension"
                )
                target_titles = basics.get("target_titles") or [None]
                headline = pj.get("headline") or (
                    target_titles[0] if target_titles else None
                )
                current_company = pj.get("current_company")
                if not headline or not current_company:
                    exp = pj.get("experience") or []
                    if exp and isinstance(exp[0], dict):
                        if not headline:
                            title = exp[0].get("title") or ""
                            company = exp[0].get("company") or ""
                            raw = f"{title} at {company}"
                            headline = (
                                raw.rstrip().removesuffix(" at").strip()
                                if title
                                else company
                            )
                        if not current_company:
                            current_company = exp[0].get("company")
                # Extract current title from most recent experience
                current_title = None
                exp = pj.get("experience") or []
                if exp and isinstance(exp[0], dict):
                    current_title = exp[0].get("title")

                # Compute years of experience from experience dates
                years_experience = None
                if exp:
                    from dateutil.parser import parse as parse_dt

                    earliest = None
                    for job_entry in exp:
                        if not isinstance(job_entry, dict):
                            continue
                        start = job_entry.get("start_date")
                        if start:
                            try:
                                dt = parse_dt(str(start))
                                if earliest is None or dt < earliest:
                                    earliest = dt
                            except Exception:
                                pass
                    if earliest:
                        diff = datetime.now(UTC) - earliest.replace(
                            tzinfo=UTC
                        )
                        years_experience = max(1, diff.days // 365)

                profiles_map[cp_id] = {
                    "headline": headline,
                    "location": (pj.get("location") or basics.get("location")),
                    "current_company": current_company,
                    "current_title": current_title,
                    "years_experience": years_experience,
                    "skills": [s for s in skills if s][:10],
                    "linkedin_url": pj.get("linkedin_url"),
                    "is_platform_candidate": is_platform,
                }
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to enrich pipeline candidate profile %s",
                    cp_id,
                    exc_info=True,
                )
    # Batch-count how many recruiter jobs each candidate is linked to
    match_counts: dict[int, int] = {}
    if cp_ids:
        from app.models.recruiter_job_candidate import RecruiterJobCandidate as RJC

        rows = session.execute(
            select(
                RJC.candidate_profile_id,
                func.count(RJC.id),
            )
            .where(RJC.candidate_profile_id.in_(cp_ids))
            .group_by(RJC.candidate_profile_id)
        ).all()
        match_counts = {row[0]: row[1] for row in rows}

    results = []
    for pc in pcs:
        resp = PipelineCandidateResponse.model_validate(pc, from_attributes=True)
        resp.candidate_name = resolve_candidate_name(session, pc)
        if pc.candidate_profile_id and pc.candidate_profile_id in profiles_map:
            info = profiles_map[pc.candidate_profile_id]
            resp.headline = info["headline"]
            resp.location = info["location"]
            resp.current_company = info["current_company"]
            if info.get("current_title"):
                resp.current_title = info["current_title"]
            if info.get("years_experience"):
                resp.years_experience = info["years_experience"]
            resp.skills = info["skills"]
            resp.linkedin_url = info["linkedin_url"]
            resp.is_platform_candidate = info["is_platform_candidate"]
        if pc.candidate_profile_id:
            resp.job_match_count = match_counts.get(pc.candidate_profile_id, 0)
        results.append(resp)
    return {"items": results, "total": total}


@router.post(
    "/pipeline/upload-resumes",
    response_model=UploadBatchCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_pipeline_resumes(
    files: list[UploadFile] = File(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
):
    """Upload resume files for async batch processing.

    Files are staged, tracking rows created, and worker jobs enqueued.
    Returns immediately with a batch_id for status polling.
    """
    from app.services.batch_upload import create_upload_batch
    from app.services.billing import (
        check_recruiter_monthly_limit,
        get_recruiter_limit,
        get_recruiter_tier,
    )

    tier = get_recruiter_tier(profile)

    # Enforce monthly quota (resets counters if needed)
    check_recruiter_monthly_limit(
        profile,
        "resume_imports_used",
        "resume_imports_per_month",
        session,
    )

    # Enforce per-batch limit
    batch_limit = get_recruiter_limit(tier, "resume_imports_per_batch")
    if isinstance(batch_limit, int) and len(files) > batch_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{tier.capitalize()} tier allows up to {batch_limit} file(s) "
                f"per batch. You submitted {len(files)}."
            ),
        )

    # Check remaining monthly quota vs files submitted
    monthly_limit = get_recruiter_limit(tier, "resume_imports_per_month")
    current_used = profile.resume_imports_used or 0
    if isinstance(monthly_limit, int) and monthly_limit < 999:
        remaining_before = monthly_limit - current_used
        if len(files) > remaining_before:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly quota: {remaining_before} resume import(s) remaining "
                    f"(limit: {monthly_limit}). You submitted {len(files)}."
                ),
            )

    # Read raw bytes from each file
    file_list: list[tuple[str, bytes]] = []
    for i, upload_file in enumerate(files):
        filename = upload_file.filename or f"file_{i}"
        contents = await upload_file.read()
        file_list.append((filename, contents))

    # Stage files, create tracking rows, enqueue worker jobs
    result = create_upload_batch(
        user_id=profile.user_id,
        owner_profile_id=profile.id,
        batch_type="recruiter_resume",
        files=file_list,
        session=session,
    )

    return UploadBatchCreatedResponse(
        batch_id=result["batch_id"],
        status_url=result["status_url"],
        total_files=len(file_list),
    )


@router.post("/pipeline/bulk-delete")
def bulk_delete_pipeline_candidates(
    ids: list[int] = Query(..., max_length=100),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Batch-delete pipeline candidates owned by this recruiter."""
    from app.services.recruiter_service import bulk_delete_pipeline

    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 candidate IDs.",
        )
    deleted = bulk_delete_pipeline(session, profile, ids)
    return {"deleted": deleted, "requested": len(ids)}


@router.patch("/pipeline/bulk-stage")
def bulk_update_pipeline_stage(
    ids: list[int] = Query(..., max_length=100),
    new_stage: str = Query(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Batch-update stage on pipeline candidates owned by this recruiter."""
    from app.schemas.recruiter_crm import ALLOWED_STAGES
    from app.services.recruiter_service import (
        bulk_update_pipeline_stage as svc_bulk_stage,
    )

    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 candidate IDs.",
        )
    if new_stage not in ALLOWED_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stage. Must be one of: {', '.join(ALLOWED_STAGES)}",
        )
    updated = svc_bulk_stage(session, profile, ids, new_stage)
    return {"updated": updated, "requested": len(ids)}


@router.put("/pipeline/{candidate_id}", response_model=PipelineCandidateResponse)
def update_pipeline_candidate(
    candidate_id: int,
    data: PipelineCandidateUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> PipelineCandidateResponse:
    """Update a pipeline candidate (stage changes are auto-logged)."""
    from app.services.recruiter_service import resolve_candidate_name
    from app.services.recruiter_service import (
        update_pipeline_candidate as svc_update,
    )

    pc = svc_update(session, profile, candidate_id, data.model_dump(exclude_unset=True))
    if pc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline candidate not found.",
        )
    resp = PipelineCandidateResponse.model_validate(pc, from_attributes=True)
    resp.candidate_name = resolve_candidate_name(session, pc)
    return resp


@router.delete("/pipeline/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_candidate(
    candidate_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Remove a candidate from the pipeline."""
    from app.services.recruiter_service import (
        delete_pipeline_candidate as svc_delete,
    )

    if not svc_delete(session, profile, candidate_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline candidate not found.",
        )


# ============================================================================
# TAGS
# ============================================================================


@router.post("/pipeline/{candidate_id}/tags")
def add_pipeline_tags(
    candidate_id: int,
    tags: list[str],
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Add tags to a pipeline candidate."""
    from app.services.recruiter_service import add_tags

    pc = add_tags(session, profile, candidate_id, tags)
    if pc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline candidate not found.",
        )
    session.commit()
    return {"id": pc.id, "tags": pc.tags}


@router.delete("/pipeline/{candidate_id}/tags")
def remove_pipeline_tags(
    candidate_id: int,
    tags: list[str] = Query(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Remove tags from a pipeline candidate."""
    from app.services.recruiter_service import remove_tags

    pc = remove_tags(session, profile, candidate_id, tags)
    if pc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline candidate not found.",
        )
    session.commit()
    return {"id": pc.id, "tags": pc.tags}


@router.get("/tags")
def list_recruiter_tags(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """List all unique tags used by this recruiter (for autocomplete)."""
    from app.services.recruiter_service import list_unique_tags

    return {"tags": list_unique_tags(session, profile)}


# ============================================================================
# ACTIVITIES
# ============================================================================


@router.post(
    "/activities",
    response_model=RecruiterActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    data: RecruiterActivityCreate,
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterActivityResponse:
    """Log a recruiter activity."""
    from app.services.recruiter_service import log_activity

    activity = log_activity(
        session, profile, user.id, data.model_dump(exclude_unset=True)
    )
    return RecruiterActivityResponse.model_validate(activity, from_attributes=True)


@router.get("/activities", response_model=list[RecruiterActivityResponse])
def get_activities(
    limit: int = Query(20, ge=1, le=100),
    pipeline_candidate_id: int | None = Query(None),
    job_id: int | None = Query(None),
    client_id: int | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[RecruiterActivityResponse]:
    """List recruiter activities with optional filters.

    Solo tier: limited to last 7 days of history.
    Team/Agency: unlimited history.
    """
    from datetime import datetime, timedelta

    from app.services.billing import get_recruiter_limit, get_recruiter_tier
    from app.services.recruiter_service import list_activities

    tier = get_recruiter_tier(profile)
    crm_level = get_recruiter_limit(tier, "client_crm")

    since = None
    if crm_level == "basic":
        since = datetime.now(UTC) - timedelta(days=7)

    activities = list_activities(
        session,
        profile,
        limit=limit,
        pipeline_candidate_id=pipeline_candidate_id,
        job_id=job_id,
        client_id=client_id,
        since=since,
    )
    return [
        RecruiterActivityResponse.model_validate(a, from_attributes=True)
        for a in activities
    ]


# ============================================================================
# ANALYTICS
# ============================================================================


@router.get("/analytics/funnel")
def analytics_funnel(
    job_id: int | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Pipeline funnel — candidates at each stage."""
    from app.services.recruiter_analytics import get_pipeline_funnel

    return {"funnel": get_pipeline_funnel(session, profile.id, job_id)}


@router.get("/analytics/time-to-hire")
def analytics_time_to_hire(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Time-to-hire metrics (avg/median/p75 days)."""
    from app.services.recruiter_analytics import get_time_to_hire

    return get_time_to_hire(session, profile.id)


@router.get("/analytics/conversions")
def analytics_conversions(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Stage-to-stage conversion rates."""
    from app.services.recruiter_analytics import get_stage_conversion_rates

    return {"conversions": get_stage_conversion_rates(session, profile.id)}


@router.get("/analytics/sources")
def analytics_sources(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Source effectiveness breakdown."""
    from app.services.recruiter_analytics import get_source_effectiveness

    return {"sources": get_source_effectiveness(session, profile.id)}


# ============================================================================
# STAGE RULES
# ============================================================================


@router.post("/stage-rules", status_code=status.HTTP_201_CREATED)
def create_stage_rule(
    data: dict,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Create an automated stage advancement rule."""
    from app.services.stage_rules import create_rule

    allowed = {
        "recruiter_job_id",
        "from_stage",
        "to_stage",
        "condition_type",
        "condition_value",
        "is_active",
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    rule = create_rule(session, profile.id, filtered)
    session.commit()
    return {
        "id": rule.id,
        "from_stage": rule.from_stage,
        "to_stage": rule.to_stage,
        "condition_type": rule.condition_type,
        "condition_value": rule.condition_value,
        "is_active": rule.is_active,
        "recruiter_job_id": rule.recruiter_job_id,
    }


@router.get("/stage-rules")
def list_stage_rules(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """List all stage rules for this recruiter."""
    from app.services.stage_rules import list_rules

    rules = list_rules(session, profile.id)
    return {
        "rules": [
            {
                "id": r.id,
                "from_stage": r.from_stage,
                "to_stage": r.to_stage,
                "condition_type": r.condition_type,
                "condition_value": r.condition_value,
                "is_active": r.is_active,
                "recruiter_job_id": r.recruiter_job_id,
            }
            for r in rules
        ]
    }


@router.patch("/stage-rules/{rule_id}")
def update_stage_rule(
    rule_id: int,
    data: dict,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Update a stage rule."""
    from app.services.stage_rules import update_rule

    allowed = {
        "from_stage",
        "to_stage",
        "condition_type",
        "condition_value",
        "is_active",
        "recruiter_job_id",
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    rule = update_rule(session, profile.id, rule_id, filtered)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage rule not found.",
        )
    session.commit()
    return {
        "id": rule.id,
        "from_stage": rule.from_stage,
        "to_stage": rule.to_stage,
        "condition_type": rule.condition_type,
        "condition_value": rule.condition_value,
        "is_active": rule.is_active,
        "recruiter_job_id": rule.recruiter_job_id,
    }


@router.delete("/stage-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage_rule(
    rule_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Delete a stage rule."""
    from app.services.stage_rules import delete_rule

    if not delete_rule(session, profile.id, rule_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage rule not found.",
        )
    session.commit()


@router.post("/stage-rules/apply")
def apply_stage_rules(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Apply all active rules to all pipeline candidates."""
    from app.services.stage_rules import apply_rules_to_batch

    advanced = apply_rules_to_batch(session, profile.id)
    session.commit()
    return {"advanced": advanced}


# ============================================================================
# TEAM
# ============================================================================


@router.get("/team", response_model=list[RecruiterTeamMemberResponse])
def get_team_members(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[RecruiterTeamMemberResponse]:
    """List team members for this recruiter profile."""
    from app.services.recruiter_service import list_team_members

    members = list_team_members(session, profile)
    results = []
    for m in members:
        resp = RecruiterTeamMemberResponse.model_validate(m, from_attributes=True)
        user = session.get(User, m.user_id)
        resp.email = user.email if user else None
        results.append(resp)
    return results


@router.post(
    "/team",
    response_model=RecruiterTeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_team_member(
    data: RecruiterTeamInvite,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterTeamMemberResponse:
    """Invite a team member (checks seat limits)."""
    from app.services.recruiter_service import invite_team_member as svc_invite

    member = svc_invite(session, profile, data.email, data.role)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seat limit reached or user not found.",
        )
    resp = RecruiterTeamMemberResponse.model_validate(member, from_attributes=True)
    resp.email = data.email
    return resp


@router.delete("/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    member_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Remove a team member."""
    from app.services.recruiter_service import remove_team_member as svc_remove

    if not svc_remove(session, profile, member_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found.",
        )


# ============================================================================
# NOTIFICATIONS & @MENTIONS
# ============================================================================


@router.post("/pipeline/{candidate_id}/notes")
def add_pipeline_note(
    candidate_id: int,
    body: dict,
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Add a note to a pipeline candidate with @mention support."""
    from app.services.recruiter_service import create_note_with_mentions

    text = body.get("body", "")
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Note body is required.",
        )
    activity = create_note_with_mentions(session, profile, user.id, candidate_id, text)
    session.commit()
    return {
        "id": activity.id,
        "body": activity.body,
        "created_at": (
            activity.created_at.isoformat() if activity.created_at else None
        ),
    }


@router.get("/notifications")
def get_recruiter_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict:
    """Get notifications for the current user."""
    from app.services.recruiter_service import get_notifications

    notifs = get_notifications(session, user.id, unread_only=unread_only, limit=limit)
    return {
        "notifications": [
            {
                "id": n.id,
                "notification_type": n.notification_type,
                "message": n.message,
                "is_read": n.is_read,
                "sender_user_id": n.sender_user_id,
                "created_at": (n.created_at.isoformat() if n.created_at else None),
            }
            for n in notifs
        ]
    }


@router.post("/notifications/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict:
    """Mark a notification as read."""
    from app.services.recruiter_service import mark_notification_read

    if not mark_notification_read(session, user.id, notification_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    session.commit()
    return {"status": "ok"}


# ============================================================================
# ONBOARDING
# ============================================================================


@router.post("/onboarding/complete")
def complete_onboarding(
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict:
    """Mark recruiter onboarding as done."""
    user.onboarding_completed_at = datetime.now(UTC)
    session.commit()
    return {"status": "ok"}


# ============================================================================
# CANDIDATES (sourced)
# ============================================================================


@router.get("/candidates")
def list_sourced_candidates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List candidate profiles sourced by this recruiter."""
    # Find profiles sourced by this user (stored in profile_json.sourced_by_user_id)
    # Also include all linkedin_extension sourced profiles for now
    stmt = (
        select(CandidateProfile)
        .where(
            or_(
                cast(CandidateProfile.profile_json["sourced_by_user_id"], String)
                == str(user.id),
                cast(CandidateProfile.profile_json["source"], String).ilike(
                    "%linkedin_extension%"
                ),
            )
        )
        .order_by(CandidateProfile.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    profiles = session.execute(stmt).scalars().all()

    # Batch-count how many recruiter jobs each candidate is linked to
    profile_ids = [p.id for p in profiles]
    match_counts: dict[int, int] = {}
    if profile_ids:
        from app.models.recruiter_job_candidate import RecruiterJobCandidate as RJC

        rows = session.execute(
            select(
                RJC.candidate_profile_id,
                func.count(RJC.id),
            )
            .where(RJC.candidate_profile_id.in_(profile_ids))
            .group_by(RJC.candidate_profile_id)
        ).all()
        match_counts = {row[0]: row[1] for row in rows}

    candidates = []
    for p in profiles:
        pj = p.profile_json or {}
        candidates.append(
            {
                "candidate_profile_id": p.id,
                "profile_json": pj,
                "job_match_count": match_counts.get(p.id, 0),
            }
        )

    return {"candidates": candidates, "total": len(candidates)}


@router.get("/candidates/export")
def export_sourced_candidates(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Export all sourced candidates to CSV or XLSX."""
    from io import BytesIO

    from app.services.recruiter_export import export_csv, export_xlsx

    stmt = (
        select(CandidateProfile)
        .where(
            or_(
                cast(CandidateProfile.profile_json["sourced_by_user_id"], String)
                == str(user.id),
                cast(CandidateProfile.profile_json["source"], String).ilike(
                    "%linkedin_extension%"
                ),
            )
        )
        .order_by(CandidateProfile.updated_at.desc())
    )
    profiles = session.execute(stmt).scalars().all()

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    if format == "xlsx":
        data = export_xlsx(profiles)
        return StreamingResponse(
            BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="candidates-{today}.xlsx"'
            },
        )

    data = export_csv(profiles)
    return StreamingResponse(
        BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="candidates-{today}.csv"'
        },
    )


@router.delete("/candidates")
def delete_sourced_candidates(
    ids: list[int] = Query(..., max_length=100),
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict:
    """Batch-delete sourced candidate profiles.

    Only deletes profiles where sourced_by_user_id == current user.
    Cleans up placeholder @sourced.winnow User records with no remaining profiles.
    """
    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 candidate IDs.",
        )

    profiles = (
        session.execute(select(CandidateProfile).where(CandidateProfile.id.in_(ids)))
        .scalars()
        .all()
    )

    deleted = 0
    placeholder_user_ids: set[int] = set()

    for p in profiles:
        pj = p.profile_json or {}
        sourced_by = str(pj.get("sourced_by_user_id", ""))
        source = pj.get("source", "")

        if sourced_by != str(user.id) and source != "linkedin_extension":
            continue

        # Track placeholder user for cleanup
        if p.user_id:
            placeholder_user_ids.add(p.user_id)

        session.delete(p)
        deleted += 1

    session.flush()

    # Clean up placeholder @sourced.winnow users with no remaining profiles
    for uid in placeholder_user_ids:
        u = session.get(User, uid)
        if not u or not u.email.endswith("@sourced.winnow"):
            continue
        remaining = session.execute(
            select(func.count(CandidateProfile.id)).where(
                CandidateProfile.user_id == uid
            )
        ).scalar()
        if not remaining:
            session.delete(u)

    session.commit()

    return {"deleted": deleted, "requested": len(ids)}


# Immutable fields that recruiters cannot edit
_IMMUTABLE_PROFILE_FIELDS = {"source", "sourced_by_user_id", "linkedin_url"}


@router.get(
    "/candidates/{candidate_profile_id}/matched-jobs",
    response_model=CandidateMatchedJobsResponse,
)
def get_candidate_matched_jobs(
    candidate_profile_id: int,
    limit: int = Query(20, ge=1, le=100),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> CandidateMatchedJobsResponse:
    """Return matched jobs for a candidate, sorted by match score descending."""
    cp = session.get(CandidateProfile, candidate_profile_id)
    if cp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    cached = (
        session.execute(
            select(RecruiterJobCandidate)
            .join(
                RecruiterJob,
                RecruiterJob.id == RecruiterJobCandidate.recruiter_job_id,
            )
            .where(
                RecruiterJobCandidate.candidate_profile_id == candidate_profile_id,
                RecruiterJob.recruiter_profile_id == profile.id,
            )
            .order_by(RecruiterJobCandidate.match_score.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    total = (
        session.execute(
            select(func.count(RecruiterJobCandidate.id))
            .join(
                RecruiterJob,
                RecruiterJob.id == RecruiterJobCandidate.recruiter_job_id,
            )
            .where(
                RecruiterJobCandidate.candidate_profile_id == candidate_profile_id,
                RecruiterJob.recruiter_profile_id == profile.id,
            )
        ).scalar()
        or 0
    )

    jobs = []
    for match in cached:
        job = session.get(RecruiterJob, match.recruiter_job_id)
        if not job:
            continue
        jobs.append(
            CandidateMatchedJobResult(
                job_id=job.id,
                title=job.title,
                client_company_name=job.client_company_name,
                location=job.location,
                remote_policy=job.remote_policy,
                employment_type=job.employment_type,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                status=job.status,
                match_score=match.match_score,
                matched_skills=match.matched_skills or [],
            )
        )

    return CandidateMatchedJobsResponse(
        candidate_profile_id=candidate_profile_id,
        jobs=jobs,
        total=total,
    )


@router.get("/candidates/{candidate_profile_id}")
def get_sourced_candidate(
    candidate_profile_id: int,
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get a candidate profile by ID (sourced, pipeline, or job candidates)."""
    cp = session.get(CandidateProfile, candidate_profile_id)
    if cp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    pj = cp.profile_json or {}
    sourced_by = str(pj.get("sourced_by_user_id") or "")
    source = pj.get("source", "")

    # Allow if: own profile, sourced by this recruiter, or linkedin_extension
    allowed = (
        cp.user_id == user.id
        or sourced_by == str(user.id)
        or source == "linkedin_extension"
    )

    # Allow if candidate is in recruiter's pipeline
    if not allowed:
        from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

        in_pipeline = session.execute(
            select(RecruiterPipelineCandidate.id)
            .where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                RecruiterPipelineCandidate.candidate_profile_id == candidate_profile_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        allowed = in_pipeline is not None

    # Allow if candidate is in any of recruiter's job candidates
    if not allowed:
        from app.models.recruiter_job import RecruiterJob
        from app.models.recruiter_job_candidate import RecruiterJobCandidate

        in_job = session.execute(
            select(RecruiterJobCandidate.id)
            .join(
                RecruiterJob, RecruiterJob.id == RecruiterJobCandidate.recruiter_job_id
            )
            .where(
                RecruiterJob.recruiter_profile_id == profile.id,
                RecruiterJobCandidate.candidate_profile_id == candidate_profile_id,
            )
            .limit(1)
        ).scalar_one_or_none()
        allowed = in_job is not None

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    # Always return the latest profile version for this user
    if cp.user_id:
        latest = session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == cp.user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest and latest.id != cp.id:
            cp = latest
            pj = cp.profile_json or {}

    return {
        "candidate_profile_id": cp.id,
        "profile_json": pj,
        "created_at": cp.updated_at.isoformat() if cp.updated_at else None,
        "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
    }


@router.put("/candidates/{candidate_profile_id}")
def update_sourced_candidate(
    candidate_profile_id: int,
    data: SourcedCandidateUpdate,
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update editable fields of a sourced candidate's profile_json."""
    profile = session.get(CandidateProfile, candidate_profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    pj = profile.profile_json or {}
    sourced_by = str(pj.get("sourced_by_user_id", ""))
    source = pj.get("source", "")

    if sourced_by != str(user.id) and source != "linkedin_extension":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    # Merge only the fields that were explicitly sent
    updates = data.model_dump(exclude_unset=True)
    updated_pj = {**pj}
    for key, value in updates.items():
        if key not in _IMMUTABLE_PROFILE_FIELDS:
            updated_pj[key] = value

    profile.profile_json = updated_pj
    # Force SQLAlchemy to detect JSONB mutation
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(profile, "profile_json")
    session.commit()
    session.refresh(profile)

    return {
        "candidate_profile_id": profile.id,
        "profile_json": profile.profile_json,
    }


# ============================================================================
# JOB MANAGEMENT
# ============================================================================


@router.post(
    "/jobs",
    response_model=RecruiterJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recruiter_job(
    job_data: RecruiterJobCreate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterJobResponse:
    """Create a new recruiter job posting. Enforces tier job order limits."""
    from app.services.billing import get_recruiter_limit, get_recruiter_tier

    tier = get_recruiter_tier(profile)
    job_limit = get_recruiter_limit(tier, "active_job_orders")
    if isinstance(job_limit, int) and job_limit < 999:
        active_count = (
            session.execute(
                select(func.count(RecruiterJob.id)).where(
                    RecruiterJob.recruiter_profile_id == profile.id,
                    RecruiterJob.status == "active",
                )
            ).scalar()
            or 0
        )
        if active_count >= job_limit:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Active job limit reached ({job_limit} on {tier} plan). "
                    "Close or pause existing jobs, or upgrade your plan."
                ),
            )

    job = RecruiterJob(recruiter_profile_id=profile.id, **job_data.model_dump())
    session.add(job)
    session.flush()

    # Auto-link to employer job by job_id_external
    from app.services.job_linking import auto_link_recruiter_job

    linked_employer_job = auto_link_recruiter_job(session, job)

    # Generate embedding for semantic matching
    try:
        from app.services.embedding import generate_embedding

        text = (
            f"Job Title: {job.title}\n"
            f"Company: {job.client_company_name or ''}\n"
            f"Description: {(job.description or '')[:2000]}\n"
            f"Requirements: {(job.requirements or '')[:1000]}\n"
            f"Location: {job.location or ''}"
        )
        job.embedding = generate_embedding(text)
    except Exception:
        logger.debug("Failed to generate embedding for recruiter job %s", job.id)

    session.commit()
    session.refresh(job)

    # Sync to candidate-facing jobs table and pre-compute candidates
    if job.status == "active":
        _enqueue_recruiter_job_sync(job.id)

    resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = 0
    if linked_employer_job:
        resp.employer_company_name = (
            linked_employer_job.employer.company_name
            if linked_employer_job.employer
            else None
        )
    return resp


@router.post("/jobs/upload-documents", response_model=BulkUploadResponse)
async def upload_job_documents(
    files: list[UploadFile] = File(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> BulkUploadResponse:
    """Upload job description documents for AI parsing.

    Supports .doc, .docx, .pdf, .txt files (max 10 MB each).
    Creates draft RecruiterJob records from extracted data.
    """
    from app.services.billing import (
        check_recruiter_monthly_limit,
        get_recruiter_limit,
        get_recruiter_tier,
        increment_recruiter_counter,
    )
    from app.services.employer_job_parser import parse_job_document

    tier = get_recruiter_tier(profile)

    # Solo tier: Smart Job Parsing not available
    sjp_limit = get_recruiter_limit(tier, "smart_job_parsing_per_month")
    if isinstance(sjp_limit, int) and sjp_limit == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Smart Job Parsing requires a Team or Agency plan.",
        )

    # Enforce monthly upload limit (resets counters if needed)
    check_recruiter_monthly_limit(
        profile,
        "job_uploads_used",
        "smart_job_parsing_per_month",
        session,
    )

    batch_limit = _RECRUITER_BATCH_LIMITS.get(tier, 3)

    if len(files) > batch_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{tier.capitalize()} tier allows up to {batch_limit} file(s) "
                f"per batch. You submitted {len(files)}. "
                "Upgrade your plan for higher batch limits."
            ),
        )

    results: list[BulkUploadFileResult] = []
    succeeded = 0

    for i, upload_file in enumerate(files):
        filename = upload_file.filename or f"file_{i}"

        # Validate file type
        if not filename.lower().endswith((".doc", ".docx", ".pdf", ".txt")):
            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=False,
                    error="Unsupported file type. Use .doc, .docx, .pdf, or .txt.",
                )
            )
            continue

        # Validate file size (10 MB)
        contents = await upload_file.read()
        if len(contents) > 10 * 1024 * 1024:
            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=False,
                    error="File too large. Maximum size is 10 MB.",
                )
            )
            continue

        # Write to temp file and parse
        ext = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            try:
                parsed = parse_job_document(tmp_path)
            except RuntimeError as e:
                results.append(
                    BulkUploadFileResult(
                        filename=filename,
                        success=False,
                        error=str(e),
                    )
                )
                continue

            if not parsed.get("title"):
                results.append(
                    BulkUploadFileResult(
                        filename=filename,
                        success=False,
                        error="Could not extract job title from document.",
                    )
                )
                continue

            # Convert parsed date objects to datetimes for DB columns
            from datetime import date as _date

            start_at = None
            closes_at = None
            sd = parsed.get("start_date")
            cd = parsed.get("close_date")
            if isinstance(sd, _date):
                start_at = datetime(sd.year, sd.month, sd.day, tzinfo=UTC)
            if isinstance(cd, _date):
                closes_at = datetime(cd.year, cd.month, cd.day, tzinfo=UTC)

            job = RecruiterJob(
                recruiter_profile_id=profile.id,
                title=parsed.get("title"),
                description=parsed.get("description") or "",
                requirements=parsed.get("requirements"),
                nice_to_haves=parsed.get("nice_to_haves"),
                location=parsed.get("location"),
                remote_policy=parsed.get("remote_policy"),
                employment_type=parsed.get("employment_type"),
                salary_min=parsed.get("salary_min"),
                salary_max=parsed.get("salary_max"),
                salary_currency=parsed.get("salary_currency") or "USD",
                hourly_rate_min=parsed.get("hourly_rate_min"),
                hourly_rate_max=parsed.get("hourly_rate_max"),
                department=parsed.get("department"),
                job_id_external=parsed.get("job_id_external"),
                job_category=parsed.get("job_category"),
                client_company_name=parsed.get("client_company_name"),
                application_email=parsed.get("application_email"),
                application_url=parsed.get("application_url"),
                start_at=start_at,
                closes_at=closes_at,
                status="draft",
            )
            session.add(job)
            session.flush()

            # Auto-link to employer job by job_id_external
            from app.services.job_linking import auto_link_recruiter_job

            auto_link_recruiter_job(session, job)

            increment_recruiter_counter(profile, "job_uploads_used", session)

            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=True,
                    job_id=job.id,
                    title=parsed.get("title"),
                )
            )
            succeeded += 1

        except Exception as exc:
            logger.exception("Error parsing upload file: %s", filename)
            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=False,
                    error=f"Parse error: {exc}",
                )
            )
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    session.commit()

    upgrade_recommendation = None
    if tier in ("trial", "solo") and len(files) >= batch_limit:
        upgrade_recommendation = (
            f"Upgrade from {tier.capitalize()} to unlock higher batch limits."
        )

    total_failed = len(results) - succeeded
    return BulkUploadResponse(
        results=results,
        total_submitted=len(files),
        total_succeeded=succeeded,
        total_failed=total_failed,
        upgrade_recommendation=upgrade_recommendation,
    )


_RECRUITER_JOB_SORT_COLUMNS = {
    "title": RecruiterJob.title,
    "closes_at": RecruiterJob.closes_at,
    "client": RecruiterJob.client_company_name,
    "location": RecruiterJob.location,
    "created_at": RecruiterJob.created_at,
}

_NULLABLE_SORT_COLS = {"closes_at", "client", "location"}


@router.get("/jobs", response_model=list[RecruiterJobResponse])
def list_recruiter_jobs(
    status_filter: str | None = Query(None, alias="status"),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    search: str | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[RecruiterJobResponse]:
    """List all jobs posted by this recruiter."""
    match_count_sq = (
        select(func.count(RecruiterJobCandidate.id))
        .where(RecruiterJobCandidate.recruiter_job_id == RecruiterJob.id)
        .correlate(RecruiterJob)
        .scalar_subquery()
        .label("match_count")
    )

    stmt = select(RecruiterJob, match_count_sq).where(
        RecruiterJob.recruiter_profile_id == profile.id,
    )
    if status_filter:
        allowed = (
            "draft", "active", "paused", "closed",
            "expired", "no_deadline", "no_job_id",
        )
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(allowed)}",
            )
        if status_filter == "expired":
            now = datetime.now(UTC)
            stmt = stmt.where(
                RecruiterJob.closes_at < now,
                RecruiterJob.status.in_(("active", "paused")),
            )
        elif status_filter == "no_deadline":
            stmt = stmt.where(RecruiterJob.closes_at.is_(None))
        elif status_filter == "no_job_id":
            stmt = stmt.where(
                or_(
                    RecruiterJob.job_id_external.is_(None),
                    RecruiterJob.job_id_external == "",
                )
            )
        else:
            stmt = stmt.where(RecruiterJob.status == status_filter)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                RecruiterJob.title.ilike(pattern),
                RecruiterJob.client_company_name.ilike(pattern),
                RecruiterJob.location.ilike(pattern),
                RecruiterJob.remote_policy.ilike(pattern),
                RecruiterJob.employment_type.ilike(pattern),
                RecruiterJob.job_id_external.ilike(pattern),
                RecruiterJob.primary_contact["name"]
                .astext.ilike(pattern),
                RecruiterJob.primary_contact["email"]
                .astext.ilike(pattern),
            )
        )

    # Sorting
    col = _RECRUITER_JOB_SORT_COLUMNS.get(sort_by, RecruiterJob.created_at)
    direction = sa_desc if sort_dir == "desc" else sa_asc
    order_expr = direction(col)
    if sort_by in _NULLABLE_SORT_COLS:
        order_expr = nulls_last(order_expr)
    stmt = stmt.order_by(order_expr)

    rows = session.execute(stmt).all()
    results = []
    for job, count in rows:
        resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
        resp.matched_candidates_count = count or 0
        # Populate contact from primary_contact, fall back to client
        if job.primary_contact:
            resp.contact_name = job.primary_contact.get("name")
            resp.contact_email = job.primary_contact.get("email")
        elif job.client_id and job.client:
            resp.contact_name = job.client.contact_name
            resp.contact_email = job.client.contact_email
        results.append(resp)
    return results


@router.post("/jobs/bulk-delete")
def bulk_delete_recruiter_jobs(
    ids: list[int] = Query(..., max_length=100),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Batch-delete recruiter job postings owned by this recruiter."""
    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 job IDs.",
        )

    jobs = (
        session.execute(
            select(RecruiterJob).where(
                RecruiterJob.id.in_(ids),
                RecruiterJob.recruiter_profile_id == profile.id,
            )
        )
        .scalars()
        .all()
    )

    deleted = 0
    for job in jobs:
        # Deactivate proxy for active jobs
        if job.status == "active":
            try:
                from app.services.job_pipeline import deactivate_recruiter_job_proxy
                from app.services.queue import get_queue

                get_queue().enqueue(deactivate_recruiter_job_proxy, job.id)
            except Exception:
                logger.debug(
                    "Failed to enqueue deactivate for recruiter job %s", job.id
                )

        session.delete(job)
        deleted += 1

    session.commit()
    return {"deleted": deleted, "requested": len(ids)}


@router.get("/jobs/{job_id}", response_model=RecruiterJobResponse)
def get_recruiter_job(
    job_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterJobResponse:
    """Get a specific recruiter job by ID."""
    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    count = (
        session.execute(
            select(func.count(RecruiterJobCandidate.id)).where(
                RecruiterJobCandidate.recruiter_job_id == job.id
            )
        ).scalar()
        or 0
    )
    resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = count
    if job.primary_contact:
        resp.contact_name = job.primary_contact.get("name")
        resp.contact_email = job.primary_contact.get("email")
    elif job.client_id and job.client:
        resp.contact_name = job.client.contact_name
        resp.contact_email = job.client.contact_email
    if job.employer_job_id and job.employer_job:
        ej = job.employer_job
        resp.employer_company_name = ej.employer.company_name if ej.employer else None
    return resp


@router.patch("/jobs/bulk-status")
def bulk_update_recruiter_job_status(
    ids: list[int] = Query(..., max_length=100),
    new_status: str = Query(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Batch-update status of recruiter job postings owned by this recruiter."""
    allowed = ("draft", "active", "paused", "closed")
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(allowed)}",
        )
    if not ids or len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide 1-100 job IDs.",
        )

    jobs = (
        session.execute(
            select(RecruiterJob).where(
                RecruiterJob.id.in_(ids),
                RecruiterJob.recruiter_profile_id == profile.id,
            )
        )
        .scalars()
        .all()
    )

    updated = 0
    for job in jobs:
        old_status = job.status
        if old_status == new_status:
            continue

        job.status = new_status

        # Set posted_at on first publish
        if new_status == "active" and not job.posted_at:
            job.posted_at = datetime.now(UTC)

        # Handle proxy sync logic
        try:
            from app.services.job_pipeline import deactivate_recruiter_job_proxy
            from app.services.queue import get_queue

            q = get_queue()
            if new_status == "active" and old_status != "active":
                _enqueue_recruiter_job_sync(job.id)
            elif old_status == "active" and new_status != "active":
                q.enqueue(deactivate_recruiter_job_proxy, job.id)
        except Exception:
            logger.debug("Failed to enqueue sync for recruiter job %s", job.id)

        updated += 1

    session.commit()
    return {"updated": updated, "requested": len(ids)}


@router.patch("/jobs/{job_id}", response_model=RecruiterJobResponse)
def update_recruiter_job(
    job_id: int,
    job_data: RecruiterJobUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterJobResponse:
    """Update a recruiter job posting.

    If status changes to 'active', syncs to jobs table.
    """
    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    update_data = job_data.model_dump(exclude_unset=True)
    old_status = job.status
    new_status = update_data.get("status")

    # Set posted_at on first publish
    if new_status == "active" and not job.posted_at:
        update_data["posted_at"] = datetime.now(UTC)

    content_fields = {
        "title",
        "description",
        "requirements",
        "salary_min",
        "salary_max",
        "location",
    }
    content_changed = bool(update_data.keys() & content_fields)

    # Map contact_name / contact_email into primary_contact JSONB
    _cn = update_data.pop("contact_name", None)
    _ce = update_data.pop("contact_email", None)
    if _cn is not None or _ce is not None:
        pc = dict(job.primary_contact or {})
        if _cn is not None:
            pc["name"] = _cn or None
        if _ce is not None:
            pc["email"] = _ce or None
        # Remove empty keys
        pc = {k: v for k, v in pc.items() if v}
        update_data["primary_contact"] = pc or None

    for field, value in update_data.items():
        setattr(job, field, value)

    # Regenerate embedding when content fields change
    if content_changed:
        try:
            from app.services.embedding import generate_embedding

            text = (
                f"Job Title: {job.title}\n"
                f"Company: {job.client_company_name or ''}\n"
                f"Description: {(job.description or '')[:2000]}\n"
                f"Requirements: {(job.requirements or '')[:1000]}\n"
                f"Location: {job.location or ''}"
            )
            job.embedding = generate_embedding(text)
        except Exception:
            logger.debug("Failed to regenerate embedding for recruiter job %s", job.id)

    session.commit()
    session.refresh(job)

    # Sync proxy Job row for candidate matching
    try:
        from app.services.job_pipeline import (
            deactivate_recruiter_job_proxy,
            sync_recruiter_job_to_jobs,
        )
        from app.services.queue import get_queue

        q = get_queue()
        if new_status == "active" and old_status != "active":
            _enqueue_recruiter_job_sync(job.id)
        elif new_status == "active" and content_changed:
            q.enqueue(sync_recruiter_job_to_jobs, job.id)
        elif old_status == "active" and new_status and new_status != "active":
            q.enqueue(deactivate_recruiter_job_proxy, job.id)
    except Exception:
        logger.debug("Failed to enqueue sync jobs for recruiter job %s", job.id)

    count = (
        session.execute(
            select(func.count(RecruiterJobCandidate.id)).where(
                RecruiterJobCandidate.recruiter_job_id == job.id
            )
        ).scalar()
        or 0
    )
    resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = count
    return resp


@router.post("/jobs/{job_id}/reparse", response_model=RecruiterJobResponse)
async def reparse_recruiter_job(
    job_id: int,
    file: UploadFile = File(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterJobResponse:
    """Re-upload and re-parse a document for an existing recruiter job.

    Overwrites the job fields with freshly parsed data from the uploaded file.
    Useful when initial parsing produced blank/incomplete results.
    """
    from app.services.employer_job_parser import parse_job_document

    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    filename = file.filename or "file"
    if not filename.lower().endswith((".doc", ".docx", ".pdf", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use .doc, .docx, .pdf, or .txt.",
        )

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10 MB.",
        )

    ext = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        parsed = parse_job_document(tmp_path)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not parsed.get("title"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract job title from document.",
        )

    # Update job fields with parsed data (only overwrite non-empty values)
    from datetime import date as _date

    field_map = {
        "title": "title",
        "description": "description",
        "requirements": "requirements",
        "nice_to_haves": "nice_to_haves",
        "location": "location",
        "remote_policy": "remote_policy",
        "employment_type": "employment_type",
        "salary_min": "salary_min",
        "salary_max": "salary_max",
        "department": "department",
        "job_id_external": "job_id_external",
        "job_category": "job_category",
        "client_company_name": "client_company_name",
        "application_email": "application_email",
        "application_url": "application_url",
    }
    for parsed_key, model_field in field_map.items():
        val = parsed.get(parsed_key)
        if val:
            setattr(job, model_field, val)

    # Handle salary currency
    if parsed.get("salary_currency"):
        job.salary_currency = parsed["salary_currency"]

    # Handle hourly rates
    if parsed.get("hourly_rate_min") is not None:
        job.hourly_rate_min = parsed["hourly_rate_min"]
    if parsed.get("hourly_rate_max") is not None:
        job.hourly_rate_max = parsed["hourly_rate_max"]

    # Handle dates
    sd = parsed.get("start_date")
    cd = parsed.get("close_date")
    if isinstance(sd, _date):
        job.start_at = datetime(sd.year, sd.month, sd.day, tzinfo=UTC)
    if isinstance(cd, _date):
        job.closes_at = datetime(cd.year, cd.month, cd.day, tzinfo=UTC)

    # Regenerate embedding
    try:
        from app.services.embedding import generate_embedding

        text = (
            f"Job Title: {job.title}\n"
            f"Company: {job.client_company_name or ''}\n"
            f"Description: {(job.description or '')[:2000]}\n"
            f"Requirements: {(job.requirements or '')[:1000]}\n"
            f"Location: {job.location or ''}"
        )
        job.embedding = generate_embedding(text)
    except Exception:
        logger.debug("Failed to regenerate embedding for recruiter job %s", job.id)

    session.commit()
    session.refresh(job)

    count = (
        session.execute(
            select(func.count(RecruiterJobCandidate.id)).where(
                RecruiterJobCandidate.recruiter_job_id == job.id
            )
        ).scalar()
        or 0
    )
    resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = count
    return resp


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recruiter_job(
    job_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Delete a recruiter job posting."""
    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    # Deactivate proxy Job before deleting
    try:
        from app.services.job_pipeline import deactivate_recruiter_job_proxy
        from app.services.queue import get_queue

        get_queue().enqueue(deactivate_recruiter_job_proxy, job.id)
    except Exception:
        logger.debug("Failed to enqueue deactivate for recruiter job %s", job.id)

    session.delete(job)
    session.commit()


# ============================================================================
# CANDIDATE MATCHES FOR JOBS
# ============================================================================


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=RecruiterJobCandidatesResponse,
)
def get_recruiter_job_candidates(
    job_id: int,
    limit: int = Query(20, ge=1, le=100),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterJobCandidatesResponse:
    """Return cached candidate matches for a recruiter job, sorted by score desc."""
    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    cached = (
        session.execute(
            select(RecruiterJobCandidate)
            .where(RecruiterJobCandidate.recruiter_job_id == job.id)
            .order_by(RecruiterJobCandidate.match_score.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    total_cached = (
        session.execute(
            select(func.count(RecruiterJobCandidate.id)).where(
                RecruiterJobCandidate.recruiter_job_id == job.id
            )
        ).scalar()
        or 0
    )

    # Look up which candidates are already in pipeline (single query)
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

    cached_cp_ids = [c.candidate_profile_id for c in cached]
    pipeline_ids: set[int] = set()
    if cached_cp_ids:
        rows = (
            session.execute(
                select(RecruiterPipelineCandidate.candidate_profile_id).where(
                    RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                    RecruiterPipelineCandidate.candidate_profile_id.in_(cached_cp_ids),
                )
            )
            .scalars()
            .all()
        )
        pipeline_ids = set(rows)

    candidates = []
    for c in cached:
        cp = session.get(CandidateProfile, c.candidate_profile_id)
        if not cp:
            continue
        candidates.append(
            _profile_to_candidate_result(
                cp, c, in_pipeline=c.candidate_profile_id in pipeline_ids
            )
        )

    return RecruiterJobCandidatesResponse(
        job_id=job.id,
        job_title=job.title,
        candidates=candidates,
        total_cached=total_cached,
    )


@router.post("/jobs/{job_id}/refresh-candidates")
def refresh_recruiter_job_candidates(
    job_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Re-trigger candidate matching for a recruiter job (SSE with progress)."""
    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    # Capture values needed for the generator (session will be closed)
    the_job_id = job.id

    def _generate():
        import json as _json

        from app.db.session import get_session_factory
        from app.models.recruiter import RecruiterProfile as RP
        from app.models.recruiter_job import RecruiterJob as RJ
        from app.models.recruiter_job_candidate import (
            RecruiterJobCandidate as RJC,
        )
        from app.services.matching import (
            find_top_candidates_for_recruiter_job,
        )

        db = get_session_factory()()
        try:
            rj = db.execute(select(RJ).where(RJ.id == the_job_id)).scalar_one_or_none()
            if not rj:
                msg = _json.dumps(
                    {"percent": 100, "phase": "error", "message": "Job not found"}
                )
                yield f"data: {msg}\n\n"
                return

            # Generate embedding if missing (backfill existing jobs)
            if rj.embedding is None:
                try:
                    from app.services.embedding import generate_embedding

                    text = (
                        f"Job Title: {rj.title}\n"
                        f"Company: {rj.client_company_name or ''}\n"
                        f"Description: {(rj.description or '')[:2000]}\n"
                        f"Requirements: {(rj.requirements or '')[:1000]}\n"
                        f"Location: {rj.location or ''}"
                    )
                    rj.embedding = generate_embedding(text)
                    db.commit()
                except Exception:
                    logger.debug("Failed to generate embedding for job %s", the_job_id)

            msg = _json.dumps(
                {
                    "percent": 5,
                    "phase": "loading",
                    "message": "Loading candidate profiles...",
                }
            )
            yield f"data: {msg}\n\n"

            # Count eligible candidates (platform + sourced)
            rp = db.execute(
                select(RP).where(RP.id == rj.recruiter_profile_id)
            ).scalar_one()
            latest_sub = (
                select(
                    CandidateProfile.user_id,
                    func.max(CandidateProfile.version).label("max_version"),
                )
                .where(CandidateProfile.user_id.is_not(None))
                .group_by(CandidateProfile.user_id)
            ).subquery()
            platform_count = (
                db.execute(
                    select(func.count()).select_from(
                        select(CandidateProfile.id)
                        .join(
                            latest_sub,
                            (CandidateProfile.user_id == latest_sub.c.user_id)
                            & (CandidateProfile.version == latest_sub.c.max_version),
                        )
                        .where(
                            CandidateProfile.open_to_opportunities == True,  # noqa: E712
                            CandidateProfile.profile_visibility.in_(
                                ["public", "anonymous"]
                            ),
                        )
                        .subquery()
                    )
                ).scalar()
                or 0
            )
            sourced_count = (
                db.execute(
                    select(func.count(CandidateProfile.id)).where(
                        CandidateProfile.user_id.is_(None),
                        cast(
                            CandidateProfile.profile_json["sourced_by_user_id"],
                            String,
                        )
                        == str(rp.user_id),
                    )
                ).scalar()
                or 0
            )
            total_profiles = platform_count + sourced_count

            msg = _json.dumps(
                {
                    "percent": 10,
                    "phase": "scoring",
                    "message": f"Scoring {total_profiles} candidates...",
                }
            )
            yield f"data: {msg}\n\n"

            # Run matching (this is the heavy part)
            results = find_top_candidates_for_recruiter_job(
                db, rj, rp.user_id, limit=100
            )

            msg = _json.dumps(
                {
                    "percent": 80,
                    "phase": "saving",
                    "message": f"Found {len(results)} matches, saving...",
                }
            )
            yield f"data: {msg}\n\n"

            # Delete old cached rows
            from sqlalchemy import delete as sa_delete

            db.execute(sa_delete(RJC).where(RJC.recruiter_job_id == the_job_id))

            inserted = 0
            for r in results:
                if r["match_score"] <= 50:
                    continue
                db.add(
                    RJC(
                        recruiter_job_id=the_job_id,
                        candidate_profile_id=r["id"],
                        match_score=r["match_score"],
                        matched_skills=r.get("matched_skills"),
                    )
                )
                inserted += 1

            db.commit()

            msg = _json.dumps(
                {"percent": 90, "phase": "pipeline", "message": "Updating pipeline..."}
            )
            yield f"data: {msg}\n\n"

            # Auto-populate pipeline if recruiter setting is enabled
            pipeline_added = 0
            try:
                from app.models.recruiter import RecruiterProfile as RP
                from app.models.recruiter_pipeline_candidate import (
                    RecruiterPipelineCandidate,
                )

                recruiter_profile = db.execute(
                    select(RP).where(RP.id == rj.recruiter_profile_id)
                ).scalar_one_or_none()

                if recruiter_profile and recruiter_profile.auto_populate_pipeline:
                    cached = (
                        db.execute(
                            select(RJC).where(RJC.recruiter_job_id == the_job_id)
                        )
                        .scalars()
                        .all()
                    )
                    for rjc in cached:
                        exists = db.execute(
                            select(RecruiterPipelineCandidate.id).where(
                                RecruiterPipelineCandidate.recruiter_profile_id
                                == recruiter_profile.id,
                                RecruiterPipelineCandidate.candidate_profile_id
                                == rjc.candidate_profile_id,
                            )
                        ).scalar_one_or_none()
                        if not exists:
                            db.add(
                                RecruiterPipelineCandidate(
                                    recruiter_profile_id=recruiter_profile.id,
                                    recruiter_job_id=the_job_id,
                                    candidate_profile_id=rjc.candidate_profile_id,
                                    source="auto-match",
                                    stage="sourced",
                                    match_score=rjc.match_score,
                                )
                            )
                            pipeline_added += 1
                    if pipeline_added:
                        db.commit()
            except Exception:
                logger.warning("Auto-populate pipeline failed for job %s", the_job_id)

            msg = _json.dumps(
                {
                    "percent": 100,
                    "phase": "done",
                    "message": f"{inserted} candidates matched",
                    "inserted": inserted,
                    "pipeline_added": pipeline_added,
                }
            )
            yield f"data: {msg}\n\n"

        except Exception as exc:
            logger.exception("Refresh streaming failed for job %s", the_job_id)
            msg = _json.dumps({"percent": 100, "phase": "error", "message": str(exc)})
            yield f"data: {msg}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# INTELLIGENCE — briefs, salary, career trajectory, market position
# ============================================================================


@router.post("/briefs")
def generate_brief(
    candidate_profile_id: int = Query(...),
    brief_type: str = Query("general"),
    job_id: int | None = Query(None),
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Generate an AI candidate brief.

    brief_type: general | job_specific | submittal
    Enforces monthly brief limit per recruiter tier.
    """
    from app.services.billing import (
        check_recruiter_monthly_limit,
        increment_recruiter_counter,
    )
    from app.services.career_intelligence import generate_candidate_brief

    try:
        check_recruiter_monthly_limit(
            profile,
            "candidate_briefs_used",
            "candidate_briefs_per_month",
            session,
        )

        if brief_type not in ("general", "job_specific", "submittal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="brief_type must be general, job_specific, or submittal.",
            )

        result = generate_candidate_brief(
            candidate_profile_id=candidate_profile_id,
            employer_job_id=job_id,
            brief_type=brief_type,
            user_id=user.id,
            db=session,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Brief generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    increment_recruiter_counter(profile, "candidate_briefs_used", session)
    return result


@router.get("/salary-roles")
def salary_roles() -> list[str]:
    """Return searchable role titles for salary autocomplete (no auth required)."""
    from app.services.salary_reference import get_supported_roles

    return get_supported_roles()


@router.get("/salary-intelligence")
def salary_lookup(
    role: str = Query(...),
    location: str | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Look up salary percentiles for a role/location.

    Enforces monthly salary lookup limit per recruiter tier.
    """
    from app.services.billing import (
        check_recruiter_monthly_limit,
        increment_recruiter_counter,
    )
    from app.services.career_intelligence import salary_intelligence

    check_recruiter_monthly_limit(
        profile,
        "salary_lookups_used",
        "salary_lookups_per_month",
        session,
    )

    result = salary_intelligence(role_title=role, location=location, db=session)
    increment_recruiter_counter(profile, "salary_lookups_used", session)
    return result


@router.get("/time-to-fill/{job_id}")
def recruiter_time_to_fill(
    job_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Predict time-to-fill for a recruiter job order."""
    from app.services.career_intelligence import predict_time_to_fill

    # Verify the recruiter owns this job
    rj = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if not rj:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        return predict_time_to_fill(recruiter_job_id=job_id, db=session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/career-trajectory/{candidate_profile_id}")
def career_trajectory(
    candidate_profile_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Predict career trajectory for a candidate profile."""
    from app.services.career_intelligence import predict_career_trajectory

    return predict_career_trajectory(
        candidate_profile_id=candidate_profile_id,
        db=session,
    )


@router.get("/market-position/{candidate_profile_id}/{job_id}")
def market_position(
    candidate_profile_id: int,
    job_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Compute candidate's percentile position among matches for a job."""
    from app.services.career_intelligence import compute_market_position

    return compute_market_position(
        candidate_profile_id=candidate_profile_id,
        employer_job_id=job_id,
        db=session,
    )


@router.get("/intelligence/usage")
def intelligence_usage(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Return current usage vs limits for intelligence features."""
    from app.services.billing import (
        _maybe_reset_recruiter_counters,
        get_recruiter_limit,
        get_recruiter_tier,
    )

    _maybe_reset_recruiter_counters(profile, session)
    tier = get_recruiter_tier(profile)
    return {
        "tier": tier,
        "briefs": {
            "used": profile.candidate_briefs_used or 0,
            "limit": get_recruiter_limit(tier, "candidate_briefs_per_month"),
        },
        "salary_lookups": {
            "used": profile.salary_lookups_used or 0,
            "limit": get_recruiter_limit(tier, "salary_lookups_per_month"),
        },
        "smart_job_parsing": {
            "used": profile.job_uploads_used or 0,
            "limit": get_recruiter_limit(tier, "smart_job_parsing_per_month"),
        },
    }


# ============================================================================
# BULK OUTREACH (team/agency only)
# ============================================================================


@router.post("/outreach/bulk")
def bulk_outreach(
    candidate_ids: list[int] = Query(...),
    message_template: str = Query(...),
    subject: str = Query("Opportunity from recruiter"),
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Send bulk outreach to multiple pipeline candidates.

    Restricted to team/agency tiers only.
    """
    from app.services.billing import get_recruiter_tier
    from app.services.recruiter_service import log_activity

    tier = get_recruiter_tier(profile)
    if tier not in ("team", "agency", "trial"):
        raise HTTPException(
            status_code=403,
            detail="Bulk outreach requires a Team or Agency plan.",
        )

    if len(candidate_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 candidates per batch.",
        )

    results = []
    for cid in candidate_ids:
        # Log activity for each candidate
        try:
            log_activity(
                session,
                profile,
                user.id,
                {
                    "activity_type": "bulk_outreach",
                    "pipeline_candidate_id": cid,
                    "subject": subject,
                    "body": message_template[:500],
                },
            )
            results.append({"candidate_id": cid, "status": "queued"})
        except Exception as exc:
            logger.warning("Failed to log outreach for candidate %d: %s", cid, exc)
            results.append({"candidate_id": cid, "status": "failed", "error": str(exc)})

    return {
        "total": len(candidate_ids),
        "queued": sum(1 for r in results if r["status"] == "queued"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }


# ============================================================================
# HELPERS
# ============================================================================


def _enqueue_recruiter_job_sync(job_id: int) -> None:
    """Enqueue sync + candidate population for an active recruiter job."""
    try:
        from app.services.job_pipeline import (
            populate_recruiter_job_candidates,
            sync_recruiter_job_to_jobs,
        )
        from app.services.queue import get_queue

        q = get_queue()
        q.enqueue(sync_recruiter_job_to_jobs, job_id)
        q.enqueue(populate_recruiter_job_candidates, job_id)
    except Exception:
        logger.debug("Failed to enqueue background jobs for recruiter job %s", job_id)


def _profile_to_candidate_result(
    cp: CandidateProfile, match: RecruiterJobCandidate, *, in_pipeline: bool = False
) -> RecruiterJobCandidateResult:
    """Convert a CandidateProfile + match cache row to a response."""
    pj = cp.profile_json or {}
    basics = pj.get("basics") or {}
    skills = pj.get("skills") or []
    visibility = cp.profile_visibility or "public"

    first = basics.get("first_name") or ""
    last = basics.get("last_name") or ""
    name = basics.get("name") or f"{first} {last}".strip()
    if not name:
        name = f"Candidate {cp.id}"
    if visibility == "anonymous":
        name = f"Candidate {cp.id}"

    headline = None
    experience = pj.get("experience") or []
    if experience and isinstance(experience[0], dict):
        title = experience[0].get("title") or ""
        company = experience[0].get("company") or ""
        if title:
            headline = f"{title} at {company}" if company else title

    return RecruiterJobCandidateResult(
        id=cp.id,
        name=name,
        headline=headline,
        location=basics.get("location"),
        years_experience=basics.get("total_years_experience"),
        top_skills=skills[:5] if isinstance(skills, list) else [],
        matched_skills=match.matched_skills or [],
        match_score=match.match_score,
        profile_visibility=visibility,
        in_pipeline=in_pipeline,
    )


# ---------------------------------------------------------------------------
# Introduction Requests (recruiter-side)
# ---------------------------------------------------------------------------


@router.post("/introductions", response_model=IntroductionRequestResponse)
def create_introduction(
    payload: IntroductionRequestCreate,
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
):
    """Send an introduction request to a candidate (tier-limited)."""
    from app.services.introductions import create_introduction_request

    profile = get_recruiter_profile(user, session)
    intro = create_introduction_request(
        session=session,
        recruiter_profile=profile,
        candidate_profile_id=payload.candidate_profile_id,
        message=payload.message,
        recruiter_job_id=payload.recruiter_job_id,
    )
    session.commit()
    return intro


@router.get("/introductions", response_model=list[IntroductionRequestResponse])
def list_introductions(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
):
    """List introduction requests sent by this recruiter."""
    from app.services.introductions import get_recruiter_introductions

    profile = get_recruiter_profile(user, session)
    return get_recruiter_introductions(
        session=session,
        recruiter_profile_id=profile.id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.get("/introductions/{intro_id}", response_model=IntroductionRequestResponse)
def get_introduction(
    intro_id: int,
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
):
    """Get a single introduction request detail."""
    from app.models.introduction_request import IntroductionRequest
    from app.services.introductions import _enrich_for_recruiter

    profile = get_recruiter_profile(user, session)
    intro = session.execute(
        select(IntroductionRequest).where(
            IntroductionRequest.id == intro_id,
            IntroductionRequest.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if intro is None:
        raise HTTPException(status_code=404, detail="Introduction request not found.")
    return _enrich_for_recruiter(session, intro)


@router.get("/introduction-usage")
def get_introduction_usage(
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
):
    """Get recruiter's introduction request usage for the current billing period."""
    from app.services.billing import (
        _maybe_reset_recruiter_counters,
        get_recruiter_limit,
        get_recruiter_tier,
    )

    profile = get_recruiter_profile(user, session)
    _maybe_reset_recruiter_counters(profile, session)
    tier = get_recruiter_tier(profile)
    limit = get_recruiter_limit(tier, "intro_requests_per_month")
    return {
        "used": profile.intro_requests_used or 0,
        "limit": limit,
        "tier": tier,
    }


# ============================================================================
# CROSS-SEGMENT JOB LINKING
# ============================================================================


@router.patch("/jobs/{job_id}/link-employer-job")
def link_employer_job(
    job_id: int,
    employer_job_id: int | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Manually link or unlink a recruiter job to/from an employer job."""
    from app.services.job_linking import manual_link_recruiter_job

    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    try:
        manual_link_recruiter_job(session, job, employer_job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    session.commit()
    return {
        "message": "linked" if employer_job_id else "unlinked",
        "employer_job_id": employer_job_id,
    }


@router.patch("/jobs/{job_id}/link-upstream-job")
def link_upstream_job(
    job_id: int,
    upstream_job_id: int | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Link or unlink a Sub's job to/from a Prime's recruiter job."""
    from app.services.job_linking import link_upstream_recruiter_job

    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    try:
        link_upstream_recruiter_job(session, job, upstream_job_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    session.commit()
    return {
        "message": "linked" if upstream_job_id else "unlinked",
        "upstream_recruiter_job_id": upstream_job_id,
    }


# ============================================================================
# CANDIDATE SUBMISSIONS
# ============================================================================


@router.get("/submission-check")
def check_submission_duplicate(
    candidate_profile_id: int = Query(...),
    recruiter_job_id: int = Query(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Check if a candidate was already submitted to this job."""
    from app.services.submission import check_duplicate_submission

    return check_duplicate_submission(
        session,
        candidate_profile_id=candidate_profile_id,
        recruiter_job_id=recruiter_job_id,
    )


@router.post(
    "/submissions",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    data: dict,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Submit a candidate to an employer job."""
    from app.schemas.submission import CandidateSubmissionCreate
    from app.services.submission import submit_candidate

    body = CandidateSubmissionCreate(**data)

    try:
        submission, is_first = submit_candidate(
            session,
            recruiter_profile_id=profile.id,
            recruiter_job_id=body.recruiter_job_id,
            candidate_profile_id=body.candidate_profile_id,
            pipeline_candidate_id=body.pipeline_candidate_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    session.commit()
    session.refresh(submission)

    return {
        "id": submission.id,
        "recruiter_job_id": submission.recruiter_job_id,
        "candidate_profile_id": submission.candidate_profile_id,
        "employer_job_id": submission.employer_job_id,
        "is_first_submission": is_first,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat()
        if submission.submitted_at
        else None,
    }


@router.get("/submissions")
def list_submissions(
    job_id: int | None = Query(None),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[dict]:
    """List submissions by this recruiter."""
    from app.services.submission import get_submissions_by_recruiter

    subs = get_submissions_by_recruiter(session, profile.id, recruiter_job_id=job_id)
    results = []
    for s in subs:
        job_title = None
        if s.employer_job_id and s.employer_job:
            job_title = s.employer_job.title
        elif s.external_job_title:
            job_title = s.external_job_title
        else:
            job_title = s.recruiter_job.title if s.recruiter_job else None

        candidate_name = _resolve_submission_candidate_name(session, s)

        results.append(
            {
                "id": s.id,
                "recruiter_job_id": s.recruiter_job_id,
                "employer_job_id": s.employer_job_id,
                "candidate_profile_id": s.candidate_profile_id,
                "candidate_name": candidate_name,
                "job_title": job_title,
                "status": s.status,
                "is_first_submission": s.is_first_submission,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "employer_notes": s.employer_notes,
            }
        )
    return results


@router.get("/jobs/{job_id}/submission-check/{candidate_id}")
def check_submission(
    job_id: int,
    candidate_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Pre-submit check: is this candidate already submitted for this job?"""
    from app.services.billing import check_recruiter_feature
    from app.services.submission import (
        check_candidate_submitted,
        check_own_submissions,
    )

    job = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    # Solo tier: only check own submissions (no cross-vendor intelligence)
    if not check_recruiter_feature(profile, "cross_vendor_duplicate_check"):
        own = check_own_submissions(session, profile.id, job.id, candidate_id)
        return {
            "already_submitted": bool(own),
            "submission_count": len(own),
            "first_submitted_at": own[0].submitted_at.isoformat()
            if own and own[0].submitted_at
            else None,
            "first_submitted_by": "you" if own else None,
            "upgrade_for_cross_vendor": True,
        }

    existing = check_candidate_submitted(session, job.employer_job_id, candidate_id)
    if not existing:
        return {
            "already_submitted": False,
            "submission_count": 0,
            "first_submitted_at": None,
            "first_submitted_by": None,
        }

    first = existing[0]
    # Redact vendor name for other recruiters
    if first.recruiter_profile_id == profile.id:
        submitted_by = "you"
    else:
        submitted_by = "another vendor"

    return {
        "already_submitted": True,
        "submission_count": len(existing),
        "first_submitted_at": first.submitted_at.isoformat()
        if first.submitted_at
        else None,
        "first_submitted_by": submitted_by,
    }


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_submission(
    submission_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> None:
    """Withdraw a submission (recruiter can only withdraw their own)."""
    from app.models.candidate_submission import CandidateSubmission

    sub = session.execute(
        select(CandidateSubmission).where(
            CandidateSubmission.id == submission_id,
            CandidateSubmission.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )
    sub.status = "withdrawn"
    session.commit()


def _resolve_submission_candidate_name(session: Session, submission) -> str:
    """Resolve candidate name for a submission."""
    if submission.candidate_profile_id:
        cp = session.get(CandidateProfile, submission.candidate_profile_id)
        if cp:
            pj = cp.profile_json or {}
            basics = pj.get("basics") or {}
            first = basics.get("first_name", "")
            last = basics.get("last_name", "")
            name = basics.get("name") or f"{first} {last}".strip()
            if name:
                return name
    return f"Candidate #{submission.candidate_profile_id}"
