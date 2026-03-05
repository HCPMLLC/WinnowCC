"""Email Ingest Service — processes inbound emails via SendGrid Inbound Parse.

SendGrid receives emails at upload@jobs.winnowcc.ai, extracts sender/subject/
attachments, and POSTs everything as multipart form data to our webhook.

Two-phase flow:
  Phase 1 (webhook, fast):
    1. Validate sender, file type, file size
    2. Save attachment to disk
    3. Send instant acknowledgment email
    4. Enqueue parsing job to RQ worker
  Phase 2 (RQ worker, slow):
    5. Parse document with parse_job_from_file() (PROMPT77)
    6. Create draft employer_job
    7. Send completion or error email
    8. Update email_ingest_log
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.email_ingest_log import EmailIngestLog
from app.services.job_parser import parse_job_from_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INGEST_EMAIL = os.getenv("EMAIL_INGEST_ADDRESS", "upload@jobs.winnowcc.ai")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".doc"}
ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "application/msword",
}
MAX_ATTACHMENT_SIZE_MB = 10

# Directory for persisting attachments between webhook and worker
_INGEST_DIR = os.path.join(tempfile.gettempdir(), "winnow_email_ingest")


def _ensure_ingest_dir() -> str:
    os.makedirs(_INGEST_DIR, exist_ok=True)
    return _INGEST_DIR


# ---------------------------------------------------------------------------
# Phase 1: Webhook — validate, save, ack, enqueue
# ---------------------------------------------------------------------------


async def process_inbound_email(
    sender_email: str,
    sender_name: str,
    subject: str,
    attachment_file,
    attachment_filename: str,
    attachment_content_type: str,
    db: Session,
    raw_headers: dict | None = None,
) -> dict:
    """Phase 1: validate email, save attachment, send ack, enqueue.

    Called by the webhook endpoint. Returns immediately after
    enqueuing so SendGrid gets a fast 200 response.
    """
    # 1. Create log entry
    log_entry = EmailIngestLog(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        status="received",
        metadata_=raw_headers or {},
    )
    db.add(log_entry)
    db.flush()

    # 2. Validate file type
    file_ext = _get_file_extension(attachment_filename)
    if (
        file_ext not in ALLOWED_EXTENSIONS
        and attachment_content_type not in ALLOWED_CONTENT_TYPES
    ):
        log_entry.status = "ignored"
        log_entry.status_detail = (
            f"Unsupported file type: {file_ext} ({attachment_content_type})"
        )
        db.commit()
        _send_no_attachment_reply(sender_email, subject)
        return {"status": "ignored", "reason": "unsupported_file_type"}

    # 3. Read and validate file size
    file_data = await attachment_file.read()
    size_bytes = len(file_data)
    size_mb = size_bytes / (1024 * 1024)
    log_entry.attachment_size_bytes = size_bytes

    if size_mb > MAX_ATTACHMENT_SIZE_MB:
        log_entry.status = "failed"
        log_entry.status_detail = (
            f"File too large: {size_mb:.1f}MB (max {MAX_ATTACHMENT_SIZE_MB}MB)"
        )
        db.commit()
        return {"status": "failed", "reason": "file_too_large"}

    # 4. Match sender to a registered Winnow user (employer or recruiter)
    user, profile = _match_sender_to_user(sender_email, db)

    if not user:
        log_entry.status = "failed"
        log_entry.status_detail = f"Sender {sender_email} not found in Winnow"
        db.commit()
        _send_unregistered_reply(sender_email, subject)
        return {"status": "failed", "reason": "sender_not_registered"}

    log_entry.matched_user_id = user.id

    # Determine if the matched profile is employer or recruiter
    from app.models.employer import EmployerProfile
    from app.models.recruiter import RecruiterProfile

    is_employer = isinstance(profile, EmployerProfile)
    is_recruiter = isinstance(profile, RecruiterProfile)

    if profile:
        log_entry.matched_employer_id = profile.id

    if not profile:
        log_entry.status = "failed"
        log_entry.status_detail = (
            f"User {sender_email} has no employer or recruiter profile — "
            "email upload requires an employer or recruiter account"
        )
        db.commit()
        _send_unregistered_reply(sender_email, subject)
        return {"status": "failed", "reason": "no_employer_profile"}

    # 5. Check AI parsing tier limit (employer profiles only;
    #    recruiters use founder/admin bypass or have no parsing cap)
    if is_employer:
        from app.services.billing import (
            _maybe_reset_employer_counters,
            get_employer_limit,
            get_employer_tier,
        )

        tier = get_employer_tier(profile)
        ai_limit = get_employer_limit(tier, "ai_job_parsing_per_month")
        if isinstance(ai_limit, int) and ai_limit < 999:
            _maybe_reset_employer_counters(profile, db)
            ai_used = profile.ai_parsing_used or 0
            if ai_used >= ai_limit:
                log_entry.status = "failed"
                log_entry.status_detail = (
                    f"AI parsing limit reached: {ai_used}/{ai_limit} (tier={tier})"
                )
                db.commit()
                _send_limit_reached_reply(sender_email, subject, tier, ai_limit)
                return {
                    "status": "failed",
                    "reason": "tier_limit_reached",
                }

    # 6. Save attachment to shared storage (GCS in prod, local disk in dev)
    #    so the worker container can access it.
    from app.services.storage import upload_bytes

    import hashlib

    file_hash = hashlib.sha256(file_data).hexdigest()[:12]
    suffix = file_ext if file_ext else ".docx"
    stored_name = f"{file_hash}_{attachment_filename}"
    stored_path = upload_bytes(
        file_data, "email_ingest/", stored_name
    )

    # 7. Mark as queued and commit
    log_entry.status = "queued"
    log_entry.status_detail = f"Saved to {stored_path}, enqueuing"
    db.commit()

    # 8. Send instant acknowledgment
    _send_acknowledgment(sender_email, subject, attachment_filename)

    # 9. Enqueue the heavy work to the RQ worker
    from app.services.queue import get_queue

    get_queue().enqueue(
        process_email_parse_job,
        log_entry.id,
        stored_path,
        sender_email,
        subject,
        attachment_filename,
        user.id,
        profile.id,
        "recruiter" if is_recruiter else "employer",
    )

    logger.info(
        "Email from %s queued for parsing (log=%s)",
        sender_email,
        log_entry.id,
    )
    return {"status": "queued", "log_id": log_entry.id}


# ---------------------------------------------------------------------------
# Phase 2: RQ Worker — parse, create draft, send result email
# ---------------------------------------------------------------------------


def process_email_parse_job(
    log_id: int,
    file_path: str,
    sender_email: str,
    subject: str,
    attachment_filename: str,
    user_id: int,
    profile_id: int,
    profile_type: str = "employer",
) -> None:
    """Phase 2: parse the document and create a draft job.

    Runs in the RQ worker. Opens its own DB session.
    profile_type is "employer" or "recruiter".
    """
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        _do_parse_and_create(
            session,
            log_id,
            file_path,
            sender_email,
            subject,
            attachment_filename,
            user_id,
            profile_id,
            profile_type,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        # Clean up stored file and any local temp copy
        from app.services.storage import delete_file
        delete_file(file_path)


def _do_parse_and_create(
    db: Session,
    log_id: int,
    file_path: str,
    sender_email: str,
    subject: str,
    attachment_filename: str,
    user_id: int,
    profile_id: int,
    profile_type: str = "employer",
) -> None:
    """Inner logic for Phase 2, using an injected session."""
    log_entry = db.query(EmailIngestLog).filter(EmailIngestLog.id == log_id).first()
    if not log_entry:
        logger.error("EmailIngestLog %s not found", log_id)
        return

    log_entry.status = "processing"
    db.commit()

    # 1. Download file from shared storage to a local temp file
    from app.services.storage import download_to_tempfile, delete_file

    suffix = ""
    if "." in attachment_filename:
        suffix = "." + attachment_filename.rsplit(".", 1)[-1].lower()
    local_path = download_to_tempfile(file_path, suffix=suffix)

    # 2. Parse with the unified job parser (PROMPT77)
    try:
        parsed_data = parse_job_from_file(
            file_path=str(local_path),
            source="email_upload",
            employer_id=str(profile_id),
            user_id=str(user_id),
        )
        if not parsed_data or not parsed_data.get("title"):
            logger.warning(
                "Empty parse result for %s from %s",
                attachment_filename,
                sender_email,
            )
            log_entry.status = "failed"
            log_entry.status_detail = "No job details could be extracted"
            log_entry.processed_at = datetime.now(UTC)
            db.commit()
            _send_parse_error_reply(sender_email, subject, attachment_filename, profile_type)
            return
        confidence = parsed_data.get("parsing_confidence", 0.0)
        log_entry.parsing_confidence = confidence
        log_entry.status = "parsed"
        db.commit()
    except Exception as e:
        logger.error(
            "Parse failed for %s from %s: %s",
            attachment_filename,
            sender_email,
            e,
            exc_info=True,
        )
        log_entry.status = "failed"
        log_entry.status_detail = f"Parsing failed: {e}"
        log_entry.processed_at = datetime.now(UTC)
        db.commit()
        _send_parse_error_reply(sender_email, subject, attachment_filename, profile_type)
        return

    # 3. Create draft job (employer_job or recruiter_job based on profile)
    try:
        if profile_type == "recruiter":
            from app.models.recruiter_job import RecruiterJob

            job = RecruiterJob(
                recruiter_profile_id=profile_id,
                title=parsed_data.get("title", "Untitled Position"),
                description=parsed_data.get("description", ""),
                requirements=parsed_data.get(
                    "requirements",
                    parsed_data.get("requirements_text", ""),
                ),
                location=parsed_data.get("location", ""),
                remote_policy=parsed_data.get("remote_policy", ""),
                employment_type=parsed_data.get("employment_type", "full-time"),
                salary_min=parsed_data.get("salary_min"),
                salary_max=parsed_data.get("salary_max"),
                salary_currency=parsed_data.get("salary_currency", "USD"),
                status="draft",
                department=parsed_data.get("department"),
                job_id_external=parsed_data.get("job_id_external"),
                job_category=parsed_data.get("job_category"),
                client_company_name=parsed_data.get("company", ""),
            )
        else:
            from app.models.employer import EmployerJob

            job = EmployerJob(
                employer_id=profile_id,
                title=parsed_data.get("title", "Untitled Position"),
                description=parsed_data.get("description", ""),
                requirements=parsed_data.get(
                    "requirements",
                    parsed_data.get("requirements_text", ""),
                ),
                location=parsed_data.get("location", ""),
                remote_policy=parsed_data.get("remote_policy", ""),
                employment_type=parsed_data.get("employment_type", "full-time"),
                salary_min=parsed_data.get("salary_min"),
                salary_max=parsed_data.get("salary_max"),
                salary_currency=parsed_data.get("salary_currency", "USD"),
                status="draft",
                parsed_from_document=True,
                parsing_confidence=parsed_data.get("confidence", 0.0),
                source_document_url=(f"email-upload://{attachment_filename}"),
                job_id_external=parsed_data.get("job_id_external"),
                department=parsed_data.get("department"),
                job_category=parsed_data.get("job_category"),
                job_type=parsed_data.get("job_type"),
                certifications_required=parsed_data.get("certifications_required"),
                start_date=parsed_data.get("start_date"),
                close_date=parsed_data.get("close_date"),
            )

        db.add(job)
        db.flush()
        job_id = job.id

        log_entry.created_job_id = job_id
        log_entry.status = "draft_created"
        log_entry.status_detail = f"Draft {profile_type} job created: {job_id}"
        log_entry.processed_at = datetime.now(UTC)

        # Increment AI parsing usage counter (employer only)
        if profile_type == "employer":
            from app.models.employer import EmployerProfile
            from app.services.billing import increment_employer_counter

            employer = (
                db.query(EmployerProfile)
                .filter(EmployerProfile.id == profile_id)
                .first()
            )
            if employer:
                increment_employer_counter(employer, "ai_parsing_used", db)

        db.commit()
    except Exception as e:
        logger.error(
            "Job creation failed for %s: %s",
            attachment_filename,
            e,
            exc_info=True,
        )
        log_entry.status = "failed"
        log_entry.status_detail = f"Job creation failed: {e}"
        log_entry.processed_at = datetime.now(UTC)
        db.commit()
        return

    # 3. Send completion email with correct review URL
    review_path = (
        "recruiter/jobs" if profile_type == "recruiter" else "employer/jobs"
    )
    logger.info(
        "Sending success email for job %s: title=%r confidence=%s keys=%s",
        job_id,
        parsed_data.get("title"),
        parsed_data.get("parsing_confidence"),
        list(parsed_data.keys()),
    )
    _send_success_reply(sender_email, subject, parsed_data, job_id, review_path)

    logger.info("Draft job %s created from email by %s", job_id, sender_email)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _get_file_extension(filename: str) -> str:
    """Extract lowercase file extension including the dot."""
    if not filename:
        return ""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


def extract_email_address(from_field: str) -> tuple[str, str]:
    """Extract email and display name from RFC 5322 'From' field.

    Handles formats:
      - "Display Name <email@domain.com>"
      - "email@domain.com"
      - "<email@domain.com>"

    Returns (email, display_name).
    """
    match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', from_field)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip().lower()
        return email, name

    # No angle brackets — try the whole string as an email
    email = from_field.strip().lower()
    return email, ""


def _match_sender_to_user(sender_email: str, db: Session) -> tuple:
    """Look up the sender's email in the users table.

    Also checks employer_profile.billing_email as fallback.
    Returns (user, employer_or_recruiter_profile) or (None, None).
    Supports both employer and recruiter profiles for email ingest.
    """
    from app.models.employer import EmployerProfile
    from app.models.recruiter import RecruiterProfile
    from app.models.user import User

    user = db.query(User).filter(User.email == sender_email).first()

    if not user:
        # Fallback: check employer billing_email
        employer = (
            db.query(EmployerProfile)
            .filter(EmployerProfile.billing_email == sender_email)
            .first()
        )
        if employer:
            user = db.query(User).filter(User.id == employer.user_id).first()
            return (user, employer)
        return (None, None)

    # Check employer profile first
    employer = (
        db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    )
    if employer:
        return (user, employer)

    # Fall back to recruiter profile
    recruiter = (
        db.query(RecruiterProfile).filter(RecruiterProfile.user_id == user.id).first()
    )
    if recruiter:
        return (user, recruiter)

    return (user, None)


def _cleanup_temp(file_path: str) -> None:
    """Remove a temporary file, ignoring errors."""
    try:
        os.unlink(file_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Reply Emails (sent via Resend — existing email service)
# ---------------------------------------------------------------------------


def _send_acknowledgment(to_email: str, original_subject: str, filename: str) -> None:
    """Instant ack: we got your email, parsing now."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        return

    import resend

    resend.api_key = RESEND_API_KEY

    html = (
        "<p>Hi,</p>"
        "<p>We received your file "
        f'"<strong>{filename}</strong>" and are '
        "parsing it now.</p>"
        "<p>You'll get a second email shortly with "
        "the parsed job details and a link to review "
        "and publish the draft.</p>"
        "<p>— Winnow Career Concierge</p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Received, Parsing Now"),
                "html": html,
            },
            description=(f"email-ingest ack for {filename}"),
        )
    except Exception as e:
        logger.error("Failed to send ack to %s: %s", to_email, e)


