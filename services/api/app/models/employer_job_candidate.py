"""Cached pre-computed candidate matches for employer jobs."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EmployerJobCandidate(Base):
    """Pre-computed match between an employer job and a candidate profile."""

    __tablename__ = "employer_job_candidates"
    __table_args__ = (
        UniqueConstraint(
            "employer_job_id",
            "candidate_profile_id",
            name="uq_employer_job_candidate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    matched_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Denormalized filter columns (populated from CandidateProfile.profile_json)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    job = relationship("EmployerJob")
    profile = relationship("CandidateProfile")
