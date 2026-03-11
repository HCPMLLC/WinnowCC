"""
Cross-job recommendation cache.
When candidate applies for Job A, calculate fit for Jobs B, C, D.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class CrossJobRecommendation(Base):
    """Cached cross-job match recommendation."""

    __tablename__ = "cross_job_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    candidate_id = Column(
        Integer,
        ForeignKey("candidate.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommended_job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    ips_score = Column(Integer, nullable=False)  # 0-100
    explanation = Column(Text, nullable=True)  # LLM-generated

    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "source_job_id",
            "recommended_job_id",
            name="uq_cross_job_recommendation",
        ),
        Index("ix_cross_job_recommendations_candidate", "candidate_id"),
        Index("ix_cross_job_recommendations_expires", "expires_at"),
    )

    @classmethod
    def default_expiry(cls) -> datetime:
        return datetime.utcnow() + timedelta(hours=24)