def _send_limit_reached_reply(
    to_email: str,
    original_subject: str,
    tier: str,
    limit: int,
) -> None:
    """Reply explaining the sender hit their plan's parsing limit."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        return

    import resend

    resend.api_key = RESEND_API_KEY

    upgrade_url = f"{FRONTEND_URL}/employer/billing"
    html = (
        "<p>Hi,</p>"
        "<p>We received your job posting, but your "
        f"<strong>{tier}</strong> plan allows "
        f"<strong>{limit}</strong> AI-parsed job uploads "
        "per month and you've reached that limit.</p>"
        "<p>To upload more jobs via email:</p>"
        "<ol>"
        "<li>Upgrade your plan at "
        f'<a href="{upgrade_url}">{upgrade_url}</a></li>'
        "<li>Or wait until next month when your "
        "limit resets</li>"
        "</ol>"
        "<p>You can still create jobs manually at "
        f'<a href="{FRONTEND_URL}/employer/jobs/new">'
        f"{FRONTEND_URL}/employer/jobs/new</a>.</p>"
        "<p>— Winnow Career Concierge</p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Plan Limit Reached"),
                "html": html,
            },
            description="email-ingest limit-reached reply",
        )
    except Exception as e:
        logger.error(
            "Failed to send limit-reached reply to %s: %s",
            to_email,
            e,
        )


def _send_success_reply(
    to_email: str,
    original_subject: str,
    parsed_data: dict,
    job_id: int,
    review_path: str = "employer/jobs",
) -> None:
    """Completion email with review link."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set; skipping success reply to %s",
            to_email,
        )
        return

    import resend

    resend.api_key = RESEND_API_KEY

    title = parsed_data.get("title") or parsed_data.get("normalized_title") or "your job posting"
    confidence = parsed_data.get("parsing_confidence", 0.0)
    confidence_pct = f"{confidence * 100:.0f}%"
    review_url = f"{FRONTEND_URL}/{review_path}/{job_id}"

    html = (
        "<p>Hi,</p>"
        "<p>Your job posting has been parsed!</p>"
        "<ul>"
        f"<li><strong>Job Title:</strong> {title}</li>"
        f"<li><strong>Confidence:</strong> "
        f"{confidence_pct}</li>"
        "<li><strong>Status:</strong> Draft "
        "(awaiting review)</li>"
        "</ul>"
        "<p>Review and publish your job posting here:"
        "<br>"
        f'<a href="{review_url}">{review_url}</a></p>'
        "<p>Please review before publishing — especially "
        "salary, location, and requirements.</p>"
        "<p>Thank you for using Winnow!</p>"
        "<p>— Winnow Career Concierge<br>"
        f'<a href="{FRONTEND_URL}">'
        f"{FRONTEND_URL}</a></p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Job Draft Created"),
                "html": html,
            },
            description=(f"email-ingest success reply for job {job_id}"),
        )
    except Exception as e:
        logger.error(
            "Failed to send success reply to %s: %s",
            to_email,
            e,
        )


