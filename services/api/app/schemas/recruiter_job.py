"""Pydantic schemas for recruiter job endpoints."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_REMOTE_POLICIES = ["on-site", "hybrid", "remote"]
ALLOWED_EMPLOYMENT_TYPES = ["full-time", "part-time", "contract", "internship"]
ALLOWED_JOB_STATUSES = ["draft", "active", "paused", "closed"]


class RecruiterJobCreate(BaseModel):
    """Schema for creating a new recruiter job posting."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    requirements: str | None = None
    nice_to_haves: str | None = None
    location: str | None = Field(None, max_length=255)
    remote_policy: str | None = None
    employment_type: str | None = None
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str = Field(default="USD", max_length=10)
    hourly_rate_min: int | None = Field(None, ge=0)
    hourly_rate_max: int | None = Field(None, ge=0)
    client_company_name: str | None = Field(None, max_length=255)
    client_id: int | None = None
    status: str = Field(default="draft")
    application_url: str | None = Field(None, max_length=500)
    application_email: EmailStr | None = None
    closes_at: datetime | None = None
    start_at: datetime | None = None
    priority: str | None = Field(default="normal")
    positions_to_fill: int = Field(default=1, ge=1)
    department: str | None = Field(None, max_length=100)
    job_id_external: str | None = Field(None, max_length=100)
    job_category: str | None = Field(None, max_length=100)
    assigned_to_user_id: int | None = None

    @field_validator("remote_policy")
    @classmethod
    def validate_remote_policy(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_REMOTE_POLICIES:
            raise ValueError(
                f"remote_policy must be one of: {', '.join(ALLOWED_REMOTE_POLICIES)}"
            )
        return v

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_EMPLOYMENT_TYPES:
            raise ValueError(
                f"employment_type must be one of: {', '.join(ALLOWED_EMPLOYMENT_TYPES)}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ALLOWED_JOB_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(ALLOWED_JOB_STATUSES)}"
            )
        return v

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("salary_min") is not None:
            if v < info.data["salary_min"]:
                raise ValueError("salary_max must be >= salary_min")
        return v


ALLOWED_PRIORITIES = ["low", "normal", "high", "urgent"]


class RecruiterJobUpdate(BaseModel):
    """Schema for updating a recruiter job posting. All fields optional."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=10)
    requirements: str | None = None
    nice_to_haves: str | None = None
    location: str | None = Field(None, max_length=255)
    remote_policy: str | None = None
    employment_type: str | None = None
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    salary_currency: str | None = Field(None, max_length=10)
    hourly_rate_min: int | None = Field(None, ge=0)
    hourly_rate_max: int | None = Field(None, ge=0)
    client_company_name: str | None = Field(None, max_length=255)
    client_id: int | None = None
    status: str | None = None
    application_url: str | None = Field(None, max_length=500)
    application_email: EmailStr | None = None
    closes_at: datetime | None = None
    start_at: datetime | None = None
    priority: str | None = None
    positions_to_fill: int | None = Field(None, ge=1)
    positions_filled: int | None = Field(None, ge=0)
    department: str | None = Field(None, max_length=100)
    job_id_external: str | None = Field(None, max_length=100)
    job_category: str | None = Field(None, max_length=100)
    assigned_to_user_id: int | None = None

    @field_validator("remote_policy")
    @classmethod
    def validate_remote_policy(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_REMOTE_POLICIES:
            raise ValueError(
                f"remote_policy must be one of: {', '.join(ALLOWED_REMOTE_POLICIES)}"
            )
        return v

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_EMPLOYMENT_TYPES:
            raise ValueError(
                f"employment_type must be one of: {', '.join(ALLOWED_EMPLOYMENT_TYPES)}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_JOB_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(ALLOWED_JOB_STATUSES)}"
            )
        return v


class RecruiterJobResponse(BaseModel):
    """Schema for recruiter job posting response."""

    id: int
    recruiter_profile_id: int
    title: str
    description: str
    requirements: str | None = None
    nice_to_haves: str | None = None
    location: str | None = None
    remote_policy: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = "USD"
    hourly_rate_min: int | None = None
    hourly_rate_max: int | None = None
    client_company_name: str | None = None
    client_id: int | None = None
    client_name: str | None = None
    status: str
    application_url: str | None = None
    application_email: str | None = None
    posted_at: datetime | None = None
    closes_at: datetime | None = None
    start_at: datetime | None = None
    priority: str | None = "normal"
    positions_to_fill: int = 1
    positions_filled: int = 0
    department: str | None = None
    job_id_external: str | None = None
    job_category: str | None = None
    assigned_to_user_id: int | None = None
    # Cross-segment linking
    employer_job_id: int | None = None
    employer_company_name: str | None = None
    primary_contact: dict | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    matched_candidates_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RecruiterJobCandidateResult(BaseModel):
    """Single candidate in top-candidates ranking for a recruiter job."""

    id: int
    name: str
    headline: str | None = None
    location: str | None = None
    years_experience: int | None = None
    top_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    match_score: float = Field(..., ge=0, le=100)
    profile_visibility: str
    in_pipeline: bool = False


class RecruiterJobCandidatesResponse(BaseModel):
    """Response for matched candidates for a recruiter job."""

    job_id: int
    job_title: str
    candidates: list[RecruiterJobCandidateResult]
    total_cached: int


class CandidateMatchedJobResult(BaseModel):
    """Single job match result for a candidate."""

    job_id: int
    title: str
    client_company_name: str | None = None
    location: str | None = None
    remote_policy: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = "USD"
    status: str
    match_score: float = Field(..., ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)


class CandidateMatchedJobsResponse(BaseModel):
    """Response for matched jobs for a candidate."""

    candidate_profile_id: int
    jobs: list[CandidateMatchedJobResult]
    total: int
