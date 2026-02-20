"""Pydantic schemas for outreach sequences and enrollments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class OutreachStep(BaseModel):
    step_number: int
    delay_days: int
    subject: str
    body: str

    @field_validator("step_number")
    @classmethod
    def step_number_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("step_number must be >= 1")
        return v

    @field_validator("delay_days")
    @classmethod
    def delay_days_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("delay_days must be >= 0")
        return v

    @field_validator("subject", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class OutreachSequenceCreate(BaseModel):
    name: str
    description: str | None = None
    recruiter_job_id: int | None = None
    steps: list[OutreachStep]

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Sequence name is required")
        return v.strip()

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: list[OutreachStep]) -> list[OutreachStep]:
        if not v:
            raise ValueError("At least one step is required")
        if len(v) > 10:
            raise ValueError("Maximum 10 steps per sequence")
        numbers = [s.step_number for s in v]
        expected = list(range(1, len(v) + 1))
        if numbers != expected:
            raise ValueError("Steps must be numbered sequentially starting from 1")
        return v


class OutreachSequenceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    recruiter_job_id: int | None = None
    is_active: bool | None = None
    steps: list[OutreachStep] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Sequence name cannot be empty")
        return v.strip() if v else v

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: list[OutreachStep] | None) -> list[OutreachStep] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("At least one step is required")
        if len(v) > 10:
            raise ValueError("Maximum 10 steps per sequence")
        numbers = [s.step_number for s in v]
        expected = list(range(1, len(v) + 1))
        if numbers != expected:
            raise ValueError("Steps must be numbered sequentially starting from 1")
        return v


class OutreachSequenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recruiter_profile_id: int
    recruiter_job_id: int | None = None
    name: str
    description: str | None = None
    is_active: bool = True
    steps: list[dict] = []
    enrolled_count: int = 0
    sent_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EnrollCandidatesRequest(BaseModel):
    pipeline_candidate_ids: list[int]

    @field_validator("pipeline_candidate_ids")
    @classmethod
    def validate_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("At least one candidate ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 candidates per enrollment request")
        return v


class UnenrollRequest(BaseModel):
    enrollment_ids: list[int]

    @field_validator("enrollment_ids")
    @classmethod
    def validate_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("At least one enrollment ID is required")
        if len(v) > 50:
            raise ValueError("Maximum 50 enrollments per unenroll request")
        return v


class OutreachEnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence_id: int
    pipeline_candidate_id: int
    recruiter_profile_id: int
    current_step: int = 0
    status: str = "active"
    next_send_at: datetime | None = None
    last_sent_at: datetime | None = None
    enrolled_at: datetime | None = None
    completed_at: datetime | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None
