from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job_run import JobRun
from app.models.resume_document import ResumeDocument
from app.models.user import User
from app.schemas.profile import ParseJobResponse
from app.schemas.resume import (
    ParseJobStatusResponse,
    ResumeDocumentResponse,
    ResumeUploadResponse,
)
from app.services.auth import get_current_user, require_onboarded_user
from app.services.resume_parse_job import parse_resume_job
from app.services.storage import upload_file
from app.services.trust_scoring import evaluate_trust_for_resume

router = APIRouter(
    prefix="/api/resume",
    tags=["resume"],
    dependencies=[Depends(require_onboarded_user)],
)

ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _validate_extension(filename: str) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use PDF or DOCX.",
        )
    return extension


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ResumeUploadResponse:
    original_filename = Path(file.filename or "").name
    ext = _validate_extension(original_filename)

    stored_filename = f"{uuid4().hex}_{original_filename}"

    # Write to a temp file first for SHA256 + size validation
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
    size = 0
    digest = hashlib.sha256()
    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File exceeds 10MB limit.",
                )
            tmp.write(chunk)
            digest.update(chunk)
        tmp.close()
    except HTTPException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    sha256 = digest.hexdigest()

    # Upload to GCS or copy to local data dir
    try:
        stored_path = upload_file(tmp.name, "resumes/", stored_filename)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    record = ResumeDocument(
        user_id=user.id,
        filename=original_filename,
        path=stored_path,
        sha256=sha256,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    try:
        evaluate_trust_for_resume(
            session, record, profile_json=None, action="initial_evaluation"
        )
    except Exception:
        session.rollback()

    return ResumeUploadResponse(
        resume_document_id=record.id,
        filename=record.filename,
    )


@router.get("/", response_model=list[ResumeDocumentResponse])
def list_resumes(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ResumeDocumentResponse]:
    stmt = (
        select(ResumeDocument)
        .where(ResumeDocument.user_id == user.id, ResumeDocument.active())
        .order_by(ResumeDocument.created_at.desc())
    )
    records = session.execute(stmt).scalars().all()
    return [ResumeDocumentResponse.model_validate(r) for r in records]


@router.get("/{resume_id}", response_model=ResumeDocumentResponse)
def get_resume_details(
    resume_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ResumeDocumentResponse:
    record = session.get(ResumeDocument, resume_id)
    if record is None or record.user_id != user.id or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return ResumeDocumentResponse.model_validate(record)


@router.post("/{resume_id}/parse", response_model=ParseJobResponse)
def parse_resume(
    resume_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ParseJobResponse:
    record = session.get(ResumeDocument, resume_id)
    if record is None or record.user_id != user.id or record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    job_run = JobRun(
        job_type="resume_parse",
        status="queued",
        resume_document_id=resume_id,
    )
    session.add(job_run)
    session.commit()
    session.refresh(job_run)

    # Run parse synchronously — parse_profile_from_text is regex-based and
    # fast, and on Cloud Run the worker can't access the API's local files.
    parse_resume_job(resume_id, job_run.id)
    session.refresh(job_run)

    return ParseJobResponse(job_id="sync", job_run_id=job_run.id, status=job_run.status)


@router.get("/parse/{job_run_id}", response_model=ParseJobStatusResponse)
def get_parse_status(
    job_run_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ParseJobStatusResponse:
    job_run = session.get(JobRun, job_run_id)
    if job_run is None:
        raise HTTPException(status_code=404, detail="Parse job not found.")
    if job_run.resume_document_id is None:
        raise HTTPException(status_code=404, detail="Parse job not found.")

    resume = session.get(ResumeDocument, job_run.resume_document_id)
    if resume is None or resume.user_id != user.id or resume.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Parse job not found.")

    return ParseJobStatusResponse(
        job_run_id=job_run.id,
        status=job_run.status,
        error_message=job_run.error_message,
    )
