"""Pydantic schemas for submittal package endpoints."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SubmittalPackageOptions(BaseModel):
    include_briefs: bool = True
    include_resumes: bool = True


class SubmittalPackageCreate(BaseModel):
    candidate_ids: list[int] = Field(default_factory=list)
    pipeline_candidate_ids: list[int] = Field(default_factory=list)
    recipient_name: str = Field(..., min_length=1, max_length=255)
    recipient_email: EmailStr
    client_id: int | None = None
    options: SubmittalPackageOptions = Field(
        default_factory=SubmittalPackageOptions
    )
    cover_email_subject: str | None = None
    cover_email_body: str | None = None


class SubmittalPackageResponse(BaseModel):
    id: int
    recruiter_job_id: int
    status: str
    candidate_ids: list[int] | None = None
    pipeline_candidate_ids: list[int] | None = None
    candidate_count: int = 0
    recipient_name: str
    recipient_email: str
    merged_pdf_url: str | None = None
    cover_email_subject: str | None = None
    cover_email_body: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmittalPackageSendRequest(BaseModel):
    subject: str | None = None
    body: str | None = None
