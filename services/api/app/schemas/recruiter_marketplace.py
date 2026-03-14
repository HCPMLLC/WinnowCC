"""Pydantic schemas for recruiter job marketplace endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.recruiter_job import RecruiterJobCandidateResult


class MarketplaceJobItem(BaseModel):
    """Single job in the marketplace listing."""

    id: int
    title: str
    company: str | None = None
    location: str | None = None
    remote_flag: bool | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    source: str | None = None
    posted_at: datetime | None = None
    description_text: str | None = None
    cached_candidates_count: int = 0


class MarketplaceJobListResponse(BaseModel):
    """Paginated list of marketplace jobs."""

    jobs: list[MarketplaceJobItem]
    total: int
    page: int
    page_size: int


class MarketplaceJobDetail(BaseModel):
    """Full detail for a marketplace job."""

    id: int
    title: str
    company: str | None = None
    location: str | None = None
    remote_flag: bool | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    source: str | None = None
    url: str | None = None
    description_text: str | None = None
    posted_at: datetime | None = None
    cached_candidates_count: int = 0
    cache_fresh: bool = False


class MarketplaceJobCandidatesResponse(BaseModel):
    """Response for matched candidates for a marketplace job."""

    job_id: int
    job_title: str
    candidates: list[RecruiterJobCandidateResult]
    total_cached: int
    needs_refresh: bool = False
