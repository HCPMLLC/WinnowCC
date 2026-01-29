from pydantic import BaseModel


class TailorRequestResponse(BaseModel):
    status: str
    job_id: str


class TailorStatusResponse(BaseModel):
    status: str
    resume_url: str | None = None
    cover_letter_url: str | None = None
    error_message: str | None = None
