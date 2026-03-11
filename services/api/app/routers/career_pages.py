"""Career page management API for employers and recruiters."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.schemas.career_page import (
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


def _get_tenant_info(user: User) -> tuple[int, str, str]:
    """Extract tenant info from user. Returns (tenant_id, tenant_type, plan_tier)."""
    if user.employer_profile:
        return (
            user.employer_profile.id,
            "employer",
            user.employer_profile.subscription_tier or "free",
        )
    elif user.recruiter_profile:
        return (
            user.recruiter_profile.id,
            "recruiter",
            user.recruiter_profile.subscription_tier or "trial",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Career pages require employer or recruiter account",
    )


@router.get("", response_model=CareerPageListResponse)
def list_pages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    tenant_id, tenant_type, _ = _get_tenant_info(user)
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
    tenant_id, tenant_type, plan_tier = _get_tenant_info(user)

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
    tenant_id, tenant_type, _ = _get_tenant_info(user)
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
    tenant_id, tenant_type, _ = _get_tenant_info(user)
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
    tenant_id, tenant_type, _ = _get_tenant_info(user)
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
    tenant_id, tenant_type, _ = _get_tenant_info(user)
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

    tenant_id, tenant_type, _ = _get_tenant_info(user)
    try:
        get_career_page(db, page_id, tenant_id, tenant_type)
    except CareerPageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None

    kit = scrape_brand(website_url)
    return kit.model_dump()
