"""Pydantic schemas for candidate submission endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CandidateSubmissionCreate(BaseModel):
    """Create a new candidate submission."""

    recruiter_job_id: int
    candidate_profile_id: int
    pipeline_candidate_id: int | None = None


class CandidateSubmissionUpdate(BaseModel):
    """Update a submission (employer side)."""

    status: str | None = None
    employer_notes: str | None = None


class CandidateSubmissionResponse(BaseModel):
    """Full submission response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_job_id: int | None = None
    recruiter_job_id: int
    candidate_profile_id: int
    recruiter_profile_id: int
    pipeline_candidate_id: int | None = None
    external_company_name: str | None = None
    external_job_title: str | None = None
    external_job_id: str | None = None
    submitted_at: datetime
    status: str = "submitted"
    is_first_submission: bool = False
    employer_response_at: datetime | None = None
    employer_notes: str | None = None
    created_at: datetime | None = None
    # Derived fields populated by the router
    candidate_name: str | None = None
    recruiter_company_name: str | None = None
    job_title: str | None = None


class SubmissionCheckResponse(BaseModel):
    """Result of a pre-submit duplicate check."""

    already_submitted: bool
    submission_count: int = 0
    first_submitted_at: datetime | None = None
    first_submitted_by: str | None = None
