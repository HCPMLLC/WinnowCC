"""Employer models for two-sided marketplace."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmployerProfile(Base):
    """Employer profile with company info and subscription details."""

    __tablename__ = "employer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Company information
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Primary contact
    contact_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Subscription & billing
    subscription_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="free"
    )
    subscription_status: Mapped[str | None] = mapped_column(
        String(50), server_default="active"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Usage counters (monthly rollover)
    ai_parsing_used: Mapped[int] = mapped_column(Integer, server_default="0")
    intro_requests_used: Mapped[int] = mapped_column(Integer, server_default="0")
    usage_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="employer_profile")
    jobs = relationship(
        "EmployerJob", back_populates="employer", cascade="all, delete-orphan"
    )
    candidate_views = relationship(
        "EmployerCandidateView",
        back_populates="employer",
        cascade="all, delete-orphan",
    )
    saved_candidates = relationship(
        "EmployerSavedCandidate",
        back_populates="employer",
        cascade="all, delete-orphan",
    )
    board_connections = relationship(
        "BoardConnection",
        back_populates="employer",
        cascade="all, delete-orphan",
    )


class EmployerJob(Base):
    """Job posting created by an employer."""

    __tablename__ = "employer_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    nice_to_haves: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Location & type
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_policy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Enhanced fields
    job_id_external: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    job_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certifications_required: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    job_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Compensation
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(
        String(10), server_default="USD"
    )
    equity_offered: Mapped[bool | None] = mapped_column(Boolean, server_default="false")

    # Status & application
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="draft"
    )
    application_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Dates
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Archival
    archived: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Document source tracking
    source_document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parsed_from_document: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    parsing_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Analytics
    view_count: Mapped[int | None] = mapped_column(Integer, server_default="0")
    application_count: Mapped[int | None] = mapped_column(Integer, server_default="0")

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    employer = relationship("EmployerProfile", back_populates="jobs")
    distributions = relationship(
        "JobDistribution",
        back_populates="employer_job",
        cascade="all, delete-orphan",
    )


class EmployerCandidateView(Base):
    """Tracks when an employer views a candidate profile."""

    __tablename__ = "employer_candidate_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    employer = relationship("EmployerProfile", back_populates="candidate_views")


class EmployerSavedCandidate(Base):
    """Employer's saved/favorited candidates."""

    __tablename__ = "employer_saved_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    employer = relationship("EmployerProfile", back_populates="saved_candidates")
