from pydantic import BaseModel, Field


class CandidateProfilePreferences(BaseModel):
    target_titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_ok: bool | None = None
    job_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None


class CandidateProfilePayload(BaseModel):
    basics: dict = Field(default_factory=dict)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    preferences: CandidateProfilePreferences = Field(
        default_factory=CandidateProfilePreferences
    )


class CandidateProfileResponse(BaseModel):
    version: int
    profile_json: dict


class CandidateProfileUpdateRequest(BaseModel):
    profile_json: dict


class ParseJobResponse(BaseModel):
    job_id: str
    job_run_id: int
    status: str
