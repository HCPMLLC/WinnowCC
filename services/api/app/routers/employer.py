"""Employer API: profile, jobs, candidate search, saved, analytics."""

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.employer import (
    EmployerCandidateView,
    EmployerJob,
    EmployerProfile,
    EmployerSavedCandidate,
)
from app.models.user import User
from app.schemas.employer import (
    BulkUploadFileResult,
    BulkUploadResponse,
    CandidateSearchFilters,
    CandidateSearchResponse,
    CandidateSearchResult,
    CompanyJobListItem,
    EmployerAnalyticsSummary,
    EmployerJobCreate,
    EmployerJobResponse,
    EmployerJobUpdate,
    EmployerProfileCreate,
    EmployerProfileResponse,
    EmployerProfileUpdate,
    JobDocumentUploadResponse,
    PaginatedCompanyJobsResponse,
    SaveCandidateRequest,
    SavedCandidateResponse,
    TopCandidateResult,
    TopCandidatesResponse,
    UpdateSavedCandidateNotes,
)
from app.services.auth import get_employer_profile, require_employer
from app.services.billing import (
    check_employer_monthly_limit,
    get_employer_limit,
    get_employer_tier,
    increment_employer_counter,
)

router = APIRouter(prefix="/api/employer", tags=["employer"])

# Batch upload limits (separate from EMPLOYER_PLAN_LIMITS)
_BATCH_LIMITS: dict[str, int] = {"free": 1, "starter": 5, "pro": 10, "enterprise": 10}

logger = logging.getLogger(__name__)


def _enqueue_distribution_jobs(
    job_id: int,
    old_status: str | None,
    new_status: str | None,
    content_changed: bool,
) -> None:
    """Enqueue distribution worker jobs based on status/content changes."""
    from app.services.queue import get_queue
    from app.services.scheduled_jobs import (
        process_distribution,
        process_distribution_update,
        process_removal,
    )

    try:
        queue = get_queue()
        if new_status == "active" and old_status != "active":
            queue.enqueue(process_distribution, job_id)
            logger.info("Enqueued auto-distribution for job %s", job_id)
        elif new_status in ("paused", "closed") and old_status == "active":
            queue.enqueue(process_removal, job_id)
            logger.info("Enqueued auto-removal for job %s", job_id)
        elif content_changed and old_status == "active" and new_status is None:
            # Content edited on an active job (no status change)
            queue.enqueue(process_distribution_update, job_id)
            logger.info("Enqueued distribution update for job %s", job_id)
    except Exception:
        logger.warning(
            "Failed to enqueue distribution job for %s",
            job_id,
            exc_info=True,
        )


# ============================================================================
# PROFILE MANAGEMENT
# ============================================================================


@router.post(
    "/profile",
    response_model=EmployerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employer_profile(
    profile_data: EmployerProfileCreate,
    user: User = Depends(require_employer),
    session: Session = Depends(get_session),
) -> EmployerProfile:
    """Create employer profile for current user."""
    existing = session.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employer profile already exists for this user.",
        )

    employer = EmployerProfile(user_id=user.id, **profile_data.model_dump())
    session.add(employer)
    session.commit()
    session.refresh(employer)
    return employer


@router.get("/profile", response_model=EmployerProfileResponse)
def get_my_employer_profile(
    employer: EmployerProfile = Depends(get_employer_profile),
) -> EmployerProfile:
    """Get current user's employer profile."""
    return employer


@router.patch("/profile", response_model=EmployerProfileResponse)
def update_employer_profile(
    profile_data: EmployerProfileUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerProfile:
    """Update employer profile (partial update)."""
    from app.schemas.employer import FREE_EMAIL_DOMAINS, _extract_base_domain

    updates = profile_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(employer, field, value)

    # Validate email domain against website after merge
    if employer.contact_email and employer.company_website:
        email_domain = _extract_base_domain(employer.contact_email, is_email=True)
        website_domain = _extract_base_domain(employer.company_website)
        if email_domain in FREE_EMAIL_DOMAINS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Contact email must use a company domain (e.g. you@{website_domain}), "
                    f"not a free email provider ({email_domain})."
                ),
            )
        if email_domain != website_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Contact email domain ({email_domain}) does not match "
                    f"company website domain ({website_domain})."
                ),
            )

    session.commit()
    session.refresh(employer)
    return employer


# ============================================================================
# JOB MANAGEMENT
# ============================================================================


