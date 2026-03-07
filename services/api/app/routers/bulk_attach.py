"""Bulk resume attach router for recruiters."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.recruiter import RecruiterProfile
from app.services.auth import get_recruiter_profile

router = APIRouter(prefix="/api/recruiter/bulk-attach", tags=["recruiter-bulk-attach"])

logger = logging.getLogger(__name__)

MAX_ZIP_SIZE = 200 * 1024 * 1024  # 200 MB


class SelectedMatch(BaseModel):
    filename: str
    candidate_id: int
    matched_by: str


class ProcessRequest(BaseModel):
    batch_id: str
    zip_staged_path: str
    selected_matches: list[SelectedMatch]


@router.post("/preview")
async def preview_bulk_attach(
    file: UploadFile = File(...),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
):
    """Upload a ZIP of resumes and preview matches to pipeline candidates."""
    from app.services.billing import get_recruiter_limit

    # Check billing limit
    tier = profile.subscription_tier or "trial"
    limit = get_recruiter_limit(tier, "resume_imports")
    if limit <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resume imports not available on your plan.",
        )

    # Read and validate ZIP
    contents = await file.read()
    if len(contents) > MAX_ZIP_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"ZIP file too large. Max size is "
                f"{MAX_ZIP_SIZE // (1024 * 1024)} MB."
            ),
        )

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a ZIP file.",
        )

    from app.services.bulk_resume_attach import preview_bulk_attach as do_preview

    try:
        result = do_preview(
            recruiter_profile_id=profile.id,
            user_id=profile.user_id,
            zip_bytes=contents,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    return result


@router.post("/process")
async def process_bulk_attach(
    request: ProcessRequest,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    session: Session = Depends(get_session),
):
    """Confirm and process selected matches from the preview."""
    from app.services.billing import check_recruiter_monthly_limit

    # Check billing limit
    try:
        check_recruiter_monthly_limit(
            profile, "resume_imports_used", "resume_imports", session
        )
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resume import limit reached for this period.",
        ) from None

    from app.services.bulk_resume_attach import process_bulk_attach as do_process

    try:
        result = do_process(
            recruiter_profile_id=profile.id,
            user_id=profile.user_id,
            batch_id=request.batch_id,
            zip_staged_path=request.zip_staged_path,
            selected_matches=[m.model_dump() for m in request.selected_matches],
            session=session,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None

    return result
