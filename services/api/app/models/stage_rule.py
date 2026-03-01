"""Automated stage advancement rules for recruiter pipelines."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StageRule(Base):
    """Rule for auto-advancing pipeline candidates between stages."""

    __tablename__ = "stage_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    recruiter_job_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )

    from_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    condition_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", nullable=False
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    recruiter_profile = relationship("RecruiterProfile")
    job = relationship("RecruiterJob")
