"""Upload batch status polling endpoint."""

import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.upload_batch import UploadBatch, UploadBatchFile
from app.models.user import User
from app.schemas.upload_batch import (
    UploadBatchFileStatus,
    UploadBatchStatusResponse,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/upload-batches", tags=["upload-batches"])


@router.get("/{batch_id}/status", response_model=UploadBatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    include_files: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UploadBatchStatusResponse:
    """Poll upload batch progress. Users can only see their own batches.

    During processing, returns summary counters only (no per-file rows)
    unless ``include_files=true`` is passed. On completion or when
    ``include_files=true``, returns paginated file results.
    """
    batch = session.execute(
        select(UploadBatch).where(UploadBatch.batch_id == batch_id)
    ).scalar_one_or_none()

    if batch is None or batch.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found.",
        )

    file_statuses: list[UploadBatchFileStatus] = []
    resp_page = None
    resp_total_pages = None

    # Only load per-file rows when needed (completed or explicitly requested)
    if batch.status == "completed" or include_files:
        total_count = (
            session.execute(
                select(func.count(UploadBatchFile.id)).where(
                    UploadBatchFile.batch_id == batch_id
                )
            ).scalar()
            or 0
        )

        resp_total_pages = max(1, math.ceil(total_count / page_size))
        resp_page = page

        files = (
            session.execute(
                select(UploadBatchFile)
                .where(UploadBatchFile.batch_id == batch_id)
                .order_by(UploadBatchFile.file_index)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )

        for f in files:
            result = None
            if f.result_json:
                try:
                    result = json.loads(f.result_json)
                except (json.JSONDecodeError, TypeError):
                    pass

            file_statuses.append(
                UploadBatchFileStatus(
                    filename=f.original_filename,
                    status=f.status,
                    error=f.error_message,
                    result=result,
                )
            )

    # Calculate time estimate for in-progress batches
    estimated_finish = None
    if batch.status in ("pending", "processing") and batch.total_files > 0:
        PROCESSING_RATE = 960  # files/hour
        remaining = batch.total_files - batch.files_completed
        if remaining > 0:
            from datetime import UTC, datetime, timedelta

            hours_left = remaining / PROCESSING_RATE
            estimated_finish = (
                datetime.now(UTC) + timedelta(hours=hours_left)
            ).isoformat()

    return UploadBatchStatusResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        total_files=batch.total_files,
        files_completed=batch.files_completed,
        files_succeeded=batch.files_succeeded,
        files_failed=batch.files_failed,
        files=file_statuses,
        page=resp_page,
        total_pages=resp_total_pages,
        estimated_finish_utc=estimated_finish,
    )
