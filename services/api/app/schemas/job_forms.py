"""Schemas for employer job forms, filled forms, and application packets."""

from datetime import datetime

from pydantic import BaseModel


class JobFormResponse(BaseModel):
    id: int
    job_id: int
    original_filename: str
    file_type: str
    form_type: str
    is_parsed: bool
    total_fields: int | None = None
    auto_fillable: int | None = None
    needs_manual: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FilledFormResponse(BaseModel):
    id: int
    job_form_id: int
    job_id: int
    status: str
    filled_count: int | None = None
    unfilled_fields: list[dict] | None = None
    gaps_detected: list[dict] | None = None
    output_storage_url: str | None = None
    generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MergedPacketResponse(BaseModel):
    id: int
    job_id: int
    match_id: int | None = None
    status: str
    document_order: list[dict] | None = None
    merged_pdf_url: str | None = None
    naming_convention: str | None = None
    generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplyReadinessResponse(BaseModel):
    ready: bool
    has_references: bool
    references_count: int
    forms_count: int
    gaps: list[dict]
    warnings: list[str]
    skill_coverage: float | None = None


class GeneratePacketRequest(BaseModel):
    naming_convention: str | None = None
    include_cover_letter: bool = True
    include_references: bool = True
