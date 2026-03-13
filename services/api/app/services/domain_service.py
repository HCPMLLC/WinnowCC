"""
Domain management service.

Handles custom domain configuration, verification, and lifecycle.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_page import CareerPage
from app.models.domain_verification import (
    DomainVerification,
    DomainVerificationLog,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


class DomainLimitExceeded(Exception):
    pass


class DomainAlreadyExists(Exception):
    pass


class DomainNotFound(Exception):
    pass


class DomainNotAllowed(Exception):
    pass


async def check_domain_allowed(tenant_type: str, plan_tier: str) -> bool:
    """Check if tier allows custom domains."""
    allowed_tiers = {
        "employer": ["pro", "enterprise"],
        "recruiter": ["team", "agency"],
    }
    return plan_tier in allowed_tiers.get(tenant_type, [])


async def configure_domain(
    db: AsyncSession,
    career_page_id: UUID,
    domain: str,
    tenant_type: str,
    plan_tier: str,
) -> DomainVerification:
    """
    Configure a custom domain for a career page.

    Creates verification record and generates CNAME target.
    """
    if not await check_domain_allowed(tenant_type, plan_tier):
        raise DomainNotAllowed("Custom domains not available on your plan")

    # Check domain not already in use
    existing = await db.execute(
        select(DomainVerification).where(
            DomainVerification.custom_domain == domain
        )
    )
    if existing.scalar_one_or_none():
        raise DomainAlreadyExists(f"Domain {domain} is already configured")

    # Get career page
    page_result = await db.execute(
        select(CareerPage).where(CareerPage.id == career_page_id)
    )
    career_page = page_result.scalar_one_or_none()
    if not career_page:
        raise ValueError("Career page not found")

    # Check if page already has a domain — remove it
    existing_verification = await db.execute(
        select(DomainVerification).where(
            DomainVerification.career_page_id == career_page_id
        )
    )
    existing_ver = existing_verification.scalar_one_or_none()
    if existing_ver:
        await db.delete(existing_ver)

    # Generate CNAME target
    cname_target = f"{career_page.slug}.careers.winnowcc.ai"

    # Create verification record
    verification = DomainVerification(
        career_page_id=career_page_id,
        custom_domain=domain,
        cname_target=cname_target,
        status=VerificationStatus.PENDING,
    )
    db.add(verification)

    # Update career page
    career_page.custom_domain = domain
    career_page.custom_domain_verified = False
    career_page.cname_target = cname_target

    # Log event
    log = DomainVerificationLog(
        domain_verification_id=verification.id,
        event_type="domain_configured",
        details={"domain": domain, "cname_target": cname_target},
    )
    db.add(log)

    await db.commit()
    await db.refresh(verification)

    logger.info("Configured domain %s for career page %s", domain, career_page.slug)
    return verification


async def get_domain_status(
    db: AsyncSession,
    career_page_id: UUID,
) -> Optional[DomainVerification]:
    """Get current domain verification status."""
    result = await db.execute(
        select(DomainVerification).where(
            DomainVerification.career_page_id == career_page_id
        )
    )
    return result.scalar_one_or_none()


async def remove_domain(
    db: AsyncSession,
    career_page_id: UUID,
) -> None:
    """Remove custom domain from career page."""
    result = await db.execute(
        select(DomainVerification).where(
            DomainVerification.career_page_id == career_page_id
        )
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise DomainNotFound("No custom domain configured")

    # Get career page
    page_result = await db.execute(
        select(CareerPage).where(CareerPage.id == career_page_id)
    )
    career_page = page_result.scalar_one()

    # Update career page
    career_page.custom_domain = None
    career_page.custom_domain_verified = False
    career_page.custom_domain_ssl_provisioned = False
    career_page.cname_target = None

    # Log event
    log = DomainVerificationLog(
        domain_verification_id=verification.id,
        event_type="domain_removed",
        details={"domain": verification.custom_domain},
    )
    db.add(log)

    await db.delete(verification)
    await db.commit()

    logger.info("Removed domain %s", verification.custom_domain)


async def update_verification_status(
    db: AsyncSession,
    verification_id: UUID,
    status: str,
    error: Optional[str] = None,
) -> DomainVerification:
    """Update verification status."""
    result = await db.execute(
        select(DomainVerification).where(
            DomainVerification.id == verification_id
        )
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise DomainNotFound("Verification not found")

    old_status = verification.status
    verification.status = status
    verification.updated_at = datetime.utcnow()

    if error:
        if status == VerificationStatus.FAILED:
            verification.dns_error = error
        else:
            verification.ssl_error = error

    # Update career page if now active
    if status == VerificationStatus.ACTIVE:
        page_result = await db.execute(
            select(CareerPage).where(CareerPage.id == verification.career_page_id)
        )
        career_page = page_result.scalar_one()
        career_page.custom_domain_verified = True
        career_page.custom_domain_ssl_provisioned = True

    # Log status change
    log = DomainVerificationLog(
        domain_verification_id=verification_id,
        event_type="status_changed",
        details={"old_status": old_status, "new_status": status},
        error_message=error,
    )
    db.add(log)

    await db.commit()
    await db.refresh(verification)

    return verification


async def get_pending_verifications(
    db: AsyncSession,
    limit: int = 50,
) -> list[DomainVerification]:
    """Get domains pending DNS verification."""
    result = await db.execute(
        select(DomainVerification)
        .where(
            DomainVerification.status.in_(
                [VerificationStatus.PENDING, VerificationStatus.VERIFYING]
            )
        )
        .order_by(DomainVerification.dns_last_checked_at.asc().nullsfirst())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_domains_needing_ssl_renewal(
    db: AsyncSession,
) -> list[DomainVerification]:
    """Get domains with SSL certificates expiring soon."""
    from datetime import timedelta

    renewal_threshold = datetime.utcnow() + timedelta(days=30)

    result = await db.execute(
        select(DomainVerification).where(
            DomainVerification.status == VerificationStatus.ACTIVE,
            DomainVerification.ssl_expires_at < renewal_threshold,
        )
    )
    return list(result.scalars().all())
