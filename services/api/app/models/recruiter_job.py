"""Recruiter job posting model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector as _Vector

    _EmbeddingType = _Vector(384)
except ImportError:
    import sqlalchemy as _sa

    _EmbeddingType = _sa.JSON()


class RecruiterJob(Base):
    """Job posting created by a recruiter on behalf of a client company."""

    __tablename__ = "recruiter_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    nice_to_haves: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Location & type
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_policy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Compensation
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(
        String(10), server_default="USD"
    )
    hourly_rate_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hourly_rate_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Client company
    client_company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recruiter_clients.id", ondelete="SET NULL"), nullable=True
    )

    # CRM fields
    priority: Mapped[str | None] = mapped_column(String(20), server_default="normal")
    positions_to_fill: Mapped[int] = mapped_column(Integer, server_default="1")
    positions_filled: Mapped[int] = mapped_column(Integer, server_default="0")
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_id_external: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Job-level primary contact (from migration Contact/Contact Slug)
    primary_contact = mapped_column(JSONB, nullable=True)

    # Cross-segment link to employer job
    employer_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("employer_jobs.id", ondelete="SET NULL"), nullable=True
    )

    # Recruiter-to-recruiter link (Sub's job → Prime's job)
    upstream_recruiter_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status & application
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="draft"
    )
    application_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Raw document text from upload (for re-parsing)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Embedding for semantic matching
    embedding = mapped_column(_EmbeddingType, nullable=True)

    # Dates
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    start_at: Mapped[datetime | None] = mapped_column(
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
    recruiter_profile = relationship("RecruiterProfile", back_populates="jobs")
    client = relationship("RecruiterClient", back_populates="jobs")
    pipeline_candidates = relationship(
        "RecruiterPipelineCandidate", back_populates="job"
    )
    employer_job = relationship("EmployerJob")
    upstream_job = relationship(
        "RecruiterJob", remote_side=[id], foreign_keys=[upstream_recruiter_job_id]
    )
