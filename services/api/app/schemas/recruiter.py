"""Schemas for recruiter profile endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class RecruiterProfileCreate(BaseModel):
    company_name: str
    company_type: str | None = None
    company_website: str | None = None
    specializations: list[str] | None = None

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Company name is required")
        return v.strip()


class RecruiterProfileUpdate(BaseModel):
    company_name: str | None = None
    company_type: str | None = None
    company_website: str | None = None
    specializations: list[str] | None = None
    auto_populate_pipeline: bool | None = None

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Company name cannot be empty")
        return v.strip() if v else v


class SourcedCandidateUpdate(BaseModel):
    """Editable fields for a recruiter-sourced candidate profile."""

    name: str | None = None
    headline: str | None = None
    location: str | None = None
    current_company: str | None = None
    about: str | None = None
    experience: list[dict] | None = None
    education: list[dict] | None = None
    skills: list[str | dict] | None = None
    certifications: list[dict] | None = None
    volunteer: list[dict] | None = None
    publications: list[dict] | None = None
    projects: list[dict] | None = None
    contact_info: dict | None = None
    open_to_work: bool | None = None
    recommendations_count: int | None = None
    notes: str | None = None


class RecruiterProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_name: str
    company_type: str | None = None
    company_website: str | None = None
    specializations: list | None = None
    subscription_tier: str = "trial"
    subscription_status: str | None = None
    billing_interval: str | None = None
    seats_purchased: int = 1
    seats_used: int = 1
    candidate_briefs_used: int = 0
    salary_lookups_used: int = 0
    resume_imports_used: int = 0
    auto_populate_pipeline: bool = False
    is_trial_active: bool = False
    trial_days_remaining: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
