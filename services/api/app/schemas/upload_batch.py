"""Pydantic schemas for upload batch status polling."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class UploadBatchFileStatus(BaseModel):
    filename: str
    status: str  # pending | processing | succeeded | failed | skipped
    error: str | None = None
    result: dict[str, Any] | None = None


class UploadBatchStatusResponse(BaseModel):
    batch_id: str
    status: str  # pending | processing | completed
    total_files: int
    files_completed: int
    files_succeeded: int
    files_failed: int
    files: list[UploadBatchFileStatus]


class UploadBatchCreatedResponse(BaseModel):
    batch_id: str
    status_url: str
    total_files: int
