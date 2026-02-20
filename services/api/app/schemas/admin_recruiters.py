"""Admin recruiter management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminRecruiterResponse(BaseModel):
    id: int
    user_id: int
    email: str | None
    company_name: str
    company_type: str | None
    company_website: str | None
    subscription_tier: str
    subscription_status: str | None
    billing_interval: str | None
    seats_purchased: int
    seats_used: int
    is_trial_active: bool
    trial_days_remaining: int
    candidate_briefs_used: int
    salary_lookups_used: int
    job_uploads_used: int
    intro_requests_used: int
    resume_imports_used: int
    outreach_enrollments_used: int
    pipeline_count: int
    jobs_count: int
    clients_count: int
    created_at: datetime | None


class AdminRecruiterJobResponse(BaseModel):
    id: int
    title: str
    status: str
    client_company_name: str | None
    location: str | None
    priority: str | None
    positions_to_fill: int
    positions_filled: int
    created_at: datetime | None


class AdminRecruiterClientResponse(BaseModel):
    id: int
    company_name: str
    industry: str | None
    contact_name: str | None
    contact_email: str | None
    status: str
    contract_type: str | None
    fee_percentage: float | None
    created_at: datetime | None


class DeleteRecruitersRequest(BaseModel):
    user_ids: list[int]


class DeleteRecruitersResponse(BaseModel):
    deleted_count: int
    message: str


class RecruiterTierOverrideRequest(BaseModel):
    subscription_tier: str  # trial, solo, team, agency
    subscription_status: str | None = None


class RecruiterTierOverrideResponse(BaseModel):
    id: int
    subscription_tier: str
    subscription_status: str | None
