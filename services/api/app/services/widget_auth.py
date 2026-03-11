"""Widget authentication service."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.widget_api_key import WidgetApiKey, WidgetApiKeyUsage

logger = logging.getLogger(__name__)


class InvalidApiKey(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


class DomainNotAllowed(Exception):
    pass


def _extract_domain(url: str) -> str | None:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc.lower()
    except Exception:
        return None


async def validate_api_key(
    db: AsyncSession, api_key: str, request: Request
) -> WidgetApiKey:
    """Validate widget API key. Raises on failure."""
    key_hash = WidgetApiKey.hash_key(api_key)

    result = await db.execute(
        select(WidgetApiKey).where(WidgetApiKey.key_hash == key_hash)
    )
    key_record = result.scalar_one_or_none()

    if not key_record or not key_record.active:
        raise InvalidApiKey("Invalid or inactive API key")

    # Check domain restriction
    origin = request.headers.get("origin") or request.headers.get("referer")
    if key_record.allowed_domains and origin:
        origin_domain = _extract_domain(origin)
        if origin_domain and origin_domain not in key_record.allowed_domains:
            raise DomainNotAllowed(f"Domain '{origin_domain}' not allowed")

    # Check rate limit
    current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(WidgetApiKeyUsage).where(
            and_(
                WidgetApiKeyUsage.api_key_id == key_record.id,
                WidgetApiKeyUsage.hour == current_hour,
            )
        )
    )
    usage = result.scalar_one_or_none()

    if usage and usage.request_count >= key_record.rate_limit_per_hour:
        raise RateLimitExceeded(
            f"Rate limit exceeded ({key_record.rate_limit_per_hour}/hour)"
        )

    # Increment usage
    if usage:
        usage.request_count += 1
    else:
        db.add(
            WidgetApiKeyUsage(
                api_key_id=key_record.id,
                hour=current_hour,
                request_count=1,
            )
        )

    key_record.last_used_at = datetime.utcnow()
    key_record.request_count += 1
    await db.commit()

    return key_record


async def create_api_key(
    db: AsyncSession,
    tenant_id: int,
    tenant_type: str,
    name: str | None = None,
    allowed_domains: list[str] | None = None,
    environment: str = "live",
) -> tuple[WidgetApiKey, str]:
    """Create new API key. Returns (record, full_key)."""
    full_key, key_hash = WidgetApiKey.generate_key(environment)

    key_record = WidgetApiKey(
        tenant_id=tenant_id,
        tenant_type=tenant_type,
        key_prefix=f"pk_{environment}_",
        key_suffix=full_key[-8:],
        key_hash=key_hash,
        name=name,
        allowed_domains=allowed_domains,
    )

    db.add(key_record)
    await db.commit()
    await db.refresh(key_record)

    return key_record, full_key


async def list_api_keys(
    db: AsyncSession, tenant_id: int, tenant_type: str
) -> list[WidgetApiKey]:
    result = await db.execute(
        select(WidgetApiKey)
        .where(
            and_(
                WidgetApiKey.tenant_id == tenant_id,
                WidgetApiKey.tenant_type == tenant_type,
            )
        )
        .order_by(WidgetApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(
    db: AsyncSession, key_id: UUID, tenant_id: int, tenant_type: str
) -> None:
    result = await db.execute(
        select(WidgetApiKey).where(
            and_(
                WidgetApiKey.id == key_id,
                WidgetApiKey.tenant_id == tenant_id,
                WidgetApiKey.tenant_type == tenant_type,
            )
        )
    )
    key_record = result.scalar_one_or_none()
    if key_record:
        key_record.active = False
        await db.commit()


async def delete_api_key(
    db: AsyncSession, key_id: UUID, tenant_id: int, tenant_type: str
) -> None:
    result = await db.execute(
        select(WidgetApiKey).where(
            and_(
                WidgetApiKey.id == key_id,
                WidgetApiKey.tenant_id == tenant_id,
                WidgetApiKey.tenant_type == tenant_type,
            )
        )
    )
    key_record = result.scalar_one_or_none()
    if key_record:
        await db.delete(key_record)
        await db.commit()
