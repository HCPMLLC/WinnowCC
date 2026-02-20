"""Recruiter API: profile, CRM clients, pipeline, activities, team, jobs, dashboard."""

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, func, or_, select
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
    ResumeUploadFileResult,
    ResumeUploadResponse,
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
    RecruiterJobCandidateResult,
    RecruiterJobCandidatesResponse,
    RecruiterJobCreate,
    RecruiterJobResponse,
    RecruiterJobUpdate,
)
from app.schemas.introduction import (
    IntroductionRequestCreate,
    IntroductionRequestResponse,
)
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
        "trial_days_remaining": profile.trial_days_remaining if tier == "trial" else None,
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
    from app.services.billing import get_recruiter_limit, get_recruiter_tier
    from app.services.recruiter_service import create_client as svc_create
    from app.services.recruiter_service import get_client_job_count

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
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[RecruiterClientResponse]:
    """List all clients for this recruiter."""
    from app.services.recruiter_service import get_client_job_count
    from app.services.recruiter_service import list_clients as svc_list

    clients = svc_list(session, profile, status_filter)
    results = []
    for c in clients:
        resp = RecruiterClientResponse.model_validate(c, from_attributes=True)
        resp.job_count = get_client_job_count(session, c.id)
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


@router.put("/clients/{client_id}", response_model=RecruiterClientResponse)
def update_client(
    client_id: int,
    data: RecruiterClientUpdate,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> RecruiterClientResponse:
    """Update a client company."""
    from app.services.recruiter_service import get_client_job_count
    from app.services.recruiter_service import update_client as svc_update

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


@router.get("/pipeline", response_model=list[PipelineCandidateResponse])
def list_pipeline(
    stage: str | None = Query(None),
    job_id: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> list[PipelineCandidateResponse]:
    """List pipeline candidates with optional filters."""
    from app.models.candidate_profile import CandidateProfile
    from app.services.recruiter_service import list_pipeline as svc_list
    from app.services.recruiter_service import resolve_candidate_name

    pcs = svc_list(
        session, profile, stage=stage, job_id=job_id,
        search=search, limit=limit, offset=offset,
    )
    # Batch-load linked profiles to avoid N+1 queries
    cp_ids = [pc.candidate_profile_id for pc in pcs if pc.candidate_profile_id]
    profiles_map: dict[int, dict] = {}
    if cp_ids:
        cps = session.execute(
            select(CandidateProfile).where(CandidateProfile.id.in_(cp_ids))
        ).scalars().all()
        for cp in cps:
            pj = cp.profile_json or {}
            basics = pj.get("basics") or {}
            skills_raw = pj.get("skills") or basics.get("top_skills") or []
            skills = [
                (s if isinstance(s, str) else s.get("name", ""))
                for s in skills_raw
            ]
            is_platform = not pj.get("sourced_by_user_id") and pj.get("source") != "linkedin_extension"
            # Derive headline from experience if not set
            headline = pj.get("headline") or (basics.get("target_titles") or [None])[0]
            current_company = pj.get("current_company")
            if not headline or not current_company:
                exp = pj.get("experience") or []
                if exp and isinstance(exp[0], dict):
                    if not headline:
                        title = exp[0].get("title") or ""
                        company = exp[0].get("company") or ""
                        headline = f"{title} at {company}".strip(" at ") if title else company
                    if not current_company:
                        current_company = exp[0].get("company")
            profiles_map[cp.id] = {
                "headline": headline,
                "location": pj.get("location") or basics.get("location"),
                "current_company": current_company,
                "skills": [s for s in skills if s][:10],
                "linkedin_url": pj.get("linkedin_url"),
                "is_platform_candidate": is_platform,
            }
    results = []
    for pc in pcs:
        resp = PipelineCandidateResponse.model_validate(pc, from_attributes=True)
        resp.candidate_name = resolve_candidate_name(session, pc)
        if pc.candidate_profile_id and pc.candidate_profile_id in profiles_map:
            info = profiles_map[pc.candidate_profile_id]
            resp.headline = info["headline"]
            resp.location = info["location"]
            resp.current_company = info["current_company"]
            resp.skills = info["skills"]
            resp.linkedin_url = info["linkedin_url"]
            resp.is_platform_candidate = info["is_platform_candidate"]
        results.append(resp)
    return results


@router.post(
    "/pipeline/upload-resumes",
    response_model=ResumeUploadResponse,
)
async def upload_pipeline_resumes(
    files: list[UploadFile] = File(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
):
    """Upload resume files to parse and link to pipeline candidates.

    Each resume is parsed, the email is extracted, and matched against
    existing pipeline contacts by email. Creates CandidateProfile and
    ResumeDocument records and links them to the pipeline entry.
    """
    import hashlib

    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
    from app.models.resume_document import ResumeDocument
    from app.services.billing import (
        check_recruiter_monthly_limit,
        get_recruiter_limit,
        get_recruiter_tier,
        increment_recruiter_counter,
    )
    from app.services.profile_parser import extract_text, parse_profile_from_text

    tier = get_recruiter_tier(profile)

    # Enforce monthly quota (resets counters if needed)
    check_recruiter_monthly_limit(
        profile, "resume_imports_used", "resume_imports_per_month", session,
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

    upload_dir = Path("data/uploads/recruiter_resumes")
    upload_dir.mkdir(parents=True, exist_ok=True)

    results: list[ResumeUploadFileResult] = []
    succeeded = 0
    matched = 0
    new_count = 0
    linked_platform = 0

    for i, upload_file in enumerate(files):
        filename = upload_file.filename or f"file_{i}"
        tmp_path: str | None = None

        try:
            # Validate file type
            if not filename.lower().endswith((".pdf", ".doc", ".docx")):
                results.append(
                    ResumeUploadFileResult(
                        filename=filename,
                        success=False,
                        status="failed",
                        error="Unsupported file type. Use .pdf, .doc, or .docx.",
                    )
                )
                continue

            # Validate file size (10 MB)
            contents = await upload_file.read()
            if len(contents) > 10 * 1024 * 1024:
                results.append(
                    ResumeUploadFileResult(
                        filename=filename,
                        success=False,
                        status="failed",
                        error="File too large. Maximum size is 10 MB.",
                    )
                )
                continue

            # Write to temp file and process
            ext = Path(filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name

            # 1. Extract text
            text = extract_text(Path(tmp_path))
            if not text or len(text.strip()) < 20:
                results.append(
                    ResumeUploadFileResult(
                        filename=filename,
                        success=False,
                        status="failed",
                        error="Could not extract meaningful text from file.",
                    )
                )
                continue

            # 2. Parse profile
            profile_json = parse_profile_from_text(text)

            # 3. Extract email and name from parsed profile
            basics = profile_json.get("basics", {})
            parsed_email = basics.get("email")
            parsed_name = basics.get("name")

            # 4. Save resume file to permanent location
            file_hash = hashlib.sha256(contents).hexdigest()
            dest_filename = f"{file_hash[:16]}_{filename}"
            dest_path = upload_dir / dest_filename
            dest_path.write_bytes(contents)

            # 5. Create ResumeDocument record
            resume_doc = ResumeDocument(
                user_id=None,
                filename=filename,
                path=str(dest_path),
                sha256=file_hash,
            )
            session.add(resume_doc)
            session.flush()

            # 6. Create CandidateProfile record
            profile_json["source"] = "recruiter_resume_upload"
            profile_json["sourced_by_user_id"] = profile.user_id
            new_cp = CandidateProfile(
                user_id=None,
                resume_document_id=resume_doc.id,
                version=1,
                profile_json=profile_json,
                profile_visibility="private",
                open_to_opportunities=False,
            )
            session.add(new_cp)
            session.flush()

            # 7. Match by email (3-way resolution)
            result_status = "new"
            pipeline_candidate_id = None

            if parsed_email:
                parsed_email_lower = parsed_email.strip().lower()

                # Check platform users first
                platform_user = session.execute(
                    select(User).where(
                        func.lower(User.email) == parsed_email_lower
                    )
                ).scalar_one_or_none()

                if platform_user:
                    # Link to their latest CandidateProfile
                    existing_cp = session.execute(
                        select(CandidateProfile)
                        .where(CandidateProfile.user_id == platform_user.id)
                        .order_by(CandidateProfile.id.desc())
                    ).scalar_one_or_none()

                    if existing_cp:
                        linked_cp_id = existing_cp.id
                    else:
                        linked_cp_id = new_cp.id

                    # Find or create pipeline entry
                    pipeline_entry = session.execute(
                        select(RecruiterPipelineCandidate).where(
                            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                            func.lower(RecruiterPipelineCandidate.external_email) == parsed_email_lower,
                        )
                    ).scalar_one_or_none()

                    if pipeline_entry:
                        pipeline_entry.candidate_profile_id = linked_cp_id
                    else:
                        pipeline_entry = RecruiterPipelineCandidate(
                            recruiter_profile_id=profile.id,
                            candidate_profile_id=linked_cp_id,
                            external_name=parsed_name,
                            external_email=parsed_email,
                            source="recruiter_resume_upload",
                            stage="sourced",
                        )
                        session.add(pipeline_entry)
                        session.flush()

                    pipeline_candidate_id = pipeline_entry.id
                    result_status = "linked_platform"
                    linked_platform += 1
                else:
                    # Check pipeline entries by email
                    pipeline_entry = session.execute(
                        select(RecruiterPipelineCandidate).where(
                            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                            func.lower(RecruiterPipelineCandidate.external_email) == parsed_email_lower,
                        )
                    ).scalar_one_or_none()

                    if pipeline_entry:
                        pipeline_entry.candidate_profile_id = new_cp.id
                        pipeline_candidate_id = pipeline_entry.id
                        result_status = "matched"
                        matched += 1
                    else:
                        # Create new pipeline entry
                        pipeline_entry = RecruiterPipelineCandidate(
                            recruiter_profile_id=profile.id,
                            candidate_profile_id=new_cp.id,
                            external_name=parsed_name,
                            external_email=parsed_email,
                            source="recruiter_resume_upload",
                            stage="sourced",
                        )
                        session.add(pipeline_entry)
                        session.flush()
                        pipeline_candidate_id = pipeline_entry.id
                        result_status = "new"
                        new_count += 1
            else:
                # No email found — create new pipeline entry with name only
                pipeline_entry = RecruiterPipelineCandidate(
                    recruiter_profile_id=profile.id,
                    candidate_profile_id=new_cp.id,
                    external_name=parsed_name or filename,
                    source="recruiter_resume_upload",
                    stage="sourced",
                )
                session.add(pipeline_entry)
                session.flush()
                pipeline_candidate_id = pipeline_entry.id
                result_status = "new"
                new_count += 1

            # 8. Increment usage counter
            increment_recruiter_counter(profile, "resume_imports_used", session)

            results.append(
                ResumeUploadFileResult(
                    filename=filename,
                    success=True,
                    status=result_status,
                    pipeline_candidate_id=pipeline_candidate_id,
                    candidate_profile_id=new_cp.id,
                    matched_email=parsed_email,
                    parsed_name=parsed_name,
                )
            )
            succeeded += 1

        except Exception as exc:
            logger.exception("Error processing resume upload: %s", filename)
            session.rollback()
            results.append(
                ResumeUploadFileResult(
                    filename=filename,
                    success=False,
                    status="failed",
                    error=f"Processing error: {exc}",
                )
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    session.commit()

    # Calculate remaining quota
    monthly_limit_val = get_recruiter_limit(tier, "resume_imports_per_month")
    current_used_after = profile.resume_imports_used or 0
    remaining = (
        max(0, int(monthly_limit_val) - current_used_after)
        if isinstance(monthly_limit_val, int) and monthly_limit_val < 999
        else 999
    )

    upgrade_recommendation = None
    if tier in ("trial", "solo") and succeeded > 0:
        upgrade_recommendation = (
            f"Upgrade from {tier.capitalize()} to unlock higher batch "
            "and monthly limits for resume imports."
        )

    total_failed = len(results) - succeeded
    return ResumeUploadResponse(
        results=results,
        total_submitted=len(files),
        total_succeeded=succeeded,
        total_failed=total_failed,
        total_matched=matched,
        total_new=new_count,
        total_linked_platform=linked_platform,
        remaining_monthly_quota=remaining,
        upgrade_recommendation=upgrade_recommendation,
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
    from app.services.recruiter_service import bulk_update_pipeline_stage as svc_bulk_stage

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

    pc = svc_update(
        session, profile, candidate_id, data.model_dump(exclude_unset=True)
    )
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
    from datetime import datetime, timedelta, timezone

    from app.services.billing import get_recruiter_limit, get_recruiter_tier
    from app.services.recruiter_service import list_activities

    tier = get_recruiter_tier(profile)
    crm_level = get_recruiter_limit(tier, "client_crm")

    since = None
    if crm_level == "basic":
        since = datetime.now(timezone.utc) - timedelta(days=7)

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
                cast(
                    CandidateProfile.profile_json["sourced_by_user_id"], String
                ) == str(user.id),
                cast(
                    CandidateProfile.profile_json["source"], String
                ).ilike("%linkedin_extension%"),
            )
        )
        .order_by(CandidateProfile.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    profiles = session.execute(stmt).scalars().all()

    candidates = []
    for p in profiles:
        pj = p.profile_json or {}
        candidates.append(
            {
                "candidate_profile_id": p.id,
                "profile_json": pj,
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
                cast(
                    CandidateProfile.profile_json["sourced_by_user_id"], String
                ) == str(user.id),
                cast(
                    CandidateProfile.profile_json["source"], String
                ).ilike("%linkedin_extension%"),
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
        session.execute(
            select(CandidateProfile).where(CandidateProfile.id.in_(ids))
        )
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
            select(RecruiterPipelineCandidate.id).where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                RecruiterPipelineCandidate.candidate_profile_id == candidate_profile_id,
            ).limit(1)
        ).scalar_one_or_none()
        allowed = in_pipeline is not None

    # Allow if candidate is in any of recruiter's job candidates
    if not allowed:
        from app.models.recruiter_job_candidate import RecruiterJobCandidate
        from app.models.recruiter_job import RecruiterJob
        in_job = session.execute(
            select(RecruiterJobCandidate.id)
            .join(RecruiterJob, RecruiterJob.id == RecruiterJobCandidate.recruiter_job_id)
            .where(
                RecruiterJob.recruiter_profile_id == profile.id,
                RecruiterJobCandidate.candidate_profile_id == candidate_profile_id,
            ).limit(1)
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

    job = RecruiterJob(
        recruiter_profile_id=profile.id, **job_data.model_dump()
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # Sync to candidate-facing jobs table and pre-compute candidates
    if job.status == "active":
        _enqueue_recruiter_job_sync(job.id)

    resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = 0
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
        profile, "job_uploads_used", "smart_job_parsing_per_month", session,
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
                description=parsed.get("description", ""),
                requirements=parsed.get("requirements"),
                nice_to_haves=parsed.get("nice_to_haves"),
                location=parsed.get("location"),
                remote_policy=parsed.get("remote_policy"),
                employment_type=parsed.get("employment_type"),
                salary_min=parsed.get("salary_min"),
                salary_max=parsed.get("salary_max"),
                salary_currency=parsed.get("salary_currency") or "USD",
                department=parsed.get("department"),
                application_email=parsed.get("application_email"),
                application_url=parsed.get("application_url"),
                start_at=start_at,
                closes_at=closes_at,
                status="draft",
            )
            session.add(job)
            session.flush()

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


@router.get("/jobs", response_model=list[RecruiterJobResponse])
def list_recruiter_jobs(
    status_filter: str | None = Query(None, alias="status"),
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
        allowed = ("draft", "active", "paused", "closed")
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(allowed)}",
            )
        stmt = stmt.where(RecruiterJob.status == status_filter)

    stmt = stmt.order_by(RecruiterJob.created_at.desc())

    rows = session.execute(stmt).all()
    results = []
    for job, count in rows:
        resp = RecruiterJobResponse.model_validate(job, from_attributes=True)
        resp.matched_candidates_count = count or 0
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
                logger.debug("Failed to enqueue deactivate for recruiter job %s", job.id)

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
    """Update a recruiter job posting. If status changes to 'active', syncs to jobs table."""
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

    content_fields = {"title", "description", "requirements", "salary_min", "salary_max", "location"}
    content_changed = bool(update_data.keys() & content_fields)

    for field, value in update_data.items():
        setattr(job, field, value)
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
        rows = session.execute(
            select(RecruiterPipelineCandidate.candidate_profile_id).where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                RecruiterPipelineCandidate.candidate_profile_id.in_(cached_cp_ids),
            )
        ).scalars().all()
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
    the_profile_id = profile.id

    def _generate():
        import json as _json

        from app.db.session import get_session_factory
        from app.models.recruiter_job import RecruiterJob as RJ
        from app.models.recruiter_job_candidate import (
            RecruiterJobCandidate as RJC,
        )
        from app.services.matching import (
            find_top_candidates_for_employer_job,
        )
        from app.services.skill_synonyms import get_canonical  # noqa: F401

        db = get_session_factory()()
        try:
            rj = db.execute(
                select(RJ).where(RJ.id == the_job_id)
            ).scalar_one_or_none()
            if not rj:
                yield f"data: {_json.dumps({'percent': 100, 'phase': 'error', 'message': 'Job not found'})}\n\n"
                return

            yield f"data: {_json.dumps({'percent': 5, 'phase': 'loading', 'message': 'Loading candidate profiles...'})}\n\n"

            # Count eligible candidates first
            latest_sub = (
                select(
                    CandidateProfile.user_id,
                    func.max(CandidateProfile.version).label("max_version"),
                )
                .where(CandidateProfile.user_id.is_not(None))
                .group_by(CandidateProfile.user_id)
            ).subquery()
            total_profiles = db.execute(
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
            ).scalar() or 0

            yield f"data: {_json.dumps({'percent': 10, 'phase': 'scoring', 'message': f'Scoring {total_profiles} candidates...'})}\n\n"

            # Run matching (this is the heavy part)
            results = find_top_candidates_for_employer_job(db, rj, limit=100)

            yield f"data: {_json.dumps({'percent': 80, 'phase': 'saving', 'message': f'Found {len(results)} matches, saving...'})}\n\n"

            # Delete old cached rows
            from sqlalchemy import delete as sa_delete

            db.execute(
                sa_delete(RJC).where(RJC.recruiter_job_id == the_job_id)
            )

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

            yield f"data: {_json.dumps({'percent': 90, 'phase': 'pipeline', 'message': 'Updating pipeline...'})}\n\n"

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

            yield f"data: {_json.dumps({'percent': 100, 'phase': 'done', 'message': f'{inserted} candidates matched', 'inserted': inserted, 'pipeline_added': pipeline_added})}\n\n"

        except Exception as exc:
            logger.exception("Refresh streaming failed for job %s", the_job_id)
            yield f"data: {_json.dumps({'percent': 100, 'phase': 'error', 'message': str(exc)})}\n\n"
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
            profile, "candidate_briefs_used", "candidate_briefs_per_month", session,
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
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Brief generation failed")
        raise HTTPException(status_code=500, detail=str(exc))
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
        profile, "salary_lookups_used", "salary_lookups_per_month", session,
    )

    result = salary_intelligence(role_title=role, location=location, db=session)
    increment_recruiter_counter(profile, "salary_lookups_used", session)
    return result


@router.get("/career-trajectory/{candidate_profile_id}")
def career_trajectory(
    candidate_profile_id: int,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Predict career trajectory for a candidate profile."""
    from app.services.career_intelligence import predict_career_trajectory

    return predict_career_trajectory(
        candidate_profile_id=candidate_profile_id, db=session,
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
    from app.services.billing import get_recruiter_limit, get_recruiter_tier, _maybe_reset_recruiter_counters

    profile = get_recruiter_profile(user, session)
    _maybe_reset_recruiter_counters(profile, session)
    tier = get_recruiter_tier(profile)
    limit = get_recruiter_limit(tier, "intro_requests_per_month")
    return {
        "used": profile.intro_requests_used or 0,
        "limit": limit,
        "tier": tier,
    }

