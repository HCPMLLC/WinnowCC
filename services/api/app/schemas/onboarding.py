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
    plan_tier: str | None = None
    plan_billing_cycle: str | None = None
    alert_frequency: str | None = None
    communication_channels: list[str] = Field(default_factory=list)
    consent_terms: bool = False
    consent_privacy: bool = False
    consent_auto_renewal: bool = False
    consent_marketing: bool = False


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
    plan_tier: str | None = None
    plan_billing_cycle: str | None = None
    alert_frequency: str | None = None
    communication_channels: list[str] = Field(default_factory=list)
    consent_terms: bool = False
    consent_privacy: bool = False
    consent_auto_renewal: bool = False
    consent_marketing: bool = False
