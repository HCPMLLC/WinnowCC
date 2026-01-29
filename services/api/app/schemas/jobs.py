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
