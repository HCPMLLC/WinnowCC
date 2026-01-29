from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeUploadResponse(BaseModel):
    resume_document_id: int
    filename: str


class ResumeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    filename: str
    path: str
    created_at: datetime


class ParseJobStatusResponse(BaseModel):
    job_run_id: int
    status: str
    error_message: str | None = None