@router.post(
    "/jobs",
    response_model=EmployerJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    job_data: EmployerJobCreate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerJob:
    """Create a new job posting (respects subscription tier limits)."""
    tier = get_employer_tier(employer)
    raw_limit = get_employer_limit(tier, "active_jobs")
    limit = (
        None if (isinstance(raw_limit, int) and raw_limit >= 999) else int(raw_limit)
    )
    if limit is not None:
        active_count = (
            session.execute(
                select(func.count(EmployerJob.id)).where(
                    EmployerJob.employer_id == employer.id,
                    EmployerJob.status.in_(["active", "draft"]),
                )
            ).scalar()
            or 0
        )
        if active_count >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{employer.subscription_tier.capitalize()} tier allows "
                    f"{limit} active job(s). Upgrade to post more."
                ),
            )

    # Validate job_id_external uniqueness within this employer
    ext_id = job_data.job_id_external if hasattr(job_data, "job_id_external") else None
    if ext_id:
        existing = session.execute(
            select(EmployerJob.id).where(
                EmployerJob.employer_id == employer.id,
                EmployerJob.job_id_external == ext_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A job with external ID '{ext_id}' already exists (job #{existing}). Please use a different ID.",
            )

    job = EmployerJob(employer_id=employer.id, **job_data.model_dump())
    session.add(job)
    session.commit()
    session.refresh(job)

    # Pre-compute candidate matches and sync to candidate-facing jobs table
    if job.status == "active":
        try:
            from app.services.job_pipeline import (
                populate_job_candidates,
                sync_employer_job_to_jobs,
            )
            from app.services.queue import get_queue

            q = get_queue()
            q.enqueue(populate_job_candidates, job.id)
            q.enqueue(sync_employer_job_to_jobs, job.id)
        except Exception:
            logger.debug(
                "Failed to enqueue background jobs for employer job %s", job.id
            )

    return job


@router.get("/jobs", response_model=list[EmployerJobResponse])
def list_my_jobs(
    status_filter: str | None = Query(None, alias="status"),
    archived: bool = Query(False),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[EmployerJobResponse]:
    """List all jobs posted by this employer."""
    from app.models.employer_job_candidate import EmployerJobCandidate

    # Subquery: matched candidates count (score > 50%) per job
    match_count_sq = (
        select(func.count(EmployerJobCandidate.id))
        .where(
            EmployerJobCandidate.employer_job_id == EmployerJob.id,
            EmployerJobCandidate.match_score > 0.5,
        )
        .correlate(EmployerJob)
        .scalar_subquery()
        .label("match_count")
    )

    stmt = select(EmployerJob, match_count_sq).where(
        EmployerJob.employer_id == employer.id,
        EmployerJob.archived == archived,
    )
    if status_filter:
        allowed = ("draft", "active", "paused", "closed")
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(allowed)}",
            )
        stmt = stmt.where(EmployerJob.status == status_filter)

    # Sort: deadline descending (nulls last), then matched candidates descending
    stmt = stmt.order_by(
        EmployerJob.close_date.desc().nulls_last(),
        desc(match_count_sq),
    )

    rows = session.execute(stmt).all()

    results = []
    for job, count in rows:
        resp = EmployerJobResponse.model_validate(job, from_attributes=True)
        resp.matched_candidates_count = count or 0
        results.append(resp)
    return results


# Column mapping for company-jobs sort
_COMPANY_SORT_COLUMNS = {
    "job_id_external": EmployerJob.job_id_external,
    "title": EmployerJob.title,
    "status": EmployerJob.status,
    "job_category": EmployerJob.job_category,
    "location": EmployerJob.location,
    "posted_at": EmployerJob.posted_at,
    "close_date": EmployerJob.close_date,
    "view_count": EmployerJob.view_count,
    "application_count": EmployerJob.application_count,
    "created_at": EmployerJob.created_at,
}


@router.get("/jobs/company", response_model=PaginatedCompanyJobsResponse)
def list_company_jobs(
    sort_by: str = Query("created_at", enum=list(_COMPANY_SORT_COLUMNS)),
    sort_dir: str = Query("desc", enum=["asc", "desc"]),
    group_by: str | None = Query(
        None, enum=["poster_email", "status", "job_category", "location"]
    ),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
):
    """List all jobs for the employer's company (all team members' postings)."""
    from app.models.employer_job_candidate import EmployerJobCandidate

    # Correlated subquery for match count (same approach as list_my_jobs)
    match_count_sq = (
        select(func.count(EmployerJobCandidate.id))
        .where(
            EmployerJobCandidate.employer_job_id == EmployerJob.id,
            EmployerJobCandidate.match_score > 0.5,
        )
        .correlate(EmployerJob)
        .scalar_subquery()
        .label("match_count")
    )

    # Join EmployerJob -> EmployerProfile -> User to get poster email
    # Filter by company_name so all profiles at the same company are included
    stmt = (
        select(
            EmployerJob,
            User.email.label("poster_email"),
            match_count_sq,
        )
        .join(EmployerProfile, EmployerJob.employer_id == EmployerProfile.id)
        .join(User, EmployerProfile.user_id == User.id)
        .where(EmployerProfile.company_name == employer.company_name)
    )

    # Status filter
    if status_filter:
        allowed = ("draft", "active", "paused", "closed")
        if status_filter not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(allowed)}",
            )
        stmt = stmt.where(EmployerJob.status == status_filter)

    # Count before pagination (exclude match_count from count subquery)
    count_base = (
        select(EmployerJob.id)
        .join(EmployerProfile, EmployerJob.employer_id == EmployerProfile.id)
        .join(User, EmployerProfile.user_id == User.id)
        .where(EmployerProfile.company_name == employer.company_name)
    )
    if status_filter:
        count_base = count_base.where(EmployerJob.status == status_filter)
    total = (
        session.execute(
            select(func.count()).select_from(count_base.subquery())
        ).scalar()
        or 0
    )

    # Sorting
    col = _COMPANY_SORT_COLUMNS.get(sort_by, EmployerJob.created_at)
    direction = asc if sort_dir == "asc" else desc

    # Group-by as primary sort
    _GROUP_COLUMNS = {
        "poster_email": User.email,
        "status": EmployerJob.status,
        "job_category": EmployerJob.job_category,
        "location": EmployerJob.location,
    }
    if group_by and group_by in _GROUP_COLUMNS:
        stmt = stmt.order_by(asc(_GROUP_COLUMNS[group_by]), direction(col))
    else:
        stmt = stmt.order_by(direction(col))

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = session.execute(stmt).all()

    items = [
        CompanyJobListItem(
            id=job.id,
            job_id_external=job.job_id_external,
            title=job.title,
            status=job.status,
            job_category=job.job_category,
            location=job.location,
            remote_policy=job.remote_policy,
            posted_at=job.posted_at,
            close_date=job.close_date,
            view_count=job.view_count,
            matched_candidates_count=match_count or 0,
            application_count=job.application_count,
            poster_email=poster_email,
            created_at=job.created_at,
        )
        for job, poster_email, match_count in rows
    ]

    return PaginatedCompanyJobsResponse(
        items=items, total=total, page=page, page_size=page_size
    )


