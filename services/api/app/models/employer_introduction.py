"""Employer introduction request model — consent-gated employer-to-candidate contact."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmployerIntroductionRequest(Base):
    __tablename__ = "employer_introduction_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    employer_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    candidate_response_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    employer_profile = relationship("EmployerProfile")
    candidate_profile = relationship("CandidateProfile")
    employer_job = relationship("EmployerJob")
