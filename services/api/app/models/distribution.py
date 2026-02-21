"""Job distribution models for multi-board publishing."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BoardConnection(Base):
    """Employer's connection/credentials for an external job board."""

    __tablename__ = "board_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    board_type: Mapped[str] = mapped_column(String(50), nullable=False)
    board_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Credentials (encrypted at rest)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    feed_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Sync tracking
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    employer = relationship("EmployerProfile", back_populates="board_connections")
    distributions = relationship(
        "JobDistribution",
        back_populates="board_connection",
        cascade="all, delete-orphan",
    )


class JobDistribution(Base):
    """Tracks a job's distribution status on a specific board."""

    __tablename__ = "job_distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    board_connection_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("board_connections.id", ondelete="CASCADE"),
        nullable=False,
    )

    external_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), server_default="pending", nullable=False
    )

    # Timestamps
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    live_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    feed_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metrics
    impressions: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    clicks: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    applications: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False
    )
    cost_spent: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), server_default="0", nullable=False
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    employer_job = relationship("EmployerJob", back_populates="distributions")
    board_connection = relationship("BoardConnection", back_populates="distributions")
    events = relationship(
        "DistributionEvent",
        back_populates="distribution",
        cascade="all, delete-orphan",
        order_by="DistributionEvent.created_at.desc()",
    )


class DistributionEvent(Base):
    """Audit log entry for a distribution action."""

    __tablename__ = "distribution_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    distribution_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_distributions.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    distribution = relationship("JobDistribution", back_populates="events")
