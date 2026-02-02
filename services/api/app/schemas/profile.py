from pydantic import BaseModel, Field


class CandidateProfilePreferences(BaseModel):
    target_titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    remote_ok: bool | None = None
    job_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None


class BasicsPayload(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None  # Computed from first_name + last_name, admin-editable only
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    total_years_experience: int | None = None
    work_authorization: str | None = None


class ExperienceItemPayload(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)
    duties: list[str] = Field(default_factory=list)
    skills_used: list[str] = Field(default_factory=list)
    technologies_used: list[str] = Field(default_factory=list)
    quantified_accomplishments: list[str] = Field(default_factory=list)


class EducationItemPayload(BaseModel):
    school: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProfileDeficiency(BaseModel):
    field: str
    message: str
    weight: int


class ProfileCompletenessResponse(BaseModel):
    score: int  # 0-100 percentage
    deficiencies: list[ProfileDeficiency]
    recommendations: list[str]


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
