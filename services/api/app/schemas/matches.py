from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.jobs import JobResponse

# Valid application status values
ApplicationStatus = Literal["saved", "applied", "interviewing", "rejected", "offer"]


class MatchResponse(BaseModel):
    id: int
    job: JobResponse
    match_score: int
    interview_readiness_score: int
    offer_probability: int
    reasons: dict
    created_at: datetime
    # Interview Probability fields
    resume_score: int | None = None
    cover_letter_score: int | None = None
    application_logistics_score: int | None = None
    referred: bool = False
    interview_probability: int | None = None
    # Semantic search
    semantic_similarity: float | None = None
    # Application tracking
    application_status: str | None = None
    # IPS coaching (Pro only)
    coaching_tips: dict | None = None
    # Gap closure recommendations status
    gap_recs_status: str | None = None


class MatchesRefreshResponse(BaseModel):
    status: str
    job_id: str


class ReferralUpdateRequest(BaseModel):
    referred: bool


class ReferralUpdateResponse(BaseModel):
    id: int
    referred: bool
    interview_probability: int | None


class ApplicationStatusUpdateRequest(BaseModel):
    status: ApplicationStatus


class ApplicationStatusUpdateResponse(BaseModel):
    id: int
    application_status: str | None
    interview_prep_status: str | None = None
