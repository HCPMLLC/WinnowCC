"""
Application session models for Sieve-guided applications.

Tracks the application flow from start to completion, including
Sieve conversation history and profile completeness progress.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from app.db.base import Base


class ApplicationStatus:
    STARTED = "started"
    RESUME_UPLOADED = "resume_uploaded"
    PROFILE_BUILDING = "profile_building"
    QUESTIONS_PENDING = "questions_pending"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class CareerPageApplication(Base):
    """
    An application session through a career page.

    Tracks the candidate's journey from clicking "Apply" to submission.
    Supports both new candidates and existing Winnow users.
    """

    __tablename__ = "career_page_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source
    career_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("career_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id = Column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Candidate (may be null until identified/created)
    candidate_id = Column(
        Integer,
        ForeignKey("candidate.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Temporary identification (before account creation)
    session_token = Column(String(64), unique=True, nullable=False)
    email = Column(String(255), nullable=True, index=True)

    # Application state
    status = Column(String(20), nullable=False, default=ApplicationStatus.STARTED)

    # Profile completeness tracking
    completeness_score = Column(Integer, default=0)  # 0-100
    missing_fields = Column(JSONB, default=list)

    # Sieve conversation
    conversation_history = Column(JSONB, default=list)

    # Resume data
    resume_file_url = Column(String(500), nullable=True)
    resume_parsed_data = Column(JSONB, nullable=True)

    # Custom question responses (extracted from conversation)
    question_responses = Column(JSONB, default=dict)

    # Cross-job recommendations shown
    cross_job_recommendations = Column(JSONB, default=list)
    additional_applications = Column(ARRAY(Integer), default=list)  # Job IDs applied to

    # IPS calculated at submission
    ips_score = Column(Integer, nullable=True)
    ips_breakdown = Column(JSONB, nullable=True)

    # Metadata
    source_url = Column(String(500), nullable=True)
    utm_params = Column(JSONB, nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_career_page_applications_session", "session_token"),
        Index("ix_career_page_applications_email", "email"),
        Index("ix_career_page_applications_status", "status"),
        Index("ix_career_page_applications_job", "job_id"),
        UniqueConstraint(
            "career_page_id",
            "job_id",
            "email",
            name="uq_career_page_application_email_job",
        ),
    )

    @property
    def is_complete(self) -> bool:
        return self.status == ApplicationStatus.COMPLETED

    @property
    def can_submit(self) -> bool:
        """Check if application has minimum required data."""
        if self.email is None:
            return False
        return True
