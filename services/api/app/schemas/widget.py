"""Pydantic schemas for widget API keys."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WidgetApiKeyCreate(BaseModel):
    name: str | None = Field(None, max_length=100)
    allowed_domains: list[str] | None = None
    environment: str = Field(default="live", pattern=r"^(live|test)$")


class WidgetApiKeyResponse(BaseModel):
    id: UUID
    name: str | None
    key_prefix: str
    key_suffix: str
    allowed_domains: list[str] | None
    rate_limit_per_hour: int
    active: bool
    last_used_at: datetime | None
    request_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class WidgetApiKeyCreatedResponse(WidgetApiKeyResponse):
    """Response when creating - includes full key ONCE."""

    api_key: str = Field(..., description="Store securely - won't be shown again")


class WidgetApiKeyListResponse(BaseModel):
    keys: list[WidgetApiKeyResponse]
    total: int
