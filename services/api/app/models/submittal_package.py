"""Submittal package model for recruiter candidate submissions to clients."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubmittalPackage(Base):
    """A packaged set of candidates submitted to a client for a recruiter job.

    Bundles AI-generated briefs and resumes into a single merged PDF
    that can be emailed to the client contact.
    """

    __tablename__ = "submittal_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    recruiter_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Recipient info
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Package contents
    candidate_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pipeline_candidate_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    package_options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Generated artifacts
    merged_pdf_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    cover_email_subject: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    cover_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50), server_default="building", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    email_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    recruiter_profile = relationship("RecruiterProfile")
    recruiter_job = relationship("RecruiterJob")
    client = relationship("RecruiterClient")
    submissions = relationship(
        "CandidateSubmission", back_populates="submittal_package"
    )
