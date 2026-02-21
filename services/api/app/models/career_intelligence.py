"""Career intelligence models — briefs, market intel, predictions, trajectories."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecruiterCandidateBrief(Base):
    """AI-generated candidate brief for recruiters/employers."""

    __tablename__ = "recruiter_candidate_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
    generated_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    brief_type: Mapped[str] = mapped_column(String(50), nullable=False)
    brief_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    brief_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MarketIntel(Base):
    """Cached market intelligence data (salary ranges, demand signals)."""

    __tablename__ = "market_intel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sample_size: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TimeFillPrediction(Base):
    """Time-to-fill prediction for an employer job."""

    __tablename__ = "time_to_fill_predictions"
    __table_args__ = (Index("idx_ttf_employer_job_id", "employer_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employer_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    predicted_days: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    factors_json: Mapped[dict | None] = mapped_column(JSONB)
    actual_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CareerTrajectory(Base):
    """AI-predicted career trajectory for a candidate."""

    __tablename__ = "career_trajectories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    trajectory_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
