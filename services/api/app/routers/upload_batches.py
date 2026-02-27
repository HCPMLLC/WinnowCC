"""Upload batch status polling endpoint."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UploadBatchStatusResponse:
    """Poll upload batch progress. Users can only see their own batches."""
    batch = session.execute(
        select(UploadBatch).where(UploadBatch.batch_id == batch_id)
    ).scalar_one_or_none()

    if batch is None or batch.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found.",
        )

    files = (
        session.execute(
            select(UploadBatchFile)
            .where(UploadBatchFile.batch_id == batch_id)
            .order_by(UploadBatchFile.file_index)
        )
        .scalars()
        .all()
    )

    file_statuses = []
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

    return UploadBatchStatusResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        total_files=batch.total_files,
        files_completed=batch.files_completed,
        files_succeeded=batch.files_succeeded,
        files_failed=batch.files_failed,
        files=file_statuses,
    )
