from datetime import datetime

from pydantic import BaseModel


class TailorRequestResponse(BaseModel):
    status: str
    job_id: str


class TailorStatusResponse(BaseModel):
    status: str
    resume_url: str | None = None
    cover_letter_url: str | None = None
    error_message: str | None = None


class TailoredDocumentResponse(BaseModel):
    id: int
    job_id: int
    job_title: str
    company: str
    resume_url: str
    cover_letter_url: str
    created_at: datetime | None = None
    has_active_match: bool = False


class DocumentListItem(BaseModel):
    id: int
    job_id: int
    job_title: str | None = None
    company: str | None = None
    profile_version: int
    has_resume: bool
    has_cover_letter: bool
    created_at: datetime | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
