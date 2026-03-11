"""Public API for career page widgets (no user auth required)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job import Job
from app.schemas.career_page import (
    PublicCareerPageResponse,
    PublicJobListResponse,
    PublicJobSummary,
)
from app.services.career_page_service import (
    get_career_page_by_slug,
    increment_page_view,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/public/career-pages", tags=["career-pages-public"]
)


@router.get("/{slug}", response_model=PublicCareerPageResponse)
def get_public_career_page(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
):
    page = get_career_page_by_slug(db, slug)

    if not page or not page.published:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

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
):
    career_page = get_career_page_by_slug(db, slug)

    if not career_page or not career_page.published:
        raise HTTPException(
            status_code=404, detail="Career page not found"
        )

    # Build query — filter by active jobs linked to this tenant's employer jobs
    filters = [Job.is_active == True]  # noqa: E712

    if career_page.tenant_type == "employer":
        filters.append(Job.employer_job_id.isnot(None))

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

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(
        Job.ingested_at.desc()
    )

    result = db.execute(query)
    jobs = list(result.scalars().all())

    return PublicJobListResponse(
        jobs=[
            PublicJobSummary(
                id=job.id,
                title=job.title,
                location=job.location,
                location_type="remote" if job.remote_flag else "onsite",
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.currency,
                posted_at=job.posted_at or job.ingested_at,
            )
            for job in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
        filters={"locations": [], "departments": []},
    )
