"""Job Forms router — upload, parse, manage employer forms per job."""

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job import Job
from app.models.job_form import JobForm
from app.models.user import User
from app.schemas.job_forms import JobFormResponse
from app.services.auth import get_current_user, require_onboarded_user
from app.services.storage import delete_file, download_to_tempfile, is_gcs_path, upload_file

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/jobs/{job_id}/forms",
    tags=["job_forms"],
    dependencies=[Depends(require_onboarded_user)],
)


@router.get("", response_model=list[JobFormResponse])
def list_forms(
    job_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[JobFormResponse]:
    """List all forms associated with a job."""
    stmt = select(JobForm).where(JobForm.job_id == job_id)
    forms = session.execute(stmt).scalars().all()
    results = []
    for f in forms:
        parsed = f.parsed_structure or {}
        results.append(
            JobFormResponse(
                id=f.id,
                job_id=f.job_id,
                original_filename=f.original_filename,
                file_type=f.file_type,
                form_type=f.form_type,
                is_parsed=f.is_parsed,
                total_fields=parsed.get("total_fields"),
                auto_fillable=parsed.get("auto_fillable"),
                needs_manual=parsed.get("needs_manual"),
                created_at=f.created_at,
            )
        )
    return results


@router.post("", response_model=JobFormResponse, status_code=201)
async def upload_form(
    job_id: int,
    file: UploadFile,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobFormResponse:
    """Upload an employer form and parse its structure."""
    # Validate job exists
    job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")

    # Validate file type
    filename = file.filename or "form.docx"
    ext = Path(filename).suffix.lower()
    if ext not in (".doc", ".docx", ".pdf"):
        raise HTTPException(400, "Only .doc, .docx, and .pdf files are supported")

    # Write to temp file first
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.close()

        # Parse locally if DOCX
        parsed_structure = None
        is_parsed = False
        form_type = "other"

        if ext in (".doc", ".docx"):
            try:
                from app.services.form_parser import parse_form_document

                parse_path = tmp.name
                if ext == ".doc":
                    from app.services.doc_converter import convert_doc_to_docx

                    docx_path = convert_doc_to_docx(tmp.name)
                    parse_path = str(docx_path)
                parsed_structure = parse_form_document(parse_path, job_id)
                is_parsed = True
                sections = parsed_structure.get("sections", [])
                if sections:
                    types = [s["type"] for s in sections]
                    form_type = max(set(types), key=types.count)
            except Exception as exc:
                logger.warning("Form parsing failed for %s: %s", filename, exc)

        # Upload to storage
        stored_name = f"job{job_id}_{filename}"
        stored_path = upload_file(tmp.name, "forms/", stored_name)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    # Create DB record
    job_form = JobForm(
        job_id=job_id,
        uploaded_by_user_id=user.id,
        original_filename=filename,
        storage_url=stored_path,
        file_type=ext.lstrip("."),
        form_type=form_type,
        parsed_structure=parsed_structure,
        is_parsed=is_parsed,
    )
    session.add(job_form)
    session.commit()

    return JobFormResponse(
        id=job_form.id,
        job_id=job_form.job_id,
        original_filename=job_form.original_filename,
        file_type=job_form.file_type,
        form_type=job_form.form_type,
        is_parsed=job_form.is_parsed,
        total_fields=(parsed_structure or {}).get("total_fields"),
        auto_fillable=(parsed_structure or {}).get("auto_fillable"),
        needs_manual=(parsed_structure or {}).get("needs_manual"),
        created_at=job_form.created_at,
    )


@router.get("/{form_id}", response_model=JobFormResponse)
def get_form(
    job_id: int,
    form_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobFormResponse:
    """Get form detail including parsed structure."""
    form = session.execute(
        select(JobForm).where(JobForm.id == form_id, JobForm.job_id == job_id)
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Form not found")

    parsed = form.parsed_structure or {}
    return JobFormResponse(
        id=form.id,
        job_id=form.job_id,
        original_filename=form.original_filename,
        file_type=form.file_type,
        form_type=form.form_type,
        is_parsed=form.is_parsed,
        total_fields=parsed.get("total_fields"),
        auto_fillable=parsed.get("auto_fillable"),
        needs_manual=parsed.get("needs_manual"),
        created_at=form.created_at,
    )


@router.delete("/{form_id}")
def delete_form(
    job_id: int,
    form_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Delete a form and its uploaded file."""
    form = session.execute(
        select(JobForm).where(JobForm.id == form_id, JobForm.job_id == job_id)
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Form not found")

    # Remove file from storage
    delete_file(form.storage_url)

    session.delete(form)
    session.commit()
    return {"status": "deleted", "form_id": form_id}


@router.post("/{form_id}/reparse", response_model=JobFormResponse)
def reparse_form(
    job_id: int,
    form_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JobFormResponse:
    """Re-parse an existing form."""
    form = session.execute(
        select(JobForm).where(JobForm.id == form_id, JobForm.job_id == job_id)
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(404, "Form not found")

    if form.file_type != "docx":
        raise HTTPException(400, "Only DOCX forms can be parsed")

    from app.services.form_parser import parse_form_document

    local_path = download_to_tempfile(form.storage_url, suffix=".docx")
    try:
        parsed = parse_form_document(str(local_path), job_id)
    finally:
        if is_gcs_path(form.storage_url):
            local_path.unlink(missing_ok=True)
    form.parsed_structure = parsed
    form.is_parsed = True

    sections = parsed.get("sections", [])
    if sections:
        types = [s["type"] for s in sections]
        form.form_type = max(set(types), key=types.count)

    session.commit()

    return JobFormResponse(
        id=form.id,
        job_id=form.job_id,
        original_filename=form.original_filename,
        file_type=form.file_type,
        form_type=form.form_type,
        is_parsed=form.is_parsed,
        total_fields=parsed.get("total_fields"),
        auto_fillable=parsed.get("auto_fillable"),
        needs_manual=parsed.get("needs_manual"),
        created_at=form.created_at,
    )
