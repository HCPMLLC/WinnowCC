"""Employer team and interview feedback models (P53)."""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class EmployerTeamMember(Base):
    __tablename__ = "employer_team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employer_id = Column(
        Integer,
        ForeignKey("employer_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(
        String(50),
        nullable=False,
        default="viewer",
    )
    job_access = Column(JSONB, nullable=True)
    invited_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    accepted_at = Column(DateTime(timezone=True), nullable=True)


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employer_job_id = Column(
        Integer,
        ForeignKey("employer_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_profile_id = Column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    interviewer_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    interview_type = Column(
        String(50),
        nullable=False,
        default="phone_screen",
    )
    rating = Column(Integer, nullable=True)
    recommendation = Column(String(50), nullable=True)
    strengths = Column(Text, nullable=True)
    concerns = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
