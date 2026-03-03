from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Application status values: saved, applied, interviewing, rejected, offer
APPLICATION_STATUS_VALUES = ["saved", "applied", "interviewing", "rejected", "offer"]


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    interview_readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    offer_probability: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Interview Probability fields
    resume_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_letter_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_logistics_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    referred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interview_probability: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Semantic search similarity (0.0 – 1.0)
    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Application tracking status: saved, applied, interviewing, rejected, offer
    application_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Human-readable "why this job" explanation
    match_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
