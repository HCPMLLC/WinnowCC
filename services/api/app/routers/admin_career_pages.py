"""Admin career pages management router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.career_page import CareerPage
from app.models.employer import EmployerProfile
from app.models.recruiter import RecruiterProfile
from app.models.user import User
from app.services.auth import require_admin_user

router = APIRouter(prefix="/api/admin/career-pages", tags=["admin-career-pages"])


class AdminCareerPageResponse(BaseModel):
    id: str
    tenant_type: str
    tenant_id: int
    owner_name: str | None = None
    owner_email: str | None = None
    company: str | None = None
    name: str
    slug: str
    custom_domain: str | None = None
    custom_domain_verified: bool
    published: bool
    view_count: int
    application_count: int
    created_at: str | None = None
    published_at: str | None = None


@router.get("", response_model=list[AdminCareerPageResponse])
def list_career_pages(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminCareerPageResponse]:
    """List all career pages across employers and recruiters."""
    pages = (
        session.execute(
            select(CareerPage).order_by(CareerPage.created_at.desc())
        )
        .scalars()
        .all()
    )

    results = []
    for page in pages:
        owner_name = None
        owner_email = None
        company = None

        if page.tenant_type == "employer":
            profile = session.execute(
                select(EmployerProfile).where(EmployerProfile.id == page.tenant_id)
            ).scalar_one_or_none()
            if profile:
                company = profile.company_name
                user = session.execute(
                    select(User).where(User.id == profile.user_id)
                ).scalar_one_or_none()
                if user:
                    owner_name = (
                        user.full_name
                        or " ".join(
                            p for p in [user.first_name, user.last_name] if p
                        )
                        or None
                    )
                    owner_email = user.email
        elif page.tenant_type == "recruiter":
            profile = session.execute(
                select(RecruiterProfile).where(
                    RecruiterProfile.id == page.tenant_id
                )
            ).scalar_one_or_none()
            if profile:
                company = profile.company_name
                user = session.execute(
                    select(User).where(User.id == profile.user_id)
                ).scalar_one_or_none()
                if user:
                    owner_name = (
                        user.full_name
                        or " ".join(
                            p for p in [user.first_name, user.last_name] if p
                        )
                        or None
                    )
                    owner_email = user.email

        results.append(
            AdminCareerPageResponse(
                id=str(page.id),
                tenant_type=page.tenant_type,
                tenant_id=page.tenant_id,
                owner_name=owner_name,
                owner_email=owner_email,
                company=company,
                name=page.name,
                slug=page.slug,
                custom_domain=page.custom_domain,
                custom_domain_verified=page.custom_domain_verified or False,
                published=page.published or False,
                view_count=page.view_count or 0,
                application_count=page.application_count or 0,
                created_at=(
                    page.created_at.isoformat() if page.created_at else None
                ),
                published_at=(
                    page.published_at.isoformat() if page.published_at else None
                ),
            )
        )

    return results
