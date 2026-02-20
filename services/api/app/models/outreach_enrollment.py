"""Outreach enrollment model — tracks a candidate's progress through a sequence."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OutreachEnrollment(Base):
    """Enrollment of a pipeline candidate in an outreach sequence."""

    __tablename__ = "outreach_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id", "pipeline_candidate_id", name="uq_enrollment_seq_candidate"
        ),
        Index("ix_enrollment_status_next_send", "status", "next_send_at"),
        Index("ix_enrollment_recruiter", "recruiter_profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("outreach_sequences.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_candidate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_pipeline_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    current_step: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    next_send_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    sequence = relationship("OutreachSequence", back_populates="enrollments")
    pipeline_candidate = relationship("RecruiterPipelineCandidate")
    recruiter_profile = relationship("RecruiterProfile")
