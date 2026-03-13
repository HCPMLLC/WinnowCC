"""
Domain verification and SSL certificate models.

Tracks the lifecycle of custom domain setup from initial configuration
through DNS verification, SSL provisioning, and ongoing health monitoring.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class VerificationStatus:
    PENDING = "pending"
    VERIFYING = "verifying"
    DNS_VERIFIED = "dns_verified"
    SSL_PENDING = "ssl_pending"
    ACTIVE = "active"
    FAILED = "failed"
    EXPIRED = "expired"


class DomainVerification(Base):
    """
    Tracks custom domain verification state.

    Each career page can have one custom domain. This table tracks
    the verification process and SSL certificate state.
    """

    __tablename__ = "domain_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to career page
    career_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("career_pages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Domain configuration
    custom_domain = Column(String(255), unique=True, nullable=False)
    cname_target = Column(String(255), nullable=False)

    # Verification state
    status = Column(String(20), nullable=False, default=VerificationStatus.PENDING)

    # DNS verification
    dns_verified = Column(Boolean, default=False)
    dns_verified_at = Column(DateTime, nullable=True)
    dns_last_checked_at = Column(DateTime, nullable=True)
    dns_check_count = Column(Integer, default=0)
    dns_error = Column(Text, nullable=True)

    # SSL certificate
    ssl_provisioned = Column(Boolean, default=False)
    ssl_provisioned_at = Column(DateTime, nullable=True)
    ssl_expires_at = Column(DateTime, nullable=True)
    ssl_certificate_arn = Column(String(500), nullable=True)
    ssl_error = Column(Text, nullable=True)

    # ACME challenge (for Let's Encrypt HTTP-01)
    acme_challenge_token = Column(String(100), nullable=True)
    acme_challenge_response = Column(Text, nullable=True)

    # Health monitoring
    last_health_check_at = Column(DateTime, nullable=True)
    health_check_passed = Column(Boolean, default=False)
    consecutive_failures = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    career_page = relationship("CareerPage", backref="domain_verification")

    __table_args__ = (
        Index("ix_domain_verifications_domain", "custom_domain"),
        Index("ix_domain_verifications_status", "status"),
    )

    def __repr__(self):
        return f"<DomainVerification {self.custom_domain} ({self.status})>"

    @property
    def is_active(self) -> bool:
        return self.status == VerificationStatus.ACTIVE

    @property
    def needs_ssl_renewal(self) -> bool:
        if not self.ssl_expires_at:
            return False
        return datetime.utcnow() > (self.ssl_expires_at - timedelta(days=30))

    @property
    def verification_expired(self) -> bool:
        """Check if verification attempt has timed out (48 hours)."""
        if self.status != VerificationStatus.PENDING:
            return False
        return datetime.utcnow() > (self.created_at + timedelta(hours=48))


class DomainVerificationLog(Base):
    """Audit log for domain verification events."""

    __tablename__ = "domain_verification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    domain_verification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domain_verifications.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type = Column(String(50), nullable=False)
    details = Column(JSONB, default=dict)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "ix_domain_verification_logs_verification", "domain_verification_id"
        ),
        Index("ix_domain_verification_logs_created", "created_at"),
    )
