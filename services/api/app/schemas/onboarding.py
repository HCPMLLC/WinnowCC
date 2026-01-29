from pydantic import BaseModel, ConfigDict, Field


class CandidateUpsertRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    location_city: str | None = None
    state: str | None = None
    country: str | None = None
    work_authorization: str | None = None
    years_experience: int | None = None
    desired_job_types: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
    desired_salary_min: int | None = None
    desired_salary_max: int | None = None
    remote_preference: str | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    location_city: str | None = None
    state: str | None = None
    country: str | None = None
    work_authorization: str | None = None
    years_experience: int | None = None
    desired_job_types: list[str] = Field(default_factory=list)
    desired_locations: list[str] = Field(default_factory=list)
    desired_salary_min: int | None = None
    desired_salary_max: int | None = None
    remote_preference: str | None = None
