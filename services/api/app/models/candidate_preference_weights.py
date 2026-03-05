from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidatePreferenceWeights(Base):
    __tablename__ = "candidate_preference_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Weight multipliers for scoring components (clamped to 0.7–1.3)
    skill_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    title_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    location_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    salary_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )
    years_weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )

    # Accumulated signal data for weight derivation
    learned_signals: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )

    # Event counters
    positive_events: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    negative_events: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    last_recalculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
