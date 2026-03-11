"""Career page service for Sieve-scape."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.career_page import CareerPage
from app.schemas.career_page import CareerPageCreate, CareerPageUpdate

logger = logging.getLogger(__name__)


class CareerPageLimitExceeded(Exception):
    pass


class CareerPageSlugTaken(Exception):
    pass


class CareerPageNotFound(Exception):
    pass


# Tier limits for career pages
EMPLOYER_CAREER_PAGE_LIMITS = {
    "free": 0,
    "starter": 1,
    "pro": 3,
    "enterprise": 999,
}

RECRUITER_CAREER_PAGE_LIMITS = {
    "trial": 1,
    "solo": 1,
    "team": 5,
    "agency": 999,
}


def get_career_page_limit(tenant_type: str, plan_tier: str) -> int:
    if tenant_type == "employer":
        return EMPLOYER_CAREER_PAGE_LIMITS.get(plan_tier, 0)
    elif tenant_type == "recruiter":
        return RECRUITER_CAREER_PAGE_LIMITS.get(plan_tier, 0)
    return 0


def count_career_pages(db: Session, tenant_id: int, tenant_type: str) -> int:
    result = db.execute(
        select(func.count(CareerPage.id)).where(
            and_(
                CareerPage.tenant_id == tenant_id,
                CareerPage.tenant_type == tenant_type,
            )
        )
    )
    return result.scalar() or 0


def check_slug_available(
    db: Session, slug: str, exclude_id: UUID | None = None
) -> bool:
    query = select(CareerPage.id).where(CareerPage.slug == slug)
    if exclude_id:
        query = query.where(CareerPage.id != exclude_id)
    result = db.execute(query)
    return result.scalar() is None


def create_career_page(
    db: Session,
    tenant_id: int,
    tenant_type: str,
    plan_tier: str,
    data: CareerPageCreate,
) -> CareerPage:
    # Check limit
    limit = get_career_page_limit(tenant_type, plan_tier)
    current_count = count_career_pages(db, tenant_id, tenant_type)

    if current_count >= limit:
        raise CareerPageLimitExceeded(
            f"Career page limit reached ({limit} for {plan_tier} plan)"
        )

    if not check_slug_available(db, data.slug):
        raise CareerPageSlugTaken(f"Slug '{data.slug}' is already taken")

    cname_target = f"{data.slug}.careers.winnowcc.ai"

    page = CareerPage(
        tenant_id=tenant_id,
        tenant_type=tenant_type,
        slug=data.slug,
        name=data.name,
        page_title=data.page_title,
        meta_description=data.meta_description,
        config=data.config.model_dump(),
        cname_target=cname_target,
    )

    db.add(page)
    db.commit()
    db.refresh(page)

    logger.info(f"Created career page {page.slug} for {tenant_type} {tenant_id}")
    return page


def get_career_page(
    db: Session, page_id: UUID, tenant_id: int, tenant_type: str
) -> CareerPage:
    result = db.execute(
        select(CareerPage).where(
            and_(
                CareerPage.id == page_id,
                CareerPage.tenant_id == tenant_id,
                CareerPage.tenant_type == tenant_type,
            )
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise CareerPageNotFound(f"Career page {page_id} not found")
    return page


def get_career_page_by_slug(db: Session, slug: str) -> CareerPage | None:
    result = db.execute(select(CareerPage).where(CareerPage.slug == slug))
    return result.scalar_one_or_none()


def list_career_pages(
    db: Session, tenant_id: int, tenant_type: str
) -> list[CareerPage]:
    result = db.execute(
        select(CareerPage)
        .where(
            and_(
                CareerPage.tenant_id == tenant_id,
                CareerPage.tenant_type == tenant_type,
            )
        )
        .order_by(CareerPage.created_at.desc())
    )
    return list(result.scalars().all())


def update_career_page(
    db: Session,
    page_id: UUID,
    tenant_id: int,
    tenant_type: str,
    data: CareerPageUpdate,
) -> CareerPage:
    page = get_career_page(db, page_id, tenant_id, tenant_type)

    if data.slug and data.slug != page.slug:
        if not check_slug_available(db, data.slug, exclude_id=page_id):
            raise CareerPageSlugTaken(f"Slug '{data.slug}' is already taken")
        page.slug = data.slug
        page.cname_target = f"{data.slug}.careers.winnowcc.ai"

    if data.name is not None:
        page.name = data.name
    if data.page_title is not None:
        page.page_title = data.page_title
    if data.meta_description is not None:
        page.meta_description = data.meta_description
    if data.config is not None:
        page.config = data.config.model_dump()

    page.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(page)
    return page


def publish_career_page(
    db: Session,
    page_id: UUID,
    tenant_id: int,
    tenant_type: str,
    publish: bool = True,
) -> CareerPage:
    page = get_career_page(db, page_id, tenant_id, tenant_type)

    page.published = publish
    if publish and not page.published_at:
        page.published_at = datetime.utcnow()

    page.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(page)
    return page


def delete_career_page(
    db: Session, page_id: UUID, tenant_id: int, tenant_type: str
) -> None:
    page = get_career_page(db, page_id, tenant_id, tenant_type)
    db.delete(page)
    db.commit()


def increment_page_view(db: Session, page_id: UUID) -> None:
    db.execute(
        CareerPage.__table__.update()
        .where(CareerPage.id == page_id)
        .values(view_count=CareerPage.view_count + 1)
    )
    db.commit()
