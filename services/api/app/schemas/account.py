"""Pydantic schemas for account management endpoints."""

from pydantic import BaseModel, Field


class DeleteAccountRequest(BaseModel):
    confirm: str = Field(..., description='Must be "DELETE MY ACCOUNT"')


class ExportPreviewResponse(BaseModel):
    profile_versions: int
    resume_documents: int
    matches: int
    tailored_resumes: int
    has_trust_record: bool


class DeleteAccountResponse(BaseModel):
    status: str
    message: str
    summary: dict
