"""Admin employer management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminEmployerResponse(BaseModel):
    id: int
    user_id: int
    email: str | None
    company_name: str
    company_size: str | None
    industry: str | None
    subscription_tier: str
    subscription_status: str | None
    contact_first_name: str | None
    contact_last_name: str | None
    contact_email: str | None
    active_jobs_count: int
    total_jobs_count: int
    ai_parsing_used: int
    intro_requests_used: int
    created_at: datetime | None


class AdminEmployerJobResponse(BaseModel):
    id: int
    title: str
    status: str
    location: str | None
    remote_policy: str | None
    application_count: int | None
    view_count: int | None
    posted_at: datetime | None
    created_at: datetime | None
    archived: bool
    archived_reason: str | None


class DeleteEmployersRequest(BaseModel):
    user_ids: list[int]


class DeleteEmployersResponse(BaseModel):
    deleted_count: int
    message: str


class EmployerTierOverrideRequest(BaseModel):
    subscription_tier: str  # free, starter, pro
    subscription_status: str | None = None


class EmployerTierOverrideResponse(BaseModel):
    id: int
    subscription_tier: str
    subscription_status: str | None
