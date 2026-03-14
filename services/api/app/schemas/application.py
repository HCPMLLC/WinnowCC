"""Pydantic schemas for career page applications."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ============================================================
# Application Session
# ============================================================


class ApplicationStartRequest(BaseModel):
    """Start a new application."""

    job_id: int
    email: EmailStr
    source_url: str | None = None
    utm_params: dict[str, str] | None = None


class ApplicationStartResponse(BaseModel):
    """Response when starting application."""

    application_id: UUID
    session_token: str
    job_title: str
    company_name: str
    sieve_welcome: str
    show_resume_upload: bool = True
    show_linkedin_import: bool = True


class ApplicationStatusResponse(BaseModel):
    """Current application status."""

    application_id: UUID
    status: str
    completeness_score: int
    missing_fields: list[dict[str, Any]]
    can_submit: bool
    ips_preview: int | None = None
    cross_job_recommendations: list[dict[str, Any]] = []


# ============================================================
# Resume Upload
# ============================================================


class ResumeUploadResponse(BaseModel):
    """Response after resume upload."""

    success: bool
    parsed_data: dict[str, Any] | None = None
    completeness_score: int
    missing_fields: list[dict[str, Any]]
    sieve_response: str
    existing_applicant: bool = False
    prefilled_form: dict[str, Any] | None = None


# ============================================================
# Application Form (replaces Sieve chat)
# ============================================================


class ApplicationFormData(BaseModel):
    """Form data submitted during application."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    address: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=2)
    zip_code: str | None = Field(None, max_length=20)
    phone: str = Field(..., min_length=1, max_length=50)
    total_years_experience: int = Field(..., ge=0, le=99)
    expected_salary: int | None = Field(None, ge=0)
    remote_preference: str | None = Field(None, pattern="^(remote|hybrid|onsite)$")
    job_type_preference: str | None = Field(
        None, pattern="^(permanent|contract|temporary)$"
    )
    work_authorization: str | None = Field(None, max_length=100)
    relocation_willingness: str | None = Field(None, pattern="^(yes|no)$")


class ApplicationFormResponse(BaseModel):
    """Response after form submission."""

    success: bool
    completeness_score: int
    can_submit: bool


# ============================================================
# Cross-Job Matching
# ============================================================


class CrossJobMatch(BaseModel):
    """A recommended job based on candidate profile."""

    job_id: int
    title: str
    location: str | None = None
    ips_score: int
    explanation: str
    already_applied: bool = False


class CrossJobPitchResponse(BaseModel):
    """Cross-job recommendations for the candidate."""

    matches: list[CrossJobMatch]
    pitch_message: str


# ============================================================
# Application Submission
# ============================================================


class ApplicationSubmitRequest(BaseModel):
    """Submit the completed application."""

    apply_to_additional: list[int] = []  # Additional job IDs


class ApplicationSubmitResponse(BaseModel):
    """Response after submission."""

    success: bool
    application_id: UUID
    ips_score: int | None = None
    ips_breakdown: dict[str, Any] = {}
    additional_applications: list[int] = []
    message: str
