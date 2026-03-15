"""
Sieve application flow orchestration.

Manages the form-based application experience, integrating
resume parsing, profile completion, and cross-job matching.
"""

import logging
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.career_page import CareerPage
from app.models.career_page_application import (
    ApplicationStatus,
    CareerPageApplication,
)
from app.models.job import Job
from app.models.job_custom_question import (
    CandidateQuestionResponse,
)
from app.models.user import User
from app.services.cross_job_matcher import (
    generate_cross_job_recommendations,
)
from app.services.profile_completeness import (
    calculate_completeness_score,
    get_job_specific_requirements,
    get_missing_fields,
    get_profile_data_from_parsed_resume,
)

logger = logging.getLogger(__name__)


def start_application(
    db: Session,
    career_page_id: UUID,
    job_id: int,
    email: str | None = None,
    source_url: str | None = None,
    utm_params: dict | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> CareerPageApplication:
    """Start a new application session."""
    session_token = secrets.token_urlsafe(32)

    # Check for existing application with same email
    if email:
        existing = db.execute(
            select(CareerPageApplication).where(
                and_(
                    CareerPageApplication.career_page_id == career_page_id,
                    CareerPageApplication.job_id == job_id,
                    CareerPageApplication.email == email,
                    CareerPageApplication.status != ApplicationStatus.ABANDONED,
                )
            )
        )
        existing_app = existing.scalar_one_or_none()
        if existing_app:
            return existing_app

    # Get job details for context
    result = db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError("Job not found")

    # Get job-specific requirements
    job_requirements = get_job_specific_requirements(job)

    # Initialize missing fields
    initial_missing = get_missing_fields({})
    initial_missing.extend(job_requirements)

    application = CareerPageApplication(
        career_page_id=career_page_id,
        job_id=job_id,
        session_token=session_token,
        email=email,
        status=ApplicationStatus.STARTED,
        completeness_score=0,
        missing_fields=initial_missing,
        conversation_history=[],
        source_url=source_url,
        utm_params=utm_params,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    logger.info(
        "Started application %s for job %s",
        application.id,
        job_id,
    )
    return application


def generate_welcome_message(
    db: Session,
    application: CareerPageApplication,
    sieve_config: dict[str, Any],
) -> str:
    """Generate a static welcome message for the application."""
    result = db.execute(select(Job).where(Job.id == application.job_id))
    job = result.scalar_one()

    welcome = (
        f"Welcome! Upload your resume to get started with your "
        f"application for the {job.title} position."
    )

    db.commit()
    return welcome


def process_resume_upload(
    db: Session,
    application: CareerPageApplication,
    parsed_resume_data: dict[str, Any],
    resume_file_url: str,
) -> tuple[str, int, list[dict]]:
    """
    Process uploaded resume.

    Returns (message, completeness_score, missing_fields).
    """
    profile_data = get_profile_data_from_parsed_resume(parsed_resume_data)

    # Always inject application email (overrides whitespace-only values
    # the resume parser may have returned)
    if application.email:
        profile_data["email"] = application.email

    completeness = calculate_completeness_score(profile_data)
    missing = get_missing_fields(profile_data)

    # Add job-specific requirements
    result = db.execute(select(Job).where(Job.id == application.job_id))
    job = result.scalar_one()
    job_requirements = get_job_specific_requirements(job)

    for req in job_requirements:
        if req["field"] not in profile_data:
            missing.append(req)

    # Update application
    application.resume_file_url = resume_file_url
    application.resume_parsed_data = parsed_resume_data
    application.completeness_score = completeness
    application.missing_fields = missing
    application.status = ApplicationStatus.RESUME_UPLOADED
    application.last_activity_at = datetime.utcnow()

    db.commit()

    message = (
        f"Resume parsed successfully! Please review and complete "
        f"the form below to finish your application for {job.title}."
    )
    return message, completeness, missing


def check_existing_applicant(
    db: Session,
    email: str,
    career_page: CareerPage,
) -> tuple[bool, dict[str, Any] | None]:
    """
    Check if applicant already exists in the system.

    Returns (is_existing, candidate_data_dict or None).
    """
    # Check User -> Candidate
    user_result = db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()

    if user:
        candidate_result = db.execute(
            select(Candidate).where(Candidate.user_id == user.id)
        )
        candidate = candidate_result.scalar_one_or_none()

        if candidate and (candidate.first_name and candidate.phone):
            data: dict[str, Any] = {
                "first_name": candidate.first_name or "",
                "last_name": candidate.last_name or "",
                "phone": candidate.phone or "",
                "city": candidate.location_city or "",
                "state": candidate.state or "",
                "work_authorization": candidate.work_authorization or "",
                "total_years_experience": candidate.years_experience,
                "remote_preference": candidate.remote_preference or "",
                "expected_salary": candidate.desired_salary_min,
            }
            return True, data

    # Check RecruiterPipelineCandidate if recruiter career page
    if career_page.tenant_type == "recruiter":
        try:
            from app.models.recruiter_pipeline_candidate import (
                RecruiterPipelineCandidate,
            )

            rpc_result = db.execute(
                select(RecruiterPipelineCandidate).where(
                    RecruiterPipelineCandidate.external_email == email
                )
            )
            rpc = rpc_result.scalars().first()

            if rpc and rpc.external_name:
                name_parts = (rpc.external_name or "").split(" ", 1)
                data = {
                    "first_name": name_parts[0] if name_parts else "",
                    "last_name": name_parts[1] if len(name_parts) > 1 else "",
                    "phone": rpc.external_phone or "",
                    "city": rpc.location or "",
                }
                return True, data
        except Exception:
            logger.debug("RecruiterPipelineCandidate lookup failed")

    return False, None


def extract_prefilled_form(parsed_data: dict[str, Any]) -> dict[str, Any]:
    """Extract form-relevant fields from resume parsed data."""
    profile = get_profile_data_from_parsed_resume(parsed_data)

    form: dict[str, Any] = {}

    # Name
    full_name = profile.get("full_name", "")
    if full_name:
        parts = full_name.strip().split(" ", 1)
        form["first_name"] = parts[0]
        form["last_name"] = parts[1] if len(parts) > 1 else ""

    # Phone
    if profile.get("phone"):
        form["phone"] = profile["phone"]

    # Location - try to parse city/state from location string
    location = profile.get("location", "")
    if location:
        form["city"] = location

    # Experience (use is not None so 0 years still pre-fills)
    if profile.get("years_experience") is not None:
        form["total_years_experience"] = profile["years_experience"]

    # Salary
    if profile.get("desired_salary") is not None:
        form["expected_salary"] = profile["desired_salary"]

    # Work authorization
    if profile.get("work_authorization"):
        form["work_authorization"] = profile["work_authorization"]

    # Relocation
    if profile.get("willing_to_relocate"):
        val = str(profile["willing_to_relocate"]).lower()
        if val in ("yes", "true", "1"):
            form["relocation_willingness"] = "yes"
        elif val in ("no", "false", "0"):
            form["relocation_willingness"] = "no"

    # Current title
    if profile.get("current_title"):
        form["current_title"] = profile["current_title"]
    elif parsed_data.get("current_title"):
        form["current_title"] = parsed_data["current_title"]

    return form


def process_form_submission(
    db: Session,
    application: CareerPageApplication,
    form_data: dict[str, Any],
) -> tuple[int, bool]:
    """
    Process form data submission.

    Merges form fields into resume_parsed_data and stores raw form
    in question_responses["form_data"].

    Returns (completeness_score, can_submit).
    """
    parsed = dict(application.resume_parsed_data or {})

    # Merge form fields into parsed data
    first = form_data.get("first_name", "")
    last = form_data.get("last_name", "")
    full_name = f"{first} {last}".strip()
    if full_name:
        parsed["name"] = full_name
        parsed["full_name"] = full_name

    if form_data.get("phone"):
        parsed["phone"] = form_data["phone"]

    # Build location string
    loc_parts = []
    if form_data.get("city"):
        loc_parts.append(form_data["city"])
    if form_data.get("state"):
        loc_parts.append(form_data["state"])
    if form_data.get("zip_code"):
        loc_parts.append(form_data["zip_code"])
    if loc_parts:
        parsed["location"] = ", ".join(loc_parts)

    if form_data.get("address"):
        parsed["address"] = form_data["address"]

    if form_data.get("total_years_experience") is not None:
        parsed["years_experience"] = form_data["total_years_experience"]

    if form_data.get("expected_salary") is not None:
        parsed["desired_salary"] = form_data["expected_salary"]

    if form_data.get("remote_preference"):
        parsed["remote_preference"] = form_data["remote_preference"]

    if form_data.get("job_type_preference"):
        parsed["job_type_preference"] = form_data["job_type_preference"]

    if form_data.get("work_authorization"):
        parsed["work_authorization"] = form_data["work_authorization"]

    if form_data.get("relocation_willingness"):
        parsed["willing_to_relocate"] = form_data["relocation_willingness"]

    if form_data.get("current_title"):
        parsed["current_title"] = form_data["current_title"]

    application.resume_parsed_data = parsed

    # Store raw form in question_responses
    q_responses = dict(application.question_responses or {})
    q_responses["form_data"] = form_data
    application.question_responses = q_responses

    # Build profile_data directly instead of relying on
    # get_profile_data_from_parsed_resume which can set fields to empty
    # values (e.g. skills: [], experience: []) that block scoring.
    # Start from resume mapping, then override with form-sourced fields.
    profile_data = get_profile_data_from_parsed_resume(parsed)

    # Form-sourced fields always override resume-extracted values.
    # Use explicit None checks so that 0 and "" are handled correctly.
    if parsed.get("full_name"):
        profile_data["full_name"] = parsed["full_name"]
    if parsed.get("phone"):
        profile_data["phone"] = parsed["phone"]
    if parsed.get("location"):
        profile_data["location"] = parsed["location"]
    if parsed.get("current_title"):
        profile_data["current_title"] = parsed["current_title"]
    if parsed.get("years_experience") is not None:
        profile_data["years_experience"] = parsed["years_experience"]
    if parsed.get("work_authorization"):
        profile_data["work_authorization"] = parsed["work_authorization"]
    if parsed.get("desired_salary") is not None:
        profile_data["desired_salary"] = parsed["desired_salary"]
    if parsed.get("willing_to_relocate"):
        profile_data["willing_to_relocate"] = parsed["willing_to_relocate"]

    # Always inject application email (override even whitespace-only
    # values the resume parser may have returned)
    if application.email:
        profile_data["email"] = application.email

    # If a resume was uploaded, the resume itself IS evidence of work
    # history — don't penalize candidates whose resume parser didn't
    # extract a structured experience list.
    if application.resume_file_url and not profile_data.get("work_history"):
        profile_data["work_history"] = ["resume_uploaded"]

    new_completeness = calculate_completeness_score(profile_data)
    missing = get_missing_fields(profile_data)

    application.completeness_score = new_completeness
    application.missing_fields = missing
    application.status = ApplicationStatus.PROFILE_BUILDING
    application.last_activity_at = datetime.utcnow()

    db.commit()

    return new_completeness, application.can_submit


def generate_cross_job_pitch(
    db: Session,
    application: CareerPageApplication,
) -> tuple[str, list[dict]]:
    """Generate cross-job recommendations and Sieve's pitch."""
    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()

    recommendations = generate_cross_job_recommendations(
        db,
        application.candidate_id,
        application.job_id,
        career_page.tenant_id,
        career_page.tenant_type,
        limit=3,
    )

    if not recommendations:
        return "", []

    rec_list = [
        {
            "job_id": rec.recommended_job_id,
            "ips_score": rec.ips_score,
            "explanation": rec.explanation,
        }
        for rec in recommendations
    ]

    # Get job titles
    job_ids = [rec.recommended_job_id for rec in recommendations]
    jobs_result = db.execute(select(Job).where(Job.id.in_(job_ids)))
    jobs_map = {j.id: j for j in jobs_result.scalars().all()}

    for rec in rec_list:
        job_obj = jobs_map.get(rec["job_id"])
        if job_obj:
            rec["title"] = job_obj.title
            rec["location"] = job_obj.location

    # Get applied job title
    job_result = db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one()

    pitch = _generate_pitch_message(job.title, rec_list)

    application.cross_job_recommendations = rec_list
    db.commit()

    return pitch, rec_list


def _generate_pitch_message(
    applied_job_title: str,
    recommendations: list[dict],
) -> str:
    """Generate a cross-job pitch message."""
    if not recommendations:
        return ""

    top_rec = recommendations[0]
    title = top_rec.get("title", "another open role")
    score = top_rec["ips_score"]

    msg = (
        f"Based on your profile, you'd also be a great "
        f"fit for our {title} role — {score}% match!"
    )
    if len(recommendations) > 1:
        msg += (
            f" Plus {len(recommendations) - 1} more "
            f"role{'s' if len(recommendations) > 2 else ''} "
            f"worth checking out."
        )
    return msg


def submit_application(
    db: Session,
    application: CareerPageApplication,
    additional_job_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Submit the completed application.

    Marks application as completed and optionally records
    additional job interest.
    """
    # Completeness gate removed — email + resume is sufficient

    # Mark as completed
    application.status = ApplicationStatus.COMPLETED
    application.completed_at = datetime.utcnow()

    # Save custom question responses
    _save_question_responses(db, application)

    # Apply to additional jobs if requested
    additional: list[int] = []
    if additional_job_ids:
        for job_id in additional_job_ids:
            additional.append(job_id)
        application.additional_applications = additional_job_ids

    # Update career page application count
    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()
    career_page.application_count = (
        (career_page.application_count or 0) + 1 + len(additional)
    )

    db.commit()

    # Best-effort email notification to the career page owner
    try:
        _notify_owner(db, career_page, application)
    except Exception:
        logger.warning(
            "Failed to send application notification for %s",
            application.id,
            exc_info=True,
        )

    return {
        "application_id": str(application.id),
        "additional_applications": additional,
    }


def _save_question_responses(
    db: Session,
    application: CareerPageApplication,
) -> None:
    """Save custom question responses to database."""
    if not application.question_responses:
        return

    for question_id_str, response_data in application.question_responses.items():
        try:
            question_id = UUID(question_id_str)
        except (ValueError, TypeError):
            continue

        response = CandidateQuestionResponse(
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            question_id=question_id,
            response_text=response_data.get("response"),
            confidence_score=response_data.get("confidence"),
            answered_via="sieve",
        )
        db.add(response)

    db.commit()


def _notify_owner(
    db: Session,
    career_page: CareerPage,
    application: CareerPageApplication,
) -> None:
    """Notify the career page owner about a new application (in-app + email)."""
    from app.services.email import send_application_received_email

    # Resolve owner email and user_id
    owner_email: str | None = None
    owner_user_id: int | None = None
    career_page_name = career_page.name or "Career Page"

    if career_page.tenant_type == "recruiter":
        from app.models.recruiter import RecruiterProfile

        rp = db.execute(
            select(RecruiterProfile).where(
                RecruiterProfile.id == career_page.tenant_id
            )
        ).scalar_one_or_none()
        if rp:
            user = db.execute(
                select(User).where(User.id == rp.user_id)
            ).scalar_one_or_none()
            if user:
                owner_email = user.email
                owner_user_id = user.id
    elif career_page.tenant_type == "employer":
        from app.models.employer import EmployerProfile

        ep = db.execute(
            select(EmployerProfile).where(
                EmployerProfile.id == career_page.tenant_id
            )
        ).scalar_one_or_none()
        if ep:
            user = db.execute(
                select(User).where(User.id == ep.user_id)
            ).scalar_one_or_none()
            if user:
                owner_email = user.email
                owner_user_id = user.id

    if not owner_email:
        logger.warning("No owner email found for career page %s", career_page.id)
        return

    # Resolve job title
    job = db.execute(
        select(Job).where(Job.id == application.job_id)
    ).scalar_one_or_none()
    job_title = job.title if job else "Unknown Position"

    # Build applicant name from parsed data
    parsed = application.resume_parsed_data or {}
    applicant_name = parsed.get("full_name") or parsed.get("name") or "Unknown"

    # Create in-app notification for recruiter owners
    if career_page.tenant_type == "recruiter" and owner_user_id:
        from app.models.recruiter_notification import RecruiterNotification

        notification = RecruiterNotification(
            recipient_user_id=owner_user_id,
            notification_type="new_application",
            message=(
                f"New application from {applicant_name} for {job_title}"
            ),
        )
        db.add(notification)
        db.commit()

    send_application_received_email(
        to_email=owner_email,
        applicant_name=applicant_name,
        applicant_email=application.email or "",
        job_title=job_title,
        career_page_name=career_page_name,
    )
