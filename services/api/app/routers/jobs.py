"""Public job endpoints (authenticated)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job_parsed_detail import JobParsedDetail
from app.models.user import User
from app.schemas.jobs import JobParsedDetailResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}/parsed", response_model=JobParsedDetailResponse)
def get_parsed_detail(
    job_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get parsed details for a job posting."""
    parsed = session.execute(
        select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
    ).scalar_one_or_none()

    if not parsed:
        raise HTTPException(
            status_code=404, detail="No parsed details found for this job"
        )

    return parsed
