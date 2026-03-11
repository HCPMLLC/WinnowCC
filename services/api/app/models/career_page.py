"""
Career page models for Sieve-scape.
Supports both employers and recruiters with tenant-based isolation.
"""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base


class CareerPage(Base):
    """
    A branded career page for an employer or recruiter.
    Each tenant can have multiple pages (tier-gated).
    """

    __tablename__ = "career_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant ownership (polymorphic — employer_profiles.id or recruiter_profiles.id)
    tenant_id = Column(Integer, nullable=False, index=True)
    tenant_type = Column(String(20), nullable=False)  # 'employer' or 'recruiter'

    # URL configuration
    slug = Column(String(100), unique=True, nullable=False, index=True)
    custom_domain = Column(String(255), unique=True, nullable=True)
    custom_domain_verified = Column(Boolean, default=False)
    custom_domain_ssl_provisioned = Column(Boolean, default=False)
    cname_target = Column(String(255), nullable=True)

    # Page metadata
    name = Column(String(200), nullable=False)
    page_title = Column(String(200), nullable=True)
    meta_description = Column(Text, nullable=True)

    # Builder configuration (JSONB)
    config = Column(JSONB, nullable=False, default=dict)

    # Publishing state
    published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)

    # Analytics
    view_count = Column(Integer, default=0)
    application_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_career_pages_tenant", "tenant_id", "tenant_type"),
    )

    @property
    def public_url(self) -> str:
        if self.custom_domain and self.custom_domain_verified:
            return f"https://{self.custom_domain}"
        return f"https://winnowcc.ai/careers/{self.slug}"

    @property
    def embed_url(self) -> str:
        return f"https://api.winnowcc.ai/embed/{self.slug}"


class CareerPageAnalytics(Base):
    """Daily analytics for career pages."""

    __tablename__ = "career_page_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    career_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("career_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = Column(DateTime, nullable=False)

    page_views = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    job_views = Column(Integer, default=0)
    applications_started = Column(Integer, default=0)
    applications_completed = Column(Integer, default=0)
    sieve_conversations = Column(Integer, default=0)
    traffic_sources = Column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint(
            "career_page_id", "date", name="uq_career_page_analytics_date"
        ),
    )
