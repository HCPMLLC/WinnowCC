"""Pydantic schemas for introduction requests."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IntroductionRequestCreate(BaseModel):
    candidate_profile_id: int
    recruiter_job_id: int | None = None
    message: str = Field(..., min_length=20, max_length=1000)


class IntroductionResponseAction(BaseModel):
    action: str = Field(..., pattern=r"^(accept|decline)$")
    response_message: str | None = Field(None, max_length=500)


class IntroductionPreferencesUpdate(BaseModel):
    open_to_introductions: bool


class IntroductionRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_profile_id: int
    candidate_profile_id: int
    recruiter_job_id: int | None = None
    message: str
    status: str = "pending"
    candidate_response_message: str | None = None
    created_at: datetime | None = None
    responded_at: datetime | None = None
    expires_at: datetime | None = None

    # Enriched fields (populated by service, not from ORM directly)
    recruiter_company: str | None = None
    job_title: str | None = None
    job_client: str | None = None
    candidate_name: str | None = None
    candidate_headline: str | None = None
    candidate_location: str | None = None
    candidate_email: str | None = None  # Only populated when status == accepted