def _get_remaining_job_quota(employer: EmployerProfile, session: Session) -> int | None:
    """Return remaining job slots, or None for unlimited tiers."""
    tier = get_employer_tier(employer)
    raw_limit = get_employer_limit(tier, "active_jobs")
    if isinstance(raw_limit, int) and raw_limit >= 999:
        return None  # unlimited
    total_limit = int(raw_limit)
    current_count = (
        session.execute(
            select(func.count(EmployerJob.id)).where(
                EmployerJob.employer_id == employer.id
            )
        ).scalar()
        or 0
    )
    return max(0, total_limit - current_count)


@router.post("/jobs/upload-documents", response_model=BulkUploadResponse)
async def bulk_upload_job_documents(
    files: list[UploadFile] = File(...),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> BulkUploadResponse:
    """Bulk upload multiple job description documents.

    Respects subscription tier batch and total-job limits.
    """
    from app.services.employer_job_parser import parse_job_document

    tier = get_employer_tier(employer)
    batch_limit = _BATCH_LIMITS.get(tier, 1)

    if len(files) > batch_limit:
        recommendation = (
            "Consider upgrading your plan for higher batch limits."
            if tier in ("free", "starter")
            else (
                "For larger volumes, use XML/JSON job feeds or ATS integrations "
                "for automated bulk ingestion."
            )
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{tier.capitalize()} tier allows up to {batch_limit} file(s) "
                f"per batch. You submitted {len(files)}. {recommendation}"
            ),
        )

    # For capped tiers, check remaining quota and clamp
    remaining = _get_remaining_job_quota(employer, session)
    max_to_process = len(files)
    if remaining is not None:
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{tier.capitalize()} tier job limit reached. "
                    "Upgrade your plan to post more jobs."
                ),
            )
        max_to_process = min(len(files), remaining)

    # Also check AI parsing monthly limit
    from app.services.billing import _maybe_reset_employer_counters

    ai_limit = get_employer_limit(tier, "ai_job_parsing_per_month")
    if isinstance(ai_limit, int) and ai_limit < 999:
        _maybe_reset_employer_counters(employer, session)
        ai_used = employer.ai_parsing_used or 0
        ai_remaining = max(0, ai_limit - ai_used)
        if ai_remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Monthly AI parsing limit reached ({ai_limit} per month on "
                    f"{tier} plan). Upgrade for more."
                ),
            )
        max_to_process = min(max_to_process, ai_remaining)

    results: list[BulkUploadFileResult] = []
    succeeded = 0

    for i, upload_file in enumerate(files):
        filename = upload_file.filename or f"file_{i}"

        # Skip files beyond quota
        if succeeded >= max_to_process and remaining is not None:
            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=False,
                    error=(
                        f"{tier.capitalize()} tier job limit reached. "
                        "Upgrade to post more jobs."
                    ),
                )
            )
            continue

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

        # Validate file size
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

            job = EmployerJob(
                employer_id=employer.id,
                title=parsed.get("title"),
                description=parsed.get("description", ""),
                requirements=parsed.get("requirements"),
                nice_to_haves=parsed.get("nice_to_haves"),
                location=parsed.get("location"),
                remote_policy=parsed.get("remote_policy"),
                employment_type=parsed.get("employment_type"),
                job_id_external=parsed.get("job_id_external"),
                start_date=parsed.get("start_date"),
                close_date=parsed.get("close_date"),
                job_category=parsed.get("job_category"),
                department=parsed.get("department"),
                certifications_required=parsed.get("certifications_required"),
                job_type=parsed.get("job_type"),
                salary_min=parsed.get("salary_min"),
                salary_max=parsed.get("salary_max"),
                salary_currency=parsed.get("salary_currency") or "USD",
                equity_offered=parsed.get("equity_offered") or False,
                application_email=parsed.get("application_email"),
                application_url=parsed.get("application_url"),
                parsed_from_document=True,
                parsing_confidence=parsed.get("parsing_confidence", 0.0),
                status="draft",
            )
            session.add(job)
            session.flush()  # get job.id without full commit

            results.append(
                BulkUploadFileResult(
                    filename=filename,
                    success=True,
                    job_id=job.id,
                    title=parsed.get("title"),
                )
            )
            succeeded += 1
            increment_employer_counter(employer, "ai_parsing_used", session)

        except Exception as exc:
            logger.exception("Error parsing bulk upload file: %s", filename)
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

    # Upgrade recommendation for Pro/Enterprise at batch limit
    upgrade_recommendation = None
    if tier in ("pro", "enterprise") and len(files) >= batch_limit:
        upgrade_recommendation = (
            "You've reached the per-batch upload limit. For larger volumes, "
            "consider using XML/JSON job feeds or ATS integrations "
            "for automated bulk ingestion."
        )
    elif tier in ("free", "starter"):
        if len(files) >= batch_limit or (
            remaining is not None and succeeded >= remaining
        ):
            upgrade_recommendation = (
                f"Upgrade from {tier.capitalize()} to unlock higher batch limits "
                "and more total job postings."
            )

    total_failed = len(results) - succeeded
    return BulkUploadResponse(
        results=results,
        total_submitted=len(files),
        total_succeeded=succeeded,
        total_failed=total_failed,
        upgrade_recommendation=upgrade_recommendation,
    )


