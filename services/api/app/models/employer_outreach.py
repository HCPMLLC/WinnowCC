"""Employer outreach models — sequences and enrollments for candidate outreach."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _generate_token() -> str:
    return uuid.uuid4().hex


class EmployerOutreachSequence(Base):
    """Reusable multi-step email outreach sequence defined by an employer."""

    __tablename__ = "employer_outreach_sequences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    employer_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    employer_profile = relationship("EmployerProfile")
    job = relationship("EmployerJob")
    enrollments = relationship(
        "EmployerOutreachEnrollment",
        back_populates="sequence",
        cascade="all, delete-orphan",
    )


class EmployerOutreachEnrollment(Base):
    """Enrollment of a candidate in an employer outreach sequence."""

    __tablename__ = "employer_outreach_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id",
            "candidate_profile_id",
            name="uq_employer_enrollment_seq_candidate",
        ),
        Index(
            "ix_employer_enrollment_status_next_send", "status", "next_send_at"
        ),
        Index("ix_employer_enrollment_employer", "employer_profile_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_outreach_sequences.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    employer_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    current_step: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    unsubscribe_token: Mapped[str] = mapped_column(
        String(64), default=_generate_token, nullable=False
    )
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

    # Career page tracking
    career_page_application_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    sequence = relationship("EmployerOutreachSequence", back_populates="enrollments")
    candidate_profile = relationship("CandidateProfile")
    employer_profile = relationship("EmployerProfile")
