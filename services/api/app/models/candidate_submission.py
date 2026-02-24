"""Candidate submission model for cross-segment visibility."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CandidateSubmission(Base):
    """Bridge between recruiter pipeline and employer jobs.

    Tracks when a recruiter submits a candidate to a job, enabling:
    - Employers to see all recruiter submissions in one view
    - Recruiters to get warned about duplicate submissions
    - Candidates to know who is representing them
    """

    __tablename__ = "candidate_submissions"
    __table_args__ = (
        UniqueConstraint(
            "employer_job_id",
            "candidate_profile_id",
            "recruiter_profile_id",
            name="uq_submission_employer_job_candidate_recruiter",
        ),
        UniqueConstraint(
            "recruiter_job_id",
            "candidate_profile_id",
            name="uq_submission_recruiter_job_candidate",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Platform employer job (set when employer is on Winnow)
    employer_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("employer_jobs.id", ondelete="SET NULL"), nullable=True
    )
    # Recruiter's copy of the job (always set)
    recruiter_job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recruiter_jobs.id", ondelete="CASCADE"), nullable=False
    )
    candidate_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_candidate_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_pipeline_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )

    # External employer info (used when employer is NOT on Winnow)
    external_company_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    external_job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Submission tracking
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(50), server_default="submitted")
    # submitted, under_review, accepted, rejected, withdrawn
    is_first_submission: Mapped[bool] = mapped_column(Boolean, server_default="false")

    # Employer response
    employer_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    employer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    employer_job = relationship("EmployerJob")
    candidate_profile = relationship("CandidateProfile")
    recruiter_profile = relationship("RecruiterProfile")
    recruiter_job = relationship("RecruiterJob")
