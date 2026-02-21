"""Recruiter activity audit trail model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterActivity(Base):
    """Activity log entry for recruiter CRM actions."""

    __tablename__ = "recruiter_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    pipeline_candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_pipeline_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    recruiter_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    recruiter_profile = relationship(
        "RecruiterProfile", back_populates="activities"
    )
    pipeline_candidate = relationship("RecruiterPipelineCandidate")
    job = relationship("RecruiterJob")
    client = relationship("RecruiterClient")
