"""CandidateNotification model — stores notification history."""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.db.base import Base


class CandidateNotification(Base):
    __tablename__ = "candidate_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(
        Integer,
        ForeignKey("candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employer_job_id = Column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type = Column(String(50), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    read_at = Column(DateTime(timezone=True), nullable=True)
