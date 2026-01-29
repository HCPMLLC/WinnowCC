from datetime import datetime

from pydantic import BaseModel

from app.schemas.jobs import JobResponse


class MatchResponse(BaseModel):
    id: int
    job: JobResponse
    match_score: int
    interview_readiness_score: int
    offer_probability: int
    reasons: dict
    created_at: datetime


class MatchesRefreshResponse(BaseModel):
    status: str
    job_id: str
