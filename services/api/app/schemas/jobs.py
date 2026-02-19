from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    url: str
    title: str
    company: str
    location: str
    remote_flag: bool
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    description_text: str
    posted_at: datetime | None
    ingested_at: datetime
    application_deadline: datetime | None
    hiring_manager_name: str | None
    hiring_manager_email: str | None
    hiring_manager_phone: str | None


class AdminJobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    url: str
    title: str
    company: str
    location: str
    remote_flag: bool
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    ingested_at: datetime
    application_deadline: datetime | None = None
    hiring_manager_name: str | None = None


class JobQualityListItem(BaseModel):
    job_id: int
    title: str
    company: str
    fraud_score: float | None = None
    posting_quality_score: float | None = None
    is_likely_fraudulent: bool = False
    red_flags: list[str] | None = None
    is_stale: bool = False
    parsed_at: datetime | None = None


class PaginatedJobsResponse(BaseModel):
    items: list[AdminJobListItem]
    total: int
    page: int
    page_size: int


class JobParsedDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    normalized_title: str | None = None
    seniority_level: str | None = None
    employment_type: str | None = None
    estimated_duration_months: int | None = None
    parsed_city: str | None = None
    parsed_state: str | None = None
    parsed_country: str | None = None
    work_mode: str | None = None
    travel_percent: int | None = None
    relocation_offered: bool | None = None
    parsed_salary_min: int | None = None
    parsed_salary_max: int | None = None
    parsed_salary_currency: str | None = None
    parsed_salary_type: str | None = None
    salary_confidence: str | None = None
    benefits_mentioned: list | None = None
    required_skills: list | None = None
    preferred_skills: list | None = None
    required_certifications: list | None = None
    required_education: list | None = None
    years_experience_min: int | None = None
    years_experience_max: int | None = None
    tools_and_technologies: list | None = None
    raw_responsibilities: list | None = None
    raw_qualifications: list | None = None
    inferred_industry: str | None = None
    company_size_signal: str | None = None
    department: str | None = None
    reports_to: str | None = None
    team_size: str | None = None
    posting_quality_score: int | None = None
    fraud_score: int | None = None
    is_likely_fraudulent: bool | None = False
    red_flags: list | None = None
    is_duplicate_of_job_id: int | None = None
    is_stale: bool | None = False
    parse_version: int = 1
    parsed_at: datetime | None = None
