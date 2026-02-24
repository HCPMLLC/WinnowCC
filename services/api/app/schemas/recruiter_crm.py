"""Pydantic schemas for recruiter CRM endpoints."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

ALLOWED_CONTRACT_TYPES = ["contingency", "retained", "rpo", "contract_staffing"]
ALLOWED_CLIENT_STATUSES = ["active", "inactive", "prospect"]
ALLOWED_CONTACT_ROLES = ["Purchaser", "Hiring Manager", "Prime Contractor"]

# Import canonical industry list from employer schemas
from app.schemas.employer import ALLOWED_INDUSTRIES


class ContactEntry(BaseModel):
    """A single contact on a client record."""

    first_name: str | None = Field(None, max_length=128)
    last_name: str | None = Field(None, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    role: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_CONTACT_ROLES:
            raise ValueError(f"role must be one of: {', '.join(ALLOWED_CONTACT_ROLES)}")
        return v


class RecruiterClientCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: str | None = Field(None, max_length=255)
    company_size: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    contacts: list[ContactEntry] | None = Field(None, max_length=10)
    # Legacy single-contact fields (still accepted for backward compat)
    contact_name: str | None = Field(None, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)
    contact_title: str | None = Field(None, max_length=255)
    contract_type: str | None = None
    fee_percentage: float | None = Field(None, ge=0, le=100)
    flat_fee: int | None = Field(None, ge=0)
    contract_start: datetime | None = None
    contract_end: datetime | None = None
    notes: str | None = None
    # Hierarchy & contract vehicle
    parent_client_id: int | None = None
    contract_vehicle: str | None = Field(None, max_length=255)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_INDUSTRIES:
            raise ValueError(
                f"industry must be one of: {', '.join(ALLOWED_INDUSTRIES)}"
            )
        return v

    @field_validator("contacts")
    @classmethod
    def validate_contacts_limit(
        cls,
        v: list[ContactEntry] | None,
    ) -> list[ContactEntry] | None:
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 contacts per client")
        return v


class RecruiterClientUpdate(BaseModel):
    company_name: str | None = Field(None, min_length=1, max_length=255)
    industry: str | None = Field(None, max_length=255)
    company_size: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=500)
    contacts: list[ContactEntry] | None = Field(None, max_length=10)
    # Legacy single-contact fields (still accepted for backward compat)
    contact_name: str | None = Field(None, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)
    contact_title: str | None = Field(None, max_length=255)
    contract_type: str | None = None
    fee_percentage: float | None = Field(None, ge=0, le=100)
    flat_fee: int | None = Field(None, ge=0)
    contract_start: datetime | None = None
    contract_end: datetime | None = None
    notes: str | None = None
    status: str | None = None
    # Hierarchy & contract vehicle
    parent_client_id: int | None = None
    contract_vehicle: str | None = Field(None, max_length=255)

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str | None) -> str | None:
        if v is not None and v not in ALLOWED_INDUSTRIES:
            raise ValueError(
                f"industry must be one of: {', '.join(ALLOWED_INDUSTRIES)}"
            )
        return v

    @field_validator("contacts")
    @classmethod
    def validate_contacts_limit(
        cls,
        v: list[ContactEntry] | None,
    ) -> list[ContactEntry] | None:
        if v is not None and len(v) > 10:
            raise ValueError("Maximum 10 contacts per client")
        return v


class RecruiterClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_profile_id: int
    company_name: str
    industry: str | None = None
    company_size: str | None = None
    website: str | None = None
    contacts: list[ContactEntry] | None = None
    # Legacy fields kept in response for backward compat
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contact_title: str | None = None
    contract_type: str | None = None
    fee_percentage: float | None = None
    flat_fee: int | None = None
    contract_start: datetime | None = None
    contract_end: datetime | None = None
    notes: str | None = None
    status: str = "active"
    # Hierarchy & contract vehicle
    parent_client_id: int | None = None
    contract_vehicle: str | None = None
    parent_company_name: str | None = None
    job_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Pipeline Candidates
# ---------------------------------------------------------------------------

ALLOWED_STAGES = [
    "sourced",
    "contacted",
    "screening",
    "interviewing",
    "offered",
    "placed",
    "rejected",
]


class PipelineCandidateCreate(BaseModel):
    recruiter_job_id: int | None = None
    candidate_profile_id: int | None = None
    external_name: str | None = Field(None, max_length=255)
    external_email: EmailStr | None = None
    external_phone: str | None = Field(None, max_length=50)
    external_linkedin: str | None = Field(None, max_length=500)
    external_resume_url: str | None = Field(None, max_length=500)
    source: str = Field(..., max_length=100)
    stage: str = "sourced"
    rating: int | None = Field(None, ge=1, le=5)
    tags: list[str] | None = None
    notes: str | None = None
    match_score: float | None = Field(None, ge=0, le=100)

    @model_validator(mode="after")
    def require_candidate_identity(self) -> "PipelineCandidateCreate":
        if not self.candidate_profile_id and not self.external_name:
            raise ValueError("Either candidate_profile_id or external_name is required")
        return self


class PipelineCandidateUpdate(BaseModel):
    recruiter_job_id: int | None = None
    stage: str | None = None
    rating: int | None = Field(None, ge=1, le=5)
    tags: list[str] | None = None
    notes: str | None = None
    outreach_count: int | None = Field(None, ge=0)
    last_outreach_at: datetime | None = None
    # Contact fields (editable after creation)
    external_name: str | None = Field(None, max_length=255)
    external_email: EmailStr | None = None
    external_phone: str | None = Field(None, max_length=50)
    external_linkedin: str | None = Field(None, max_length=500)
    external_resume_url: str | None = Field(None, max_length=500)


class PipelineCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_profile_id: int
    recruiter_job_id: int | None = None
    candidate_profile_id: int | None = None
    external_name: str | None = None
    external_email: str | None = None
    external_phone: str | None = None
    external_linkedin: str | None = None
    external_resume_url: str | None = None
    source: str | None = None
    stage: str = "sourced"
    rating: int | None = None
    tags: list[str] | None = None
    notes: str | None = None
    match_score: float | None = None
    outreach_count: int = 0
    last_outreach_at: datetime | None = None
    candidate_name: str | None = None
    # Profile summary fields (resolved from candidate_profile if linked)
    headline: str | None = None
    location: str | None = None
    current_company: str | None = None
    skills: list[str] | None = None
    linkedin_url: str | None = None
    is_platform_candidate: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


class RecruiterActivityCreate(BaseModel):
    activity_type: str = Field(..., min_length=1, max_length=50)
    pipeline_candidate_id: int | None = None
    recruiter_job_id: int | None = None
    client_id: int | None = None
    subject: str | None = Field(None, max_length=500)
    body: str | None = None
    metadata: dict | None = None


class RecruiterActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    recruiter_profile_id: int
    user_id: int | None = None
    pipeline_candidate_id: int | None = None
    recruiter_job_id: int | None = None
    client_id: int | None = None
    activity_type: str
    subject: str | None = None
    body: str | None = None
    metadata: dict | None = Field(None, validation_alias="activity_metadata")
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


class RecruiterTeamInvite(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class RecruiterTeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    role: str | None = "member"
    invited_at: datetime | None = None
    accepted_at: datetime | None = None
    email: str | None = None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class PipelineStageSummary(BaseModel):
    stage: str
    count: int


class RecruiterDashboardResponse(BaseModel):
    total_active_jobs: int = 0
    total_pipeline_candidates: int = 0
    total_clients: int = 0
    total_placements: int = 0
    pipeline_by_stage: list[PipelineStageSummary] = Field(default_factory=list)
    recent_activities: list[RecruiterActivityResponse] = Field(default_factory=list)
    subscription_tier: str = "trial"
