"""
Public application API for career pages.

Handles the Sieve-guided application flow.
"""

import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.career_page_application import (
    ApplicationStatus,
    CareerPageApplication,
)
from app.models.job import Job
from app.schemas.application import (
    ApplicationFormData,
    ApplicationFormResponse,
    ApplicationStartRequest,
    ApplicationStartResponse,
    ApplicationStatusResponse,
    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    CrossJobMatch,
    CrossJobPitchResponse,
    ResumeUploadResponse,
)
from app.services.career_page_service import (
    get_career_page_by_slug,
)
from app.services.sieve_application import (
    check_existing_applicant,
    extract_prefilled_form,
    generate_cross_job_pitch,
    generate_welcome_message,
    process_form_submission,
    process_resume_upload,
    start_application,
    submit_application,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/apply", tags=["career-pages-apply"])


def get_application_by_token(
    session_token: str,
    db: Session,
) -> CareerPageApplication:
    """Get application by session token."""
    result = db.execute(
        select(CareerPageApplication).where(
            CareerPageApplication.session_token == session_token
        )
    )
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found") from None

    if application.status == ApplicationStatus.ABANDONED:
        raise HTTPException(status_code=410, detail="Application expired") from None

    return application


@router.post("/{slug}/start", response_model=ApplicationStartResponse)
def start_application_endpoint(
    slug: str,
    data: ApplicationStartRequest,
    request: Request,
    db: Annotated[Session, Depends(get_session)],
):
    """Start a new application for a job."""
    career_page = get_career_page_by_slug(db, slug)
    if not career_page or not career_page.published:
        raise HTTPException(status_code=404, detail="Career page not found") from None

    # Get job
    result = db.execute(select(Job).where(Job.id == data.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found") from None

    # Start application
    application = start_application(
        db,
        career_page_id=career_page.id,
        job_id=data.job_id,
        email=data.email,
        source_url=data.source_url,
        utm_params=data.utm_params,
        user_agent=request.headers.get("user-agent"),
        ip_address=(request.client.host if request.client else None),
    )

    # Get Sieve config
    sieve_config = (career_page.config or {}).get("sieve", {})

    # Generate welcome message
    welcome = generate_welcome_message(db, application, sieve_config)

    return ApplicationStartResponse(
        application_id=application.id,
        session_token=application.session_token,
        job_title=job.title,
        company_name=career_page.name,
        sieve_welcome=welcome,
        show_resume_upload=True,
        show_linkedin_import=True,
    )


@router.get(
    "/status/{session_token}",
    response_model=ApplicationStatusResponse,
)
def get_application_status(
    session_token: str,
    db: Annotated[Session, Depends(get_session)],
):
    """Get current application status."""
    application = get_application_by_token(session_token, db)

    return ApplicationStatusResponse(
        application_id=application.id,
        status=application.status,
        completeness_score=application.completeness_score,
        missing_fields=application.missing_fields or [],
        can_submit=application.can_submit,
        ips_preview=application.ips_score,
        cross_job_recommendations=(application.cross_job_recommendations or []),
    )


@router.post(
    "/resume/{session_token}",
    response_model=ResumeUploadResponse,
)
def upload_resume(
    session_token: str,
    db: Annotated[Session, Depends(get_session)],
    file: UploadFile = File(...),
):
    """Upload and parse resume."""
    application = get_application_by_token(session_token, db)

    if application.status == ApplicationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Application already submitted",
        ) from None

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided") from None

    allowed_types = [".pdf", ".doc", ".docx", ".txt"]
    ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(f"File type not supported. Allowed: {', '.join(allowed_types)}"),
        ) from None

    # Read file content
    content = file.file.read()

    # Extract text from the uploaded file using the shared extraction pipeline
    try:
        import tempfile
        from pathlib import Path

        from app.services.llm_parser import _call_llm
        from app.services.text_extraction import extract_text

        suffix = ext  # e.g. ".pdf", ".docx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            if suffix == ".txt":
                text = content.decode("utf-8", errors="replace")
            else:
                text = extract_text(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        parsed_data = _call_llm(text)
    except Exception as e:
        logger.error("Resume parsing error: %s", e)
        raise HTTPException(status_code=400, detail="Could not parse resume") from None

    # Store file URL (simplified)
    resume_url = f"/uploads/resumes/{application.id}/{file.filename}"

    sieve_response, completeness, missing = process_resume_upload(
        db, application, parsed_data, resume_url
    )

    # Check for existing applicant
    from app.models.career_page import CareerPage

    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()

    existing_applicant = False
    prefilled_form = extract_prefilled_form(parsed_data)

    if application.email:
        is_existing, existing_data = check_existing_applicant(
            db, application.email, career_page
        )
        if is_existing and existing_data:
            existing_applicant = True
            # Merge existing data into prefilled form (existing data takes priority)
            for key, val in existing_data.items():
                if val:
                    prefilled_form[key] = val

    return ResumeUploadResponse(
        success=True,
        parsed_data=parsed_data,
        completeness_score=completeness,
        missing_fields=missing,
        sieve_response=sieve_response,
        existing_applicant=existing_applicant,
        prefilled_form=prefilled_form,
    )


@router.post("/form/{session_token}", response_model=ApplicationFormResponse)
def submit_form(
    session_token: str,
    data: ApplicationFormData,
    db: Annotated[Session, Depends(get_session)],
):
    """Submit application form data."""
    application = get_application_by_token(session_token, db)

    if application.status == ApplicationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Application already submitted",
        ) from None

    completeness, can_submit = process_form_submission(
        db, application, data.model_dump()
    )

    return ApplicationFormResponse(
        success=True,
        completeness_score=completeness,
        can_submit=can_submit,
    )


@router.get(
    "/cross-jobs/{session_token}",
    response_model=CrossJobPitchResponse,
)
def get_cross_job_pitch(
    session_token: str,
    db: Annotated[Session, Depends(get_session)],
):
    """Get cross-job recommendations and Sieve's pitch."""
    application = get_application_by_token(session_token, db)

    if application.completeness_score < 70:
        raise HTTPException(
            status_code=400,
            detail=("Profile not complete enough for recommendations"),
        ) from None

    pitch, recommendations = generate_cross_job_pitch(db, application)

    return CrossJobPitchResponse(
        matches=[
            CrossJobMatch(
                job_id=rec.get("job_id", 0),
                title=rec.get("title", ""),
                location=rec.get("location"),
                ips_score=rec.get("ips_score", 0),
                explanation=rec.get("explanation", ""),
                already_applied=False,
            )
            for rec in recommendations
        ],
        pitch_message=pitch,
    )


@router.post(
    "/submit/{session_token}",
    response_model=ApplicationSubmitResponse,
)
def submit_application_endpoint(
    session_token: str,
    data: ApplicationSubmitRequest,
    db: Annotated[Session, Depends(get_session)],
):
    """Submit the completed application."""
    application = get_application_by_token(session_token, db)

    if application.status == ApplicationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Application already submitted",
        ) from None

    if not application.can_submit:
        raise HTTPException(
            status_code=400,
            detail=("Application not ready. Please complete required fields."),
        ) from None

    try:
        result = submit_application(db, application, data.apply_to_additional)
    except Exception as e:
        logger.error("Submission error: %s", e)
        raise HTTPException(status_code=500, detail="Submission failed") from None

    return ApplicationSubmitResponse(
        success=True,
        application_id=application.id,
        ips_score=application.ips_score,
        ips_breakdown=application.ips_breakdown or {},
        additional_applications=result.get("additional_applications", []),
        message=("Your application has been submitted! We'll be in touch soon."),
    )


