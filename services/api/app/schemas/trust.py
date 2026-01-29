from datetime import datetime

from pydantic import BaseModel


class TrustStatusResponse(BaseModel):
    trust_status: str
    score: int
    user_message: str


class TrustReviewRequestResponse(BaseModel):
    status: str


class AdminTrustRecordResponse(BaseModel):
    id: int
    resume_document_id: int
    score: int
    status: str
    reasons: list[dict]
    user_message: str
    internal_notes: str | None
    updated_at: datetime


class AdminTrustUpdateRequest(BaseModel):
    status: str
    internal_notes: str | None = None


class AdminTrustUpdateResponse(BaseModel):
    id: int
    status: str
    internal_notes: str | None
