"""Cached pre-computed candidate matches for marketplace (ingested) jobs."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterMarketplaceMatch(Base):
    """Pre-computed match between an ingested job and a recruiter's candidate."""

    __tablename__ = "recruiter_marketplace_matches"
    __table_args__ = (
        UniqueConstraint(
            "recruiter_profile_id",
            "job_id",
            "candidate_profile_id",
            name="uq_recruiter_marketplace_match",
        ),
        Index(
            "ix_marketplace_match_lookup",
            "recruiter_profile_id",
            "job_id",
            "match_score",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
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
    recruiter_profile = relationship("RecruiterProfile")
    job = relationship("Job")
    profile = relationship("CandidateProfile")
