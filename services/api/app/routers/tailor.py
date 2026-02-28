from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from rq.job import Job
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job as JobModel
from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.schemas.tailor import (
    DocumentListItem,
    DocumentListResponse,
    TailorRequestResponse,
    TailorStatusResponse,
)
from app.services.auth import get_current_user, require_onboarded_user
from app.services.job_pipeline import tailor_job
from app.services.queue import get_queue, get_redis_connection
from app.services.storage import file_response_path, is_gcs_path
from app.services.trust_gate import require_allowed_trust

router = APIRouter(prefix="/api/tailor", tags=["tailor"])


def _latest_profile_version(session: Session, user_id: int) -> int:
    stmt = (
        select(CandidateProfile.version)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    version = session.execute(stmt).scalar()
    return int(version or 0)


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    dependencies=[Depends(require_onboarded_user)],
)
def list_documents(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DocumentListResponse:
    stmt = (
        select(TailoredResume, JobModel.title, JobModel.company)
        .join(JobModel, TailoredResume.job_id == JobModel.id, isouter=True)
        .where(TailoredResume.user_id == user.id)
        .order_by(TailoredResume.created_at.desc())
    )
    rows = session.execute(stmt).all()
    items: list[DocumentListItem] = []
    for tailored, job_title, company in rows:
        has_resume = bool(tailored.docx_url) and (
            is_gcs_path(tailored.docx_url) or Path(tailored.docx_url).exists()
        )
        has_cover = bool(tailored.cover_letter_url) and (
            is_gcs_path(tailored.cover_letter_url)
            or Path(tailored.cover_letter_url).exists()
        )
        # Use snapshot fields as fallback when job has been purged
        display_title = job_title or tailored.job_title_snapshot
        display_company = company or tailored.job_company_snapshot
        items.append(
            DocumentListItem(
                id=tailored.id,
                job_id=tailored.job_id,
                job_title=display_title,
                company=display_company,
                profile_version=tailored.profile_version,
                has_resume=has_resume,
                has_cover_letter=has_cover,
                created_at=tailored.created_at,
            )
        )
    return DocumentListResponse(documents=items)


@router.post(
    "/{job_id}",
    response_model=TailorRequestResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def request_tailor(
    job_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TailorRequestResponse:
    profile_version = _latest_profile_version(session, user.id)
    queue = get_queue("critical")
    job = queue.enqueue(tailor_job, user.id, job_id, profile_version)
    return TailorRequestResponse(status="queued", job_id=job.id)


@router.get(
    "/status/{rq_job_id}",
    response_model=TailorStatusResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def get_tailor_status(
    rq_job_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TailorStatusResponse:
    job = Job.fetch(rq_job_id, connection=get_redis_connection())
    status = job.get_status()
    if status == "failed":
        return TailorStatusResponse(status="failed", error_message=str(job.exc_info))
    if status != "finished":
        return TailorStatusResponse(status=status)

    job_args = job.args or ()
    job_id = job_args[1] if len(job_args) > 1 else None
    if job_id is None:
        return TailorStatusResponse(status="finished")

    stmt = (
        select(TailoredResume)
        .where(TailoredResume.user_id == user.id, TailoredResume.job_id == job_id)
        .order_by(TailoredResume.created_at.desc())
        .limit(1)
    )
    tailored = session.execute(stmt).scalars().first()
    if tailored is None:
        return TailorStatusResponse(status="finished")

    return TailorStatusResponse(
        status="finished",
        resume_url=f"/api/tailor/files/{tailored.id}/resume",
        cover_letter_url=f"/api/tailor/files/{tailored.id}/cover-letter",
    )


def _cleanup_temp(path: Path, stored_path: str) -> None:
    """Remove temp file only if it was downloaded from GCS."""
    if is_gcs_path(stored_path):
        path.unlink(missing_ok=True)


@router.get(
    "/files/{tailored_id}/resume",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def download_resume(
    tailored_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FileResponse:
    tailored = session.get(TailoredResume, tailored_id)
    if tailored is None or tailored.user_id != user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    if not tailored.docx_url:
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        path = file_response_path(tailored.docx_url, suffix=".docx")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found.") from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    background_tasks.add_task(_cleanup_temp, path, tailored.docx_url)
    return FileResponse(path, filename=path.name)


@router.get(
    "/files/{tailored_id}/cover-letter",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def download_cover_letter(
    tailored_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FileResponse:
    tailored = session.get(TailoredResume, tailored_id)
    if tailored is None or tailored.user_id != user.id:
        raise HTTPException(status_code=404, detail="File not found.")
    if not tailored.cover_letter_url:
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        path = file_response_path(tailored.cover_letter_url, suffix=".docx")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found.") from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    background_tasks.add_task(_cleanup_temp, path, tailored.cover_letter_url)
    return FileResponse(path, filename=path.name)
