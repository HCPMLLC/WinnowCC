"""Recruiter pipeline candidate tracking model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterPipelineCandidate(Base):
    """Candidate tracked in a recruiter's CRM pipeline."""

    __tablename__ = "recruiter_pipeline_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    recruiter_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )

    # External candidate fields (for candidates not on the platform)
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_linkedin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_resume_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Professional context
    current_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), server_default="sourced")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bulk attach tracking
    bulk_attach_batch_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    bulk_attach_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bulk_attach_matched_by: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outreach_count: Mapped[int] = mapped_column(Integer, server_default="0")
    last_outreach_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    recruiter_profile = relationship(
        "RecruiterProfile", back_populates="pipeline_candidates"
    )
    job = relationship("RecruiterJob", back_populates="pipeline_candidates")
    candidate_profile = relationship("CandidateProfile")
