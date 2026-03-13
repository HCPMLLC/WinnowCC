"""Pydantic schemas for custom domain management."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DomainConfigureRequest(BaseModel):
    """Request to configure a custom domain."""

    domain: str = Field(..., min_length=4, max_length=255)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.lower().strip()
        v = re.sub(r"^https?://", "", v)
        v = v.rstrip("/")

        domain_pattern = r"^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$"
        if not re.match(domain_pattern, v):
            raise ValueError("Invalid domain format")

        reserved = ["winnowcc.ai", "winnowcc.com", "winnow.ai", "sieve-scape.com"]
        for r in reserved:
            if v.endswith(r):
                raise ValueError(f"Cannot use {r} domain")

        return v


class DomainConfigureResponse(BaseModel):
    """Response after configuring domain."""

    domain: str
    cname_target: str
    status: str
    instructions: str
    dns_provider_guides: list[dict[str, str]]
    verification_id: UUID


class DomainStatusResponse(BaseModel):
    """Current domain status."""

    domain: Optional[str] = None
    cname_target: Optional[str] = None
    status: str
    dns_verified: bool
    ssl_provisioned: bool
    ssl_expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    error: Optional[str] = None
    is_active: bool


class DomainVerifyResponse(BaseModel):
    """Response from manual verification trigger."""

    status: str
    dns_verified: bool
    message: str


class DnsSetupGuide(BaseModel):
    """DNS setup guide for a specific provider."""

    provider: str
    steps: list[str]
    screenshot_urls: list[str] = []
    estimated_propagation_time: str
    support_url: Optional[str] = None


class DomainSetupGuideRequest(BaseModel):
    """Request to generate a setup guide."""

    dns_provider: Optional[str] = None


class DomainSetupGuideResponse(BaseModel):
    """Generated setup guide."""

    domain: str
    cname_target: str
    dns_provider: str
    guide: DnsSetupGuide
    pdf_download_url: Optional[str] = None


class DomainRemoveRequest(BaseModel):
    """Request to remove custom domain."""

    confirm: bool = Field(..., description="Must be true to confirm removal")
