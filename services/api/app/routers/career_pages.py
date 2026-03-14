"""Career page management API for employers and recruiters."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.career_page_application import CareerPageApplication
from app.models.job import Job
from app.models.user import User
from app.schemas.career_page import (
    ApplicationDetailResponse,
    ApplicationListResponse,
    ApplicationSummaryItem,
    CareerPageCreate,
    CareerPageListResponse,
    CareerPagePublishRequest,
    CareerPageResponse,
    CareerPageUpdate,
)
from app.services.auth import get_current_user
from app.services.career_page_service import (
    CareerPageLimitExceeded,
    CareerPageNotFound,
    CareerPageSlugTaken,
    create_career_page,
    delete_career_page,
    get_career_page,
    list_career_pages,
    publish_career_page,
    update_career_page,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/career-pages", tags=["career-pages"])


def _get_tenant_info(user: User, db: Session) -> tuple[int, str, str]:
    """Extract tenant info from user. Returns (tenant_id, tenant_type, plan_tier).

    Auto-creates a recruiter profile if the user has the recruiter role
    but no profile row yet (mirrors get_recruiter_profile in auth.py).
    """
    if user.employer_profile:
        return (
            user.employer_profile.id,
            "employer",
            user.employer_profile.subscription_tier or "free",
        )

    if user.recruiter_profile:
        return (
            user.recruiter_profile.id,
            "recruiter",
            user.recruiter_profile.subscription_tier or "trial",
        )

    # Auto-create recruiter profile for users with recruiter role
    if getattr(user, "role", None) == "recruiter":
        from app.models.recruiter import RecruiterProfile

        profile = db.execute(
            select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
        ).scalar_one_or_none()
        if profile is None:
            domain = (user.email or "").split("@")[-1].split(".")[0].title() or "My Company"
            profile = RecruiterProfile(user_id=user.id, company_name=domain)
            profile.start_trial()
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return (profile.id, "recruiter", profile.subscription_tier or "trial")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Career pages require employer or recruiter account",
    )


@router.get("", response_model=CareerPageListResponse)
def list_pages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    pages = list_career_pages(db, tenant_id, tenant_type)
    return CareerPageListResponse(
        pages=[CareerPageResponse.model_validate(p) for p in pages],
        total=len(pages),
    )


@router.post(
    "", response_model=CareerPageResponse, status_code=status.HTTP_201_CREATED
)
def create_page(
    data: CareerPageCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, plan_tier = _get_tenant_info(user, db)

    try:
        page = create_career_page(db, tenant_id, tenant_type, plan_tier, data)
        return CareerPageResponse.model_validate(page)
    except CareerPageLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(e)
        ) from None
    except CareerPageSlugTaken as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None


@router.get("/{page_id}", response_model=CareerPageResponse)
def get_page(
    page_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        page = get_career_page(db, page_id, tenant_id, tenant_type)
        return CareerPageResponse.model_validate(page)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None


@router.put("/{page_id}", response_model=CareerPageResponse)
def update_page(
    page_id: UUID,
    data: CareerPageUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        page = update_career_page(db, page_id, tenant_id, tenant_type, data)
        return CareerPageResponse.model_validate(page)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None
    except CareerPageSlugTaken as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from None


@router.post("/{page_id}/publish", response_model=CareerPageResponse)
def publish_page(
    page_id: UUID,
    data: CareerPagePublishRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        page = publish_career_page(
            db, page_id, tenant_id, tenant_type, data.publish
        )
        return CareerPageResponse.model_validate(page)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(
    page_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        delete_career_page(db, page_id, tenant_id, tenant_type)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None


@router.post("/{page_id}/import-branding")
def import_branding(
    page_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
    website_url: str = Body(..., embed=True),
):
    """Scrape a website and return extracted branding (colors, logo, fonts, hero)."""
    from app.services.brand_scraper import scrape_brand

    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        get_career_page(db, page_id, tenant_id, tenant_type)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None

    kit = scrape_brand(website_url)
    return kit.model_dump()


@router.get("/{page_id}/applications", response_model=ApplicationListResponse)
def list_applications(
    page_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
    status_filter: str | None = None,
):
    """List applications for a career page."""
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        get_career_page(db, page_id, tenant_id, tenant_type)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None

    query = select(CareerPageApplication).where(
        CareerPageApplication.career_page_id == page_id
    )
    if status_filter:
        query = query.where(CareerPageApplication.status == status_filter)
    query = query.order_by(CareerPageApplication.started_at.desc())

    apps = db.execute(query).scalars().all()

    # Batch-load job titles
    job_ids = {a.job_id for a in apps}
    jobs_map: dict[int, str] = {}
    if job_ids:
        jobs = db.execute(select(Job).where(Job.id.in_(job_ids))).scalars().all()
        jobs_map = {j.id: j.title for j in jobs}

    items = []
    for a in apps:
        parsed = a.resume_parsed_data or {}
        name = parsed.get("full_name") or parsed.get("name")
        items.append(
            ApplicationSummaryItem(
                id=a.id,
                email=a.email,
                applicant_name=name,
                job_id=a.job_id,
                job_title=jobs_map.get(a.job_id),
                status=a.status,
                completeness_score=a.completeness_score or 0,
                ips_score=a.ips_score,
                started_at=a.started_at,
                completed_at=a.completed_at,
            )
        )

    return ApplicationListResponse(applications=items, total=len(items))


@router.get(
    "/{page_id}/applications/{app_id}",
    response_model=ApplicationDetailResponse,
)
def get_application_detail(
    page_id: UUID,
    app_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    """Get full details for a single application."""
    tenant_id, tenant_type, _ = _get_tenant_info(user, db)
    try:
        get_career_page(db, page_id, tenant_id, tenant_type)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None

    app = db.execute(
        select(CareerPageApplication).where(
            CareerPageApplication.id == app_id,
            CareerPageApplication.career_page_id == page_id,
        )
    ).scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        )

    # Job title
    job = db.execute(select(Job).where(Job.id == app.job_id)).scalar_one_or_none()
    parsed = app.resume_parsed_data or {}
    name = parsed.get("full_name") or parsed.get("name")

    return ApplicationDetailResponse(
        id=app.id,
        email=app.email,
        applicant_name=name,
        job_id=app.job_id,
        job_title=job.title if job else None,
        status=app.status,
        completeness_score=app.completeness_score or 0,
        ips_score=app.ips_score,
        ips_breakdown=app.ips_breakdown,
        resume_file_url=app.resume_file_url,
        resume_parsed_data=app.resume_parsed_data,
        question_responses=app.question_responses,
        source_url=app.source_url,
        utm_params=app.utm_params,
        cross_job_recommendations=app.cross_job_recommendations,
        started_at=app.started_at,
        completed_at=app.completed_at,
    )
