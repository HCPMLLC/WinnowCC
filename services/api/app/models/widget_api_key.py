"""
Widget API key models for embeddable widgets.
Keys authenticate widget requests and enforce rate limits.
"""

import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.db.base import Base


class WidgetApiKey(Base):
    """API key for widget authentication."""

    __tablename__ = "widget_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(Integer, nullable=False, index=True)
    tenant_type = Column(String(20), nullable=False)

    key_prefix = Column(String(20), nullable=False)  # pk_live_ or pk_test_
    key_suffix = Column(String(8), nullable=False)  # Last 8 chars for display
    key_hash = Column(String(64), nullable=False, unique=True)

    name = Column(String(100), nullable=True)
    allowed_domains = Column(ARRAY(String), nullable=True)  # CORS whitelist
    rate_limit_per_hour = Column(Integer, default=1000)

    active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_widget_api_keys_tenant", "tenant_id", "tenant_type"),
        Index("ix_widget_api_keys_hash", "key_hash"),
    )

    @classmethod
    def generate_key(cls, environment: str = "live") -> tuple[str, str]:
        """Generate new API key. Returns (full_key, key_hash)."""
        prefix = f"pk_{environment}_"
        random_part = secrets.token_urlsafe(32)
        full_key = f"{prefix}{random_part}"
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, key_hash

    @classmethod
    def hash_key(cls, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()


class WidgetApiKeyUsage(Base):
    """Hourly usage tracking for rate limiting."""

    __tablename__ = "widget_api_key_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("widget_api_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    hour = Column(DateTime, nullable=False)
    request_count = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_widget_api_key_usage_key_hour", "api_key_id", "hour"),
    )
