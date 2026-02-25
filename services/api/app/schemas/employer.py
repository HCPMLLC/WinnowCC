"""Pydantic schemas for employer endpoints."""

from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Free / consumer email domains that cannot verify company identity.
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "mail.com",
        "protonmail.com",
        "proton.me",
        "zoho.com",
        "yandex.com",
        "gmx.com",
        "gmx.net",
        "fastmail.com",
        "tutanota.com",
        "hey.com",
    }
)


def _extract_base_domain(url_or_email: str, *, is_email: bool = False) -> str:
    """Return the registrable base domain (e.g. 'acme.com') from a URL or email."""
    if is_email:
        domain = url_or_email.rsplit("@", 1)[-1].lower().strip()
    else:
        parsed = urlparse(
            url_or_email if "://" in url_or_email else f"https://{url_or_email}"
        )
        domain = (parsed.hostname or "").lower().strip()
    # Strip www prefix
    if domain.startswith("www."):
        domain = domain[4:]
    # For subdomains like hr.acme.com, keep last two parts
    parts = domain.split(".")
    if len(parts) > 2:
        domain = ".".join(parts[-2:])
    return domain


# ============================================================================
# EMPLOYER PROFILE SCHEMAS
# ============================================================================

ALLOWED_COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]

ALLOWED_INDUSTRIES = [
    "Aerospace & Defense",
    "Agriculture",
    "Automotive",
    "Construction",
    "Consulting",
    "Consumer Goods",
    "Education",
    "Energy & Utilities",
    "Entertainment & Media",
    "Financial Services",
    "Food & Beverage",
    "Government",
    "Healthcare",
    "Hospitality & Tourism",
    "Insurance",
    "Legal",
    "Logistics & Transportation",
    "Manufacturing",
    "Mining & Metals",
    "Nonprofit",
    "Pharmaceuticals",
    "Professional Services",
    "Real Estate",
    "Retail & E-Commerce",
    "Technology",
    "Telecommunications",
    "Other",
]


