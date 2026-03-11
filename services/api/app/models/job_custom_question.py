"""
Custom application questions per job.
Allows employers/recruiters to add screening questions.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.db.base import Base


class JobCustomQuestion(Base):
    """Custom screening question for a job posting."""

    __tablename__ = "job_custom_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    question_text = Column(Text, nullable=False)
    question_type = Column(String(20), nullable=False, default="text")
    # Types: text, select, multiselect, boolean, number, date

    options = Column(JSONB, nullable=True)  # For select/multiselect
    required = Column(Boolean, default=False)
    min_length = Column(Integer, nullable=True)
    max_length = Column(Integer, nullable=True)

    sieve_prompt_hint = Column(Text, nullable=True)
    # Hint for Sieve on how to ask naturally

    order_index = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_job_custom_questions_job", "job_id"),)


class CandidateQuestionResponse(Base):
    """Candidate's response to a custom question."""

    __tablename__ = "candidate_question_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        Integer,
        ForeignKey("candidate.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_custom_questions.id", ondelete="CASCADE"),
        nullable=False,
    )

    response_text = Column(Text, nullable=True)
    response_options = Column(ARRAY(String), nullable=True)
    response_boolean = Column(Boolean, nullable=True)

    answered_via = Column(String(20), default="sieve")  # sieve | form | import
    confidence_score = Column(Integer, nullable=True)  # Sieve's confidence 0-100

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            "question_id",
            name="uq_candidate_question_response",
        ),
    )
