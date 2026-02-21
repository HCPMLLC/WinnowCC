"""Cached pre-computed candidate matches for recruiter jobs."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterJobCandidate(Base):
    """Pre-computed match between a recruiter job and a candidate profile."""

    __tablename__ = "recruiter_job_candidates"
    __table_args__ = (
        UniqueConstraint(
            "recruiter_job_id",
            "candidate_profile_id",
            name="uq_recruiter_job_candidate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="CASCADE"),
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

    # Relationships
    job = relationship("RecruiterJob")
    profile = relationship("CandidateProfile")