class EmployerProfileBase(BaseModel):
    """Base schema for employer profile with common fields."""

    company_name: str = Field(..., min_length=1, max_length=255)
    company_size: str | None = Field(None)
    industry: str | None = Field(None, max_length=100)
    company_website: str | None = Field(None, max_length=500)
    company_description: str | None = None
    company_logo_url: str | None = Field(None, max_length=500)
    billing_email: EmailStr | None = None

    # Primary contact
    contact_first_name: str | None = Field(None, max_length=100)
    contact_last_name: str | None = Field(None, max_length=100)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)

    @field_validator("company_size")
    @classmethod
    def validate_company_size(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_COMPANY_SIZES:
            raise ValueError(
                f"company_size must be one of: {', '.join(ALLOWED_COMPANY_SIZES)}"
            )
        return v

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_INDUSTRIES:
            raise ValueError(
                f"industry must be one of: {', '.join(ALLOWED_INDUSTRIES)}"
            )
        return v


class EmployerProfileCreate(EmployerProfileBase):
    """Schema for creating a new employer profile."""

    # Hierarchy & contract vehicle
    parent_employer_id: int | None = None
    contract_vehicle: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_contact_email_domain(self) -> "EmployerProfileCreate":
        email = self.contact_email
        website = self.company_website
        if not email or not website:
            return self

        email_domain = _extract_base_domain(email, is_email=True)
        website_domain = _extract_base_domain(website)

        if email_domain in FREE_EMAIL_DOMAINS:
            raise ValueError(
                f"Contact email must use a company domain (e.g. you@{website_domain}), "
                f"not a free email provider ({email_domain})."
            )

        if email_domain != website_domain:
            raise ValueError(
                f"Contact email domain ({email_domain}) does not match "
                f"company website domain ({website_domain}). "
                f"Please use an email address at {website_domain}."
            )

        return self


class EmployerProfileUpdate(BaseModel):
    """Schema for updating employer profile. All fields optional."""

    company_name: str | None = Field(None, min_length=1, max_length=255)
    company_size: str | None = None
    industry: str | None = Field(None, max_length=100)
    company_website: str | None = Field(None, max_length=500)
    company_description: str | None = None
    company_logo_url: str | None = Field(None, max_length=500)
    billing_email: EmailStr | None = None
    contact_first_name: str | None = Field(None, max_length=100)
    contact_last_name: str | None = Field(None, max_length=100)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)
    # Hierarchy & contract vehicle
    parent_employer_id: int | None = None
    contract_vehicle: str | None = Field(None, max_length=255)

    @field_validator("company_size")
    @classmethod
    def validate_company_size(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_COMPANY_SIZES:
            raise ValueError(
                f"company_size must be one of: {', '.join(ALLOWED_COMPANY_SIZES)}"
            )
        return v

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_INDUSTRIES:
            raise ValueError(
                f"industry must be one of: {', '.join(ALLOWED_INDUSTRIES)}"
            )
        return v


class EmployerProfileResponse(EmployerProfileBase):
    """Schema for employer profile response."""

    id: int
    user_id: int
    subscription_tier: str
    subscription_status: str | None = None
    trial_ends_at: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    # Hierarchy & contract vehicle
    parent_employer_id: int | None = None
    contract_vehicle: str | None = None
    parent_company_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ============================================================================
# JOB POSTING SCHEMAS
# ============================================================================

ALLOWED_REMOTE_POLICIES = ["on-site", "hybrid", "remote"]
ALLOWED_EMPLOYMENT_TYPES = ["full-time", "part-time", "contract", "internship"]
ALLOWED_JOB_STATUSES = ["draft", "active", "paused", "closed"]
ALLOWED_JOB_TYPES = ["permanent", "contract", "temporary", "seasonal"]
ALLOWED_JOB_CATEGORIES = [
    "Engineering",
    "Sales",
    "Marketing",
    "Design",
    "Product",
    "Operations",
    "Finance",
    "Human Resources",
    "Customer Success",
    "Customer Support",
    "Data Science",
    "Legal",
    "Executive",
    "Other",
]


class EmployerJobBase(BaseModel):
    """Base schema for job posting with common fields."""

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
    equity_offered: bool = Field(default=False)
    application_url: str | None = Field(None, max_length=500)
    application_email: EmailStr | None = None

    # Enhanced fields
    job_id_external: str | None = Field(None, max_length=100)
    start_date: date | None = None
    close_date: date | None = None
    job_category: str | None = Field(None, max_length=100)
    client_company_name: str | None = Field(None, max_length=255)
    department: str | None = Field(None, max_length=100)
    certifications_required: list[str] | None = None
    job_type: str | None = None

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

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_JOB_TYPES:
            raise ValueError(f"job_type must be one of: {', '.join(ALLOWED_JOB_TYPES)}")
        return v

    @field_validator("salary_max")
    @classmethod
    def validate_salary_range(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("salary_min") is not None:
            if v < info.data["salary_min"]:
                raise ValueError("salary_max must be >= salary_min")
        return v


class EmployerJobCreate(EmployerJobBase):
    """Schema for creating a new job posting."""

    pass


class EmployerJobUpdate(BaseModel):
    """Schema for updating a job posting. All fields optional."""

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
    equity_offered: bool | None = None
    application_url: str | None = Field(None, max_length=500)
    application_email: EmailStr | None = None
    status: str | None = None
    closes_at: datetime | None = None

    # Enhanced fields
    job_id_external: str | None = Field(None, max_length=100)
    start_date: date | None = None
    close_date: date | None = None
    job_category: str | None = Field(None, max_length=100)
    department: str | None = Field(None, max_length=100)
    certifications_required: list[str] | None = None
    job_type: str | None = None

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

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_JOB_TYPES:
            raise ValueError(f"job_type must be one of: {', '.join(ALLOWED_JOB_TYPES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_JOB_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(ALLOWED_JOB_STATUSES)}"
            )
        return v


class EmployerJobResponse(EmployerJobBase):
    """Schema for job posting response."""

    id: int
    employer_id: int
    status: str
    posted_at: datetime | None = None
    closes_at: datetime | None = None
    view_count: int | None = 0
    application_count: int | None = 0

    # Archival
    archived: bool = False
    archived_at: datetime | None = None
    archived_reason: str | None = None

    # Matched candidates with score > 50%
    matched_candidates_count: int = 0

    # Document parsing
    parsed_from_document: bool = False
    parsing_confidence: float | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDocumentUploadResponse(BaseModel):
    """Response from uploading and parsing a job document."""

    job_id: int
    parsed_data: dict[str, Any]
    confidence: float
    message: str


class BulkUploadFileResult(BaseModel):
    """Result for a single file in a bulk upload batch."""

    filename: str
    success: bool
    job_id: int | None = None
    title: str | None = None
    error: str | None = None


class BulkUploadResponse(BaseModel):
    """Response from bulk uploading multiple job documents."""

    results: list[BulkUploadFileResult]
    total_submitted: int
    total_succeeded: int
    total_failed: int
    upgrade_recommendation: str | None = None


class ResumeUploadFileResult(BaseModel):
    """Result for a single file in a resume bulk upload batch."""

    filename: str
    success: bool
    status: str | None = None  # "matched" | "new" | "linked_platform" | "failed"
    pipeline_candidate_id: int | None = None
    candidate_profile_id: int | None = None
    matched_email: str | None = None
    parsed_name: str | None = None
    llm_parse_status: str | None = None
    error: str | None = None


class ResumeUploadResponse(BaseModel):
    """Response from bulk uploading resume files for pipeline linking."""

    results: list[ResumeUploadFileResult]
    total_submitted: int
    total_succeeded: int
    total_failed: int
    total_matched: int
    total_new: int
    total_linked_platform: int
    remaining_monthly_quota: int
    upgrade_recommendation: str | None = None


# ============================================================================
# CANDIDATE SEARCH SCHEMAS
# ============================================================================


class CandidateSearchFilters(BaseModel):
    """Filters for searching candidates."""

    skills: list[str] | None = None
    experience_years_min: int | None = Field(None, ge=0)
    experience_years_max: int | None = Field(None, ge=0)
    locations: list[str] | None = None
    remote_only: bool | None = None
    job_titles: list[str] | None = None

    @field_validator("experience_years_max")
    @classmethod
    def validate_experience_range(cls, v: int | None, info) -> int | None:
        if v is not None and info.data.get("experience_years_min") is not None:
            if v < info.data["experience_years_min"]:
                raise ValueError("experience_years_max must be >= experience_years_min")
        return v


class CandidateSearchResult(BaseModel):
    """Single candidate in search results."""

    id: int
    name: str
    headline: str | None = None
    location: str | None = None
    years_experience: int | None = None
    top_skills: list[str] = Field(default_factory=list)
    match_score: float | None = Field(None, ge=0, le=100)
    profile_visibility: str
    preferred_locations: list[str] = Field(default_factory=list)
    remote_ok: bool | None = None
    willing_to_relocate: bool | None = None

    model_config = {"from_attributes": True}


class CandidateSearchResponse(BaseModel):
    """Response for candidate search with pagination."""

    results: list[CandidateSearchResult]
    total: int
    page: int
    page_size: int
    has_more: bool


class TopCandidateResult(BaseModel):
    """Single candidate in top-candidates ranking for an employer job."""

    id: int
    name: str
    headline: str | None = None
    location: str | None = None
    years_experience: int | None = None
    top_skills: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    match_score: float = Field(..., ge=0, le=100)
    profile_visibility: str


class TopCandidatesResponse(BaseModel):
    """Response for top matched candidates for an employer job."""

    job_id: int
    job_title: str
    candidates: list[TopCandidateResult]
    total_evaluated: int


# ============================================================================
# SAVED CANDIDATES SCHEMAS
# ============================================================================


class SaveCandidateRequest(BaseModel):
    """Request to save a candidate."""

    candidate_id: int
    notes: str | None = Field(None, max_length=5000)


class UpdateSavedCandidateNotes(BaseModel):
    """Request to update notes on saved candidate."""

    notes: str | None = Field(None, max_length=5000)


class SavedCandidateResponse(BaseModel):
    """Response for saved candidate."""

    id: int
    candidate_id: int
    notes: str | None = None
    saved_at: datetime | None = None
    candidate: CandidateSearchResult | None = None

    model_config = {"from_attributes": True}


# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================


class EmployerAnalyticsSummary(BaseModel):
    """Summary analytics for employer dashboard."""

    active_jobs: int
    total_job_views: int
    total_applications: int
    candidate_views_this_month: int
    candidate_views_limit: int | None = None
    saved_candidates: int
    subscription_tier: str
    subscription_status: str


class JobAnalytics(BaseModel):
    """Analytics for a specific job."""

    job_id: int
    job_title: str
    status: str
    views: int
    applications: int
    views_last_7_days: int
    applications_last_7_days: int
    posted_at: datetime | None = None
    days_active: int | None = None


# ============================================================================
# SUBSCRIPTION SCHEMAS
# ============================================================================


class SubscriptionTierInfo(BaseModel):
    """Information about a subscription tier."""

    tier: str
    name: str
    price_monthly: int | None = None
    features: dict = Field(default_factory=dict)


class UpgradeSubscriptionRequest(BaseModel):
    """Request to upgrade subscription."""

    tier: str
    payment_method_id: str | None = None

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = ["starter", "pro", "enterprise"]
        if v not in allowed:
            raise ValueError(f"tier must be one of: {', '.join(allowed)}")
        return v


# ============================================================================
# HELPER SCHEMAS
# ============================================================================


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str
    detail: str | None = None
    field: str | None = None


# ============================================================================
# DISTRIBUTION SCHEMAS
# ============================================================================

ALLOWED_BOARD_TYPES = [
    "linkedin",
    "indeed",
    "ziprecruiter",
    "glassdoor",
    "google_jobs",
    "usajobs",
    "custom",
]


class BoardConnectionCreate(BaseModel):
    """Schema for creating a board connection."""

    board_type: str = Field(..., max_length=50)
    board_name: str = Field(..., min_length=1, max_length=255)
    api_key: str | None = Field(None, max_length=1000)
    api_secret: str | None = Field(None, max_length=1000)
    feed_url: str | None = Field(None, max_length=500)
    config: dict | None = None

    @field_validator("board_type")
    @classmethod
    def validate_board_type(cls, v: str) -> str:
        if v not in ALLOWED_BOARD_TYPES:
            raise ValueError(
                f"board_type must be one of: {', '.join(ALLOWED_BOARD_TYPES)}"
            )
        return v


class BoardConnectionUpdate(BaseModel):
    """Schema for updating a board connection."""

    board_name: str | None = Field(None, min_length=1, max_length=255)
    api_key: str | None = Field(None, max_length=1000)
    api_secret: str | None = Field(None, max_length=1000)
    feed_url: str | None = Field(None, max_length=500)
    is_active: bool | None = None
    config: dict | None = None


class BoardConnectionResponse(BaseModel):
    """Schema for board connection response."""

    id: int
    employer_id: int
    board_type: str
    board_name: str
    feed_url: str | None = None
    is_active: bool = True
    config: dict | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DistributionEventResponse(BaseModel):
    """Schema for a distribution event."""

    id: int
    event_type: str
    event_data: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDistributionResponse(BaseModel):
    """Schema for a job's distribution status on one board."""

    id: int
    employer_job_id: int
    board_connection_id: int
    external_job_id: str | None = None
    status: str
    submitted_at: datetime | None = None
    live_at: datetime | None = None
    removed_at: datetime | None = None
    error_message: str | None = None
    impressions: int = 0
    clicks: int = 0
    applications: int = 0
    cost_spent: float = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Inline board info
    board_type: str | None = None
    board_name: str | None = None

    model_config = {"from_attributes": True}


class DistributeJobRequest(BaseModel):
    """Request to distribute a job to boards."""

    board_types: list[str] | None = None


class ConnectionTestResponse(BaseModel):
    """Response from testing a board connection."""

    valid: bool
    message: str


# ============================================================================
# COMPANY-WIDE JOB LISTING SCHEMAS
# ============================================================================


class CompanyJobListItem(BaseModel):
    """Single job row for the employer company-wide jobs browser."""

    model_config = {"from_attributes": True}

    id: int
    job_id_external: str | None = None
    title: str
    status: str
    job_category: str | None = None
    location: str | None = None
    remote_policy: str | None = None
    posted_at: datetime | None = None
    close_date: date | None = None
    view_count: int | None = 0
    matched_candidates_count: int = 0
    application_count: int | None = 0
    poster_email: str | None = None
    created_at: datetime | None = None


class PaginatedCompanyJobsResponse(BaseModel):
    """Paginated wrapper for employer company job listings."""

    items: list[CompanyJobListItem]
    total: int
    page: int
    page_size: int