@router.get("/jobs/{job_id}", response_model=EmployerJobResponse)
def get_job(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerJobResponse:
    """Get a specific job by ID."""
    from app.models.employer_job_candidate import EmployerJobCandidate

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    count = (
        session.execute(
            select(func.count(EmployerJobCandidate.id)).where(
                EmployerJobCandidate.employer_job_id == job.id,
                EmployerJobCandidate.match_score > 0.5,
            )
        ).scalar()
        or 0
    )
    resp = EmployerJobResponse.model_validate(job, from_attributes=True)
    resp.matched_candidates_count = count
    return resp


@router.patch("/jobs/{job_id}", response_model=EmployerJobResponse)
def update_job(
    job_id: int,
    job_data: EmployerJobUpdate,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerJob:
    """Update a job posting. If status changes to 'active', sets posted_at."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
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

    # Detect content changes that should trigger board sync
    _CONTENT_FIELDS = {
        "title",
        "description",
        "requirements",
        "salary_min",
        "salary_max",
        "location",
    }
    content_changed = bool(update_data.keys() & _CONTENT_FIELDS)

    for field, value in update_data.items():
        setattr(job, field, value)
    session.commit()
    session.refresh(job)

    # Auto-distribution hooks
    _enqueue_distribution_jobs(job.id, old_status, new_status, content_changed)

    # Sync proxy Job row for candidate matching
    try:
        from app.services.job_pipeline import (
            deactivate_employer_job_proxy,
            populate_job_candidates,
            sync_employer_job_to_jobs,
        )
        from app.services.queue import get_queue

        q = get_queue()
        if new_status == "active" and old_status != "active":
            # Becoming active: re-compute employer candidates + sync proxy
            q.enqueue(populate_job_candidates, job.id)
            q.enqueue(sync_employer_job_to_jobs, job.id)
        elif new_status == "active" and content_changed:
            # Content changed while active: update the proxy
            q.enqueue(sync_employer_job_to_jobs, job.id)
        elif old_status == "active" and new_status and new_status != "active":
            # Leaving active state: deactivate proxy
            q.enqueue(deactivate_employer_job_proxy, job.id)
    except Exception:
        logger.debug("Failed to enqueue sync jobs for employer job %s", job.id)

    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> None:
    """Delete a job posting."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    # Deactivate proxy Job before deleting the EmployerJob
    try:
        from app.services.job_pipeline import deactivate_employer_job_proxy
        from app.services.queue import get_queue

        get_queue().enqueue(deactivate_employer_job_proxy, job.id)
    except Exception:
        logger.debug("Failed to enqueue deactivate for employer job %s", job.id)

    session.delete(job)
    session.commit()


@router.post("/jobs/upload-document", response_model=JobDocumentUploadResponse)
async def upload_job_document(
    file: UploadFile = File(...),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> JobDocumentUploadResponse:
    """Upload a .doc or .docx job description and auto-create a draft job posting."""
    from app.services.employer_job_parser import parse_job_document

    # Check AI parsing monthly limit
    check_employer_monthly_limit(
        employer, "ai_parsing_used", "ai_job_parsing_per_month", session
    )

    if not file.filename or not file.filename.lower().endswith((".doc", ".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .doc and .docx files are supported.",
        )

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10 MB.",
        )

    ext = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        try:
            parsed = parse_job_document(tmp_path)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e

        if not parsed.get("title"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract job title from document.",
            )

        # Validate job_id_external uniqueness within this employer
        ext_id = parsed.get("job_id_external")
        if ext_id:
            existing = session.execute(
                select(EmployerJob.id).where(
                    EmployerJob.employer_id == employer.id,
                    EmployerJob.job_id_external == ext_id,
                )
            ).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A job with external ID '{ext_id}' already exists (job #{existing}). Please use a different ID.",
                )

        job = EmployerJob(
            employer_id=employer.id,
            title=parsed.get("title"),
            description=parsed.get("description", ""),
            requirements=parsed.get("requirements"),
            nice_to_haves=parsed.get("nice_to_haves"),
            location=parsed.get("location"),
            remote_policy=parsed.get("remote_policy"),
            employment_type=parsed.get("employment_type"),
            job_id_external=ext_id,
            start_date=parsed.get("start_date"),
            close_date=parsed.get("close_date"),
            job_category=parsed.get("job_category"),
            department=parsed.get("department"),
            certifications_required=parsed.get("certifications_required"),
            job_type=parsed.get("job_type"),
            salary_min=parsed.get("salary_min"),
            salary_max=parsed.get("salary_max"),
            salary_currency=parsed.get("salary_currency") or "USD",
            equity_offered=parsed.get("equity_offered") or False,
            application_email=parsed.get("application_email"),
            application_url=parsed.get("application_url"),
            parsed_from_document=True,
            parsing_confidence=parsed.get("parsing_confidence", 0.0),
            status="draft",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        # Increment AI parsing usage counter
        increment_employer_counter(employer, "ai_parsing_used", session)

        return JobDocumentUploadResponse(
            job_id=job.id,
            parsed_data=parsed,
            confidence=parsed.get("parsing_confidence", 0.0),
            message="Job draft created from document. Please review and publish.",
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/jobs/{job_id}/reparse-document", response_model=EmployerJobResponse)
async def reparse_job_document(
    job_id: int,
    file: UploadFile = File(...),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerJobResponse:
    """Re-upload and re-parse a document to update an existing job posting."""
    from app.models.employer_job_candidate import EmployerJobCandidate
    from app.services.employer_job_parser import parse_job_document

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    if not file.filename or not file.filename.lower().endswith(
        (".doc", ".docx", ".pdf", ".txt")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .doc, .docx, .pdf, and .txt files are supported.",
        )

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10 MB.",
        )

    ext = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        try:
            parsed = parse_job_document(tmp_path)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e
        if not parsed.get("title"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract job title from document.",
            )

        # Update all parsed fields on existing job
        updatable = (
            "title",
            "description",
            "requirements",
            "nice_to_haves",
            "location",
            "remote_policy",
            "employment_type",
            "job_id_external",
            "start_date",
            "close_date",
            "job_category",
            "department",
            "certifications_required",
            "job_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "equity_offered",
            "application_email",
            "application_url",
        )
        for field in updatable:
            if field in parsed:
                setattr(job, field, parsed[field])

        job.parsed_from_document = True
        job.parsing_confidence = parsed.get("parsing_confidence", 0.0)
        job.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(job)

        count = (
            session.execute(
                select(func.count(EmployerJobCandidate.id)).where(
                    EmployerJobCandidate.employer_job_id == job.id,
                    EmployerJobCandidate.match_score > 0.5,
                )
            ).scalar()
            or 0
        )
        resp = EmployerJobResponse.model_validate(job, from_attributes=True)
        resp.matched_candidates_count = count
        return resp
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/jobs/{job_id}/archive")
def archive_job(
    job_id: int,
    reason: str | None = Query(None),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Archive a job posting."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    if job.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Job is already archived."
        )

    old_status = job.status
    job.archived = True
    job.archived_at = datetime.now(UTC)
    job.archived_reason = reason or "manual"
    job.status = "closed"
    session.commit()
    session.refresh(job)

    # Remove from all boards if it was live
    _enqueue_distribution_jobs(job.id, old_status, "closed", content_changed=False)

    # Deactivate proxy Job for candidate matching
    try:
        from app.services.job_pipeline import deactivate_employer_job_proxy
        from app.services.queue import get_queue

        get_queue().enqueue(deactivate_employer_job_proxy, job.id)
    except Exception:
        logger.debug("Failed to enqueue deactivate for archived job %s", job.id)

    return {"message": "Job archived successfully", "job_id": job.id}


@router.post("/jobs/{job_id}/unarchive")
def unarchive_job(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Unarchive a job posting (returns to draft status)."""
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )
    if not job.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not archived."
        )

    job.archived = False
    job.archived_at = None
    job.archived_reason = None
    job.status = "draft"
    session.commit()
    session.refresh(job)

    return {"message": "Job unarchived successfully", "job_id": job.id}


@router.get("/jobs/{job_id}/top-candidates", response_model=TopCandidatesResponse)
def get_top_candidates_for_job(
    job_id: int,
    limit: int = Query(5, ge=1, le=20),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> TopCandidatesResponse:
    """Return the top-scoring candidates for an employer job.

    Reads from pre-computed cache when available, falls back to live
    computation on cache miss (cold start).
    """
    from app.models.employer_job_candidate import EmployerJobCandidate
    from app.services.matching import find_top_candidates_for_employer_job

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    # Try cached results first
    cached = (
        session.execute(
            select(EmployerJobCandidate)
            .where(EmployerJobCandidate.employer_job_id == job.id)
            .order_by(EmployerJobCandidate.match_score.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    if cached:
        candidates = []
        for c in cached:
            profile = session.get(CandidateProfile, c.candidate_profile_id)
            if not profile:
                continue
            result = _profile_to_search_result(profile)
            candidates.append(
                TopCandidateResult(
                    **result.model_dump(exclude={"match_score"}),
                    matched_skills=c.matched_skills or [],
                    match_score=c.match_score,
                )
            )
        total_evaluated = (
            session.execute(
                select(func.count(EmployerJobCandidate.id)).where(
                    EmployerJobCandidate.employer_job_id == job.id
                )
            ).scalar()
            or 0
        )
    else:
        # Fallback: live computation (cold start)
        results = find_top_candidates_for_employer_job(session, job, limit)
        candidates = [TopCandidateResult(**r) for r in results]
        total_evaluated = (
            session.execute(
                select(func.count()).select_from(
                    _latest_profiles_query()
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

    return TopCandidatesResponse(
        job_id=job.id,
        job_title=job.title,
        candidates=candidates,
        total_evaluated=total_evaluated,
    )


# ============================================================================
# CANDIDATE SEARCH
# ============================================================================


def _latest_profiles_query():
    """Base query returning only the latest CandidateProfile per user.

    Uses MAX(version) per user_id, so each user appears once.
    Excludes profiles with NULL user_id (orphaned uploads).
    """
    latest = (
        select(
            CandidateProfile.user_id,
            func.max(CandidateProfile.version).label("max_version"),
        )
        .where(CandidateProfile.user_id.is_not(None))
        .group_by(CandidateProfile.user_id)
    ).subquery()

    return select(CandidateProfile).join(
        latest,
        (CandidateProfile.user_id == latest.c.user_id)
        & (CandidateProfile.version == latest.c.max_version),
    )


def _profile_name(profile: CandidateProfile) -> str:
    """Extract display name from profile_json basics."""
    pj = profile.profile_json or {}
    basics = pj.get("basics") or {}
    first = basics.get("first_name") or ""
    last = basics.get("last_name") or ""
    name = basics.get("name") or f"{first} {last}".strip()
    return name or f"Candidate {profile.id}"


def _profile_to_search_result(profile: CandidateProfile) -> CandidateSearchResult:
    """Convert a CandidateProfile to a CandidateSearchResult."""
    pj = profile.profile_json or {}
    basics = pj.get("basics") or {}
    skills = pj.get("skills") or []
    visibility = profile.profile_visibility or "public"

    name = _profile_name(profile)
    if visibility == "anonymous":
        name = f"Candidate {profile.id}"

    headline = None
    experience = pj.get("experience") or []
    if experience and isinstance(experience[0], dict):
        title = experience[0].get("title") or ""
        company = experience[0].get("company") or ""
        if title:
            headline = f"{title} at {company}" if company else title

    preferences = pj.get("preferences") or {}
    preferred_locations = preferences.get("locations") or []
    remote_ok = preferences.get("remote_ok")
    willing_to_relocate = basics.get("willing_to_relocate")

    return CandidateSearchResult(
        id=profile.id,
        name=name,
        headline=headline,
        location=basics.get("location"),
        years_experience=basics.get("total_years_experience"),
        top_skills=[
            s["name"] if isinstance(s, dict) else str(s)
            for s in (skills[:5] if isinstance(skills, list) else [])
        ],
        match_score=None,
        profile_visibility=visibility,
        preferred_locations=preferred_locations
        if isinstance(preferred_locations, list)
        else [],
        remote_ok=remote_ok if isinstance(remote_ok, bool) else None,
        willing_to_relocate=willing_to_relocate
        if isinstance(willing_to_relocate, bool)
        else None,
    )


@router.post("/candidates/search", response_model=CandidateSearchResponse)
def search_candidates(
    filters: CandidateSearchFilters,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> CandidateSearchResponse:
    """Search for candidates. Search does not count toward view limits."""
    stmt = _latest_profiles_query().where(
        CandidateProfile.open_to_opportunities == True,  # noqa: E712
        CandidateProfile.profile_visibility.in_(["public", "anonymous"]),
    )

    # Skill filter — simple JSONB text search
    if filters.skills:
        from sqlalchemy import String, cast

        for skill in filters.skills:
            stmt = stmt.where(
                cast(CandidateProfile.profile_json["skills"], String).ilike(
                    f"%{skill}%"
                )
            )

    # Location filter
    if filters.locations:
        from sqlalchemy import String, cast

        loc_filters = [
            cast(CandidateProfile.profile_json["basics"]["location"], String).ilike(
                f"%{loc}%"
            )
            for loc in filters.locations
        ]
        stmt = stmt.where(or_(*loc_filters))

    # Job title filter
    if filters.job_titles:
        from sqlalchemy import String, cast

        title_filters = [
            cast(CandidateProfile.profile_json["experience"], String).ilike(
                f"%{title}%"
            )
            for title in filters.job_titles
        ]
        stmt = stmt.where(or_(*title_filters))

    # Count total before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    profiles = session.execute(stmt).scalars().all()

    results = [_profile_to_search_result(p) for p in profiles]

    return CandidateSearchResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < total,
    )


# ============================================================================
# SAVED CANDIDATES
# ============================================================================


@router.post(
    "/candidates/save",
    response_model=SavedCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_candidate(
    body: SaveCandidateRequest,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> SavedCandidateResponse:
    """Save a candidate to favorites."""
    existing = session.execute(
        select(EmployerSavedCandidate).where(
            EmployerSavedCandidate.employer_id == employer.id,
            EmployerSavedCandidate.candidate_id == body.candidate_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate already saved."
        )

    profile = session.execute(
        select(CandidateProfile).where(CandidateProfile.id == body.candidate_id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found."
        )

    saved = EmployerSavedCandidate(
        employer_id=employer.id, candidate_id=body.candidate_id, notes=body.notes
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)

    return SavedCandidateResponse(
        id=saved.id,
        candidate_id=profile.id,
        notes=saved.notes,
        saved_at=saved.saved_at,
        candidate=_profile_to_search_result(profile),
    )


@router.get("/candidates/saved", response_model=list[SavedCandidateResponse])
def list_saved_candidates(
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[SavedCandidateResponse]:
    """List all saved candidates."""
    stmt = (
        select(EmployerSavedCandidate)
        .where(EmployerSavedCandidate.employer_id == employer.id)
        .order_by(EmployerSavedCandidate.saved_at.desc())
    )
    saved_list = session.execute(stmt).scalars().all()

    results = []
    for s in saved_list:
        profile = session.execute(
            select(CandidateProfile).where(CandidateProfile.id == s.candidate_id)
        ).scalar_one_or_none()
        if profile is None:
            continue
        results.append(
            SavedCandidateResponse(
                id=s.id,
                candidate_id=s.candidate_id,
                notes=s.notes,
                saved_at=s.saved_at,
                candidate=_profile_to_search_result(profile),
            )
        )
    return results


@router.patch("/candidates/saved/{saved_id}", response_model=SavedCandidateResponse)
def update_saved_candidate_notes(
    saved_id: int,
    body: UpdateSavedCandidateNotes,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> SavedCandidateResponse:
    """Update notes on a saved candidate."""
    saved = session.execute(
        select(EmployerSavedCandidate).where(
            EmployerSavedCandidate.id == saved_id,
            EmployerSavedCandidate.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved candidate not found."
        )

    saved.notes = body.notes
    session.commit()
    session.refresh(saved)

    profile = session.execute(
        select(CandidateProfile).where(CandidateProfile.id == saved.candidate_id)
    ).scalar_one_or_none()

    return SavedCandidateResponse(
        id=saved.id,
        candidate_id=saved.candidate_id,
        notes=saved.notes,
        saved_at=saved.saved_at,
        candidate=_profile_to_search_result(profile) if profile else None,
    )


@router.delete("/candidates/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_candidate(
    saved_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> None:
    """Remove a candidate from saved list."""
    saved = session.execute(
        select(EmployerSavedCandidate).where(
            EmployerSavedCandidate.id == saved_id,
            EmployerSavedCandidate.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Saved candidate not found."
        )
    session.delete(saved)
    session.commit()


@router.get("/candidates/{candidate_id}")
def view_candidate_profile(
    candidate_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """View detailed candidate profile. Counts as a view (subject to tier limits)."""
    # Check subscription view limits
    tier = get_employer_tier(employer)
    raw_limit = get_employer_limit(tier, "candidate_views_per_month")
    limit = (
        None if (isinstance(raw_limit, int) and raw_limit >= 999) else int(raw_limit)
    )
    if limit is not None:
        month_start = datetime.now(UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        views_this_month = (
            session.execute(
                select(func.count(EmployerCandidateView.id)).where(
                    EmployerCandidateView.employer_id == employer.id,
                    EmployerCandidateView.viewed_at >= month_start,
                )
            ).scalar()
            or 0
        )
        if views_this_month >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{tier.capitalize()} tier allows {limit} candidate views/month. "
                    "Upgrade for more."
                ),
            )

    # Get candidate
    profile = session.execute(
        select(CandidateProfile).where(
            CandidateProfile.id == candidate_id,
            CandidateProfile.open_to_opportunities == True,  # noqa: E712
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found or not open to opportunities.",
        )

    # Log the view
    view = EmployerCandidateView(
        employer_id=employer.id, candidate_id=candidate_id, source="search"
    )
    session.add(view)
    session.commit()

    pj = profile.profile_json or {}
    basics = pj.get("basics") or {}
    visibility = profile.profile_visibility or "public"

    if visibility == "anonymous":
        return {
            "id": profile.id,
            "name": f"Candidate {profile.id}",
            "headline": None,
            "years_experience": basics.get("total_years_experience"),
            "skills": pj.get("skills", []),
            "experience": pj.get("experience", []),
            "education": pj.get("education", []),
            "anonymized": True,
        }

    return {
        "id": profile.id,
        "name": _profile_name(profile),
        "profile_json": pj,
        "years_experience": basics.get("total_years_experience"),
        "anonymized": False,
    }


# ============================================================================
# ANALYTICS
# ============================================================================


@router.get("/analytics/summary", response_model=EmployerAnalyticsSummary)
def get_analytics_summary(
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> EmployerAnalyticsSummary:
    """Get analytics summary for employer dashboard."""
    active_jobs = (
        session.execute(
            select(func.count(EmployerJob.id)).where(
                EmployerJob.employer_id == employer.id,
                EmployerJob.status == "active",
            )
        ).scalar()
        or 0
    )

    total_views = (
        session.execute(
            select(func.coalesce(func.sum(EmployerJob.view_count), 0)).where(
                EmployerJob.employer_id == employer.id
            )
        ).scalar()
        or 0
    )

    total_applications = (
        session.execute(
            select(func.coalesce(func.sum(EmployerJob.application_count), 0)).where(
                EmployerJob.employer_id == employer.id
            )
        ).scalar()
        or 0
    )

    month_start = datetime.now(UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    candidate_views_this_month = (
        session.execute(
            select(func.count(EmployerCandidateView.id)).where(
                EmployerCandidateView.employer_id == employer.id,
                EmployerCandidateView.viewed_at >= month_start,
            )
        ).scalar()
        or 0
    )

    saved_candidates = (
        session.execute(
            select(func.count(EmployerSavedCandidate.id)).where(
                EmployerSavedCandidate.employer_id == employer.id
            )
        ).scalar()
        or 0
    )

    return EmployerAnalyticsSummary(
        active_jobs=active_jobs,
        total_job_views=int(total_views),
        total_applications=int(total_applications),
        candidate_views_this_month=candidate_views_this_month,
        candidate_views_limit=get_employer_limit(
            get_employer_tier(employer), "candidate_views_per_month"
        ),
        saved_candidates=saved_candidates,
        subscription_tier=employer.subscription_tier,
        subscription_status=employer.subscription_status or "active",
    )


# ============================================================================
# RECRUITER SUBMISSIONS (employer view)
# ============================================================================


@router.get("/jobs/{job_id}/submissions")
def list_job_submissions(
    job_id: int,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> list[dict]:
    """View all recruiter submissions for an employer job."""
    from app.models.candidate_submission import CandidateSubmission
    from app.models.recruiter import RecruiterProfile
    from app.services.submission import get_submissions_for_employer_job

    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == job_id, EmployerJob.employer_id == employer.id
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    # Tier-based enrichment
    tier = get_employer_tier(employer)
    submission_view = get_employer_limit(tier, "submission_view")
    include_duplicates = get_employer_limit(tier, "duplicate_highlighting")

    subs = get_submissions_for_employer_job(session, job.id)

    # Build duplicate map for highlighting (starter+)
    candidate_counts: dict[int, int] = {}
    if include_duplicates:
        for s in subs:
            cid = s.candidate_profile_id
            if cid:
                candidate_counts[cid] = candidate_counts.get(cid, 0) + 1

    results = []
    for s in subs:
        # Resolve candidate name
        candidate_name = f"Candidate #{s.candidate_profile_id}"
        if s.candidate_profile_id:
            cp = session.get(CandidateProfile, s.candidate_profile_id)
            if cp:
                pj = cp.profile_json or {}
                basics = pj.get("basics") or {}
                first = basics.get("first_name", "")
                last = basics.get("last_name", "")
                candidate_name = (
                    basics.get("name") or f"{first} {last}".strip() or candidate_name
                )

        # Resolve recruiter company
        recruiter_company = None
        if s.recruiter_profile_id:
            rp = session.get(RecruiterProfile, s.recruiter_profile_id)
            if rp:
                recruiter_company = rp.company_name

        entry: dict = {
            "id": s.id,
            "candidate_profile_id": s.candidate_profile_id,
            "candidate_name": candidate_name,
            "recruiter_profile_id": s.recruiter_profile_id,
            "recruiter_company_name": recruiter_company,
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            "status": s.status,
            "employer_notes": s.employer_notes,
        }

        # First-submission badges and duplicate highlighting (starter+)
        if submission_view in ("standard", "full"):
            entry["is_first_submission"] = s.is_first_submission
            cid = s.candidate_profile_id
            entry["is_duplicate_candidate"] = (
                bool(include_duplicates and cid and candidate_counts.get(cid, 0) > 1)
            )
        else:
            entry["is_first_submission"] = None
            entry["is_duplicate_candidate"] = None

        results.append(entry)
    return results


@router.patch("/submissions/{submission_id}")
def update_submission_status(
    submission_id: int,
    body: dict,
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> dict:
    """Update submission status (accept/reject) — employer only."""
    from app.models.candidate_submission import CandidateSubmission

    sub = session.execute(
        select(CandidateSubmission).where(
            CandidateSubmission.id == submission_id,
        )
    ).scalar_one_or_none()
    if sub is None or sub.employer_job_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found.",
        )

    # Verify employer owns the job
    job = session.execute(
        select(EmployerJob).where(
            EmployerJob.id == sub.employer_job_id,
            EmployerJob.employer_id == employer.id,
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this job.",
        )

    allowed_statuses = {"under_review", "accepted", "rejected"}
    new_status = body.get("status")
    if new_status and new_status in allowed_statuses:
        sub.status = new_status
        sub.employer_response_at = datetime.now(UTC)
    if "employer_notes" in body:
        sub.employer_notes = body["employer_notes"]

    session.commit()
    session.refresh(sub)

    return {
        "id": sub.id,
        "status": sub.status,
        "employer_notes": sub.employer_notes,
        "employer_response_at": sub.employer_response_at.isoformat()
        if sub.employer_response_at
        else None,
    }