def _send_no_attachment_reply(to_email: str, original_subject: str) -> None:
    """Reply explaining no valid attachment was found."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        return

    import resend

    resend.api_key = RESEND_API_KEY

    upload_url = f"{FRONTEND_URL}/employer/jobs/new"
    html = (
        "<p>Hi,</p>"
        "<p>We received your email but couldn't find a "
        "valid job description attachment.</p>"
        "<p>Please re-send with a <strong>.docx</strong> "
        "or <strong>.pdf</strong> file attached "
        f"(max {MAX_ATTACHMENT_SIZE_MB}MB) and we'll "
        "parse it automatically.</p>"
        "<p>You can also upload directly at: "
        f'<a href="{upload_url}">{upload_url}</a></p>'
        "<p>— Winnow Career Concierge</p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Attachment Needed"),
                "html": html,
            },
            description="email-ingest no-attachment reply",
        )
    except Exception as e:
        logger.error(
            "Failed to send no-attachment reply to %s: %s",
            to_email,
            e,
        )


def _send_unregistered_reply(to_email: str, original_subject: str) -> None:
    """Reply explaining the sender needs a Winnow account."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        return

    import resend

    resend.api_key = RESEND_API_KEY

    signup_url = f"{FRONTEND_URL}/signup"
    html = (
        "<p>Hi,</p>"
        "<p>We received your job posting, but we couldn't "
        "find a Winnow account associated with "
        f"<strong>{to_email}</strong>.</p>"
        "<p>To use the email upload feature:</p>"
        "<ol>"
        f'<li>Sign up at <a href="{signup_url}">'
        f"{signup_url}</a> as a Recruiter or Employer"
        "</li>"
        "<li>Use the same email address you're "
        "sending from</li>"
        "<li>Then re-send your job description file"
        "</li>"
        "</ol>"
        "<p>Already have an account? Make sure you're "
        "sending from the email address you registered "
        "with.</p>"
        "<p>— Winnow Career Concierge</p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Winnow Account Required"),
                "html": html,
            },
            description=("email-ingest unregistered-sender reply"),
        )
    except Exception as e:
        logger.error(
            "Failed to send unregistered reply to %s: %s",
            to_email,
            e,
        )


