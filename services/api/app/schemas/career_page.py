"""Pydantic schemas for career pages."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BrandingColors(BaseModel):
    primary: str = Field(default="#1B3025", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary: str = Field(default="#E8C84A", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str = Field(default="#CEE3D8", pattern=r"^#[0-9A-Fa-f]{6}$")
    background: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    text: str = Field(default="#1B3025", pattern=r"^#[0-9A-Fa-f]{6}$")


class BrandingFonts(BaseModel):
    heading: str = Field(default="Inter")
    body: str = Field(default="Inter")


class BrandingConfig(BaseModel):
    colors: BrandingColors = Field(default_factory=BrandingColors)
    logo_url: str | None = None
    logo_alt: str | None = None
    favicon_url: str | None = None
    fonts: BrandingFonts = Field(default_factory=BrandingFonts)


class LayoutConfig(BaseModel):
    hero_style: str = Field(
        default="gradient", pattern=r"^(image|video|gradient|minimal)$"
    )
    gradient_angle: int = Field(default=135, ge=0, le=360)
    hero_image_url: str | None = None
    hero_overlay_opacity: int = Field(default=40, ge=0, le=100)
    job_display: str = Field(default="grid", pattern=r"^(grid|list|compact)$")
    show_ips_preview: bool = Field(default=True)
    show_salary_ranges: bool = Field(default=True)
    show_location_filter: bool = Field(default=True)
    show_department_filter: bool = Field(default=True)


class SectionConfig(BaseModel):
    type: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class SieveSectionConfig(BaseModel):
    enabled: bool = Field(default=True)
    position: str = Field(default="bottom-right")
    name: str = Field(default="Sieve")
    welcome_message: str = Field(
        default="Hi! I'm here to help you find your perfect role."
    )
    tone: str = Field(
        default="professional",
        pattern=r"^(professional|casual|enthusiastic)$",
    )
    avatar_url: str | None = None


class CareerPageConfig(BaseModel):
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    layout: LayoutConfig = Field(default_factory=LayoutConfig)
    sections: list[SectionConfig] = Field(
        default_factory=lambda: [
            SectionConfig(
                type="hero", enabled=True, config={"headline": "Join Our Team"}
            ),
            SectionConfig(
                type="jobs", enabled=True, config={"title": "Open Positions"}
            ),
        ]
    )
    sieve: SieveSectionConfig = Field(default_factory=SieveSectionConfig)


class CareerPageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(
        ..., min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$"
    )
    page_title: str | None = Field(None, max_length=200)
    meta_description: str | None = Field(None, max_length=500)
    config: CareerPageConfig = Field(default_factory=CareerPageConfig)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        reserved = ["api", "admin", "app", "www", "careers", "jobs", "embed"]
        if v.lower() in reserved:
            raise ValueError(f"Slug '{v}' is reserved")
        return v.lower()


class CareerPageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(
        None, min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$"
    )
    page_title: str | None = Field(None, max_length=200)
    meta_description: str | None = Field(None, max_length=500)
    config: CareerPageConfig | None = None


class CareerPageResponse(BaseModel):
    id: UUID
    tenant_id: int
    tenant_type: str
    slug: str
    name: str
    page_title: str | None
    meta_description: str | None
    config: dict[str, Any]
    published: bool
    published_at: datetime | None
    custom_domain: str | None
    custom_domain_verified: bool
    public_url: str
    embed_url: str
    view_count: int
    application_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CareerPageListResponse(BaseModel):
    pages: list[CareerPageResponse]
    total: int


class CareerPagePublishRequest(BaseModel):
    publish: bool = True


# Public API schemas
class PublicCareerPageResponse(BaseModel):
    slug: str
    page_title: str | None
    meta_description: str | None
    config: dict[str, Any]
    published: bool

    class Config:
        from_attributes = True


class PublicJobSummary(BaseModel):
    id: int
    title: str
    location: str | None
    location_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    posted_at: datetime
    ips_score: int | None = None
    ips_label: str | None = None


class PublicJobListResponse(BaseModel):
    jobs: list[PublicJobSummary]
    total: int
    page: int
    page_size: int
    filters: dict[str, list[str]]
