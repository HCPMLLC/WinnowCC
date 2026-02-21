"""TalentPipeline model — silver medalist CRM for employers."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class TalentPipeline(Base):
    __tablename__ = "talent_pipeline"
    __table_args__ = (
        UniqueConstraint(
            "employer_id",
            "candidate_profile_id",
            name="uq_pipeline_employer_candidate",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    employer_id = Column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_profile_id = Column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pipeline_status = Column(
        String(50),
        nullable=False,
        default="warm_lead",
        index=True,
    )
    source_job_id = Column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_score = Column(Integer, nullable=True)
    tags = Column(JSONB, default=list)
    notes = Column(Text, nullable=True)
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    next_followup_at = Column(DateTime(timezone=True), nullable=True)
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