def _send_parse_error_reply(
    to_email: str,
    original_subject: str,
    filename: str,
    profile_type: str = "employer",
) -> None:
    """Reply explaining the document couldn't be parsed."""
    from app.services.email import RESEND_API_KEY, RESEND_FROM, _send

    if not RESEND_API_KEY:
        return

    import resend

    resend.api_key = RESEND_API_KEY

    upload_path = "recruiter/jobs" if profile_type == "recruiter" else "employer/jobs/new"
    upload_url = f"{FRONTEND_URL}/{upload_path}"
    html = (
        "<p>Hi,</p>"
        "<p>We received your file "
        f'"<strong>{filename}</strong>" but had '
        "trouble extracting the job details.</p>"
        "<p>This can happen if:</p>"
        "<ul>"
        "<li>The document is heavily formatted "
        "with tables/images</li>"
        "<li>The file is password-protected</li>"
        "<li>The content isn't a standard job "
        "description</li>"
        "</ul>"
        "<p>Please try:</p>"
        "<ol>"
        "<li>Save your job description as a clean "
        ".docx with plain text</li>"
        "<li>Or upload directly at "
        f'<a href="{upload_url}">'
        f"{upload_url}</a></li>"
        "</ol>"
        "<p>If this keeps happening, contact us at "
        "hello@winnowcc.com.</p>"
        "<p>— Winnow Career Concierge</p>"
    )

    try:
        _send(
            {
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": (f"Re: {original_subject} — Parsing Issue"),
                "html": html,
            },
            description=(f"email-ingest parse-error reply for {filename}"),
        )
    except Exception as e:
        logger.error(
            "Failed to send parse-error reply to %s: %s",
            to_email,
            e,
        )
