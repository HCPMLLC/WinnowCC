"""Public API for career page widgets (no user auth required)."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.employer import EmployerJob
from app.models.job import Job
from app.models.recruiter_job import RecruiterJob
from app.schemas.career_page import (
    PublicCareerPageResponse,
    PublicJobDetail,
    PublicJobListResponse,
    PublicJobSummary,
)
from app.services.career_page_service import (
    get_career_page_by_domain,
    get_career_page_by_slug,
    increment_page_view,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/public/career-pages", tags=["career-pages-public"]
)


def _get_job_id_external(db: Session, job: Job) -> str | None:
    """Resolve the external solicitation number from the linked employer/recruiter job."""
    if job.employer_job_id:
        ej = db.get(EmployerJob, job.employer_job_id)
        if ej and ej.job_id_external:
            return ej.job_id_external
    if job.recruiter_job_id:
        rj = db.get(RecruiterJob, job.recruiter_job_id)
        if rj and rj.job_id_external:
            return rj.job_id_external
    return None


@router.get("/{slug}", response_model=PublicCareerPageResponse)
def get_public_career_page(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    preview: bool = Query(False),
):
    page = get_career_page_by_slug(db, slug)

    if not page:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

    if not page.published and not preview:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

    # Don't count preview visits in analytics
    if not preview:
        increment_page_view(db, page.id)
    return PublicCareerPageResponse.model_validate(page)


@router.get("/{slug}/jobs", response_model=PublicJobListResponse)
def list_public_jobs(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    location: str | None = None,
    search: str | None = None,
    preview: bool = Query(False),
):
    career_page = get_career_page_by_slug(db, slug)

    if not career_page:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

    if not career_page.published and not preview:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

    # Build query — filter by active jobs linked to this tenant
    now = datetime.now(UTC)
    filters = [
        Job.is_active == True,  # noqa: E712
        # Exclude jobs whose application deadline has already passed
        or_(
            Job.application_deadline.is_(None),
            Job.application_deadline >= now,
        ),
    ]

    if career_page.tenant_type == "employer":
        filters.append(Job.employer_job_id.isnot(None))
    elif career_page.tenant_type == "recruiter":
        filters.append(Job.recruiter_job_id.isnot(None))

    query = select(Job).where(and_(*filters))

    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))
    if search:
        query = query.where(
            Job.title.ilike(f"%{search}%")
            | Job.description_text.ilike(f"%{search}%")
        )

    # Count total
    count_result = db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Paginate — default sort by application deadline descending
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(
        Job.application_deadline.desc().nulls_last(),
        Job.ingested_at.desc(),
    )

    result = db.execute(query)
    jobs = list(result.scalars().all())

    return PublicJobListResponse(
        jobs=[
            PublicJobSummary(
                id=job.id,
                title=job.title,
                company=job.company,
                job_id_external=_get_job_id_external(db, job),
                location=job.location,
                location_type="remote" if job.remote_flag else "onsite",
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.currency,
                application_deadline=job.application_deadline,
                posted_at=job.posted_at or job.ingested_at,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        filters={"locations": [], "departments": []},
    )


@router.get("/{slug}/jobs/{job_id}", response_model=PublicJobDetail)
def get_public_job_detail(
    slug: str,
    job_id: int,
    db: Annotated[Session, Depends(get_session)],
    preview: bool = Query(False),
):
    """Get full job details for a career page listing."""
    career_page = get_career_page_by_slug(db, slug)
    if not career_page:
        raise HTTPException(status_code=404, detail="Career page not found")
    if not career_page.published and not preview:
        raise HTTPException(status_code=404, detail="Career page not found")

    job = db.execute(
        select(Job).where(Job.id == job_id, Job.is_active == True)  # noqa: E712
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return PublicJobDetail(
        id=job.id,
        title=job.title,
        company=job.company,
        job_id_external=_get_job_id_external(db, job),
        location=job.location,
        location_type="remote" if job.remote_flag else "onsite",
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.currency,
        application_deadline=job.application_deadline,
        posted_at=job.posted_at or job.ingested_at,
        description_html=job.description_html,
        description_text=job.description_text,
        url=job.url,
    )


@router.get("/resolve-domain/{domain}")
def resolve_custom_domain(
    domain: str,
    db: Annotated[Session, Depends(get_session)],
):
    """Resolve a custom domain to a career page slug."""
    page = get_career_page_by_domain(db, domain)
    if not page:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"slug": page.slug, "published": page.published}
