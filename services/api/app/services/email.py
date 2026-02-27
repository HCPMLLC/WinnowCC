"""Transactional email via Resend SDK and SMS via Telnyx."""

import logging
import os

import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "Winnow <noreply@winnowcc.ai>").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# Telnyx SMS config
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()
TELNYX_FROM_NUMBER = os.getenv("TELNYX_FROM_NUMBER", "").strip()

# Startup diagnostics — surface misconfiguration early in Cloud Run logs
if not RESEND_API_KEY:
    logger.error(
        "EMAIL CONFIG: RESEND_API_KEY is not set — all transactional emails "
        "(password reset, MFA, verification) will be silently skipped"
    )
if "localhost" in FRONTEND_URL:
    logger.warning(
        "EMAIL CONFIG: FRONTEND_URL is '%s' — email links will point to "
        "localhost, not your production URL",
        FRONTEND_URL,
    )
if "resend.dev" in RESEND_FROM:
    logger.warning(
        "EMAIL CONFIG: RESEND_FROM_EMAIL is '%s' — the resend.dev sandbox "
        "domain only delivers to the account owner's email. Use a verified "
        "domain for production.",
        RESEND_FROM,
    )

if not TELNYX_API_KEY:
    logger.warning(
        "SMS CONFIG: TELNYX_API_KEY not set — SMS OTP delivery will be unavailable"
    )


def _send(payload: dict, description: str) -> None:
    """Send an email via Resend with logging and error context."""
    try:
        result = resend.Emails.send(payload)
        logger.info(
            "Email sent: %s to=%s id=%s",
            description,
            payload["to"],
            result.get("id") if isinstance(result, dict) else result,
        )
    except Exception:
        logger.error(
            "Email FAILED: %s to=%s from=%s",
            description,
            payload["to"],
            payload["from"],
            exc_info=True,
        )
        raise


def send_password_reset_email(to_email: str, token: str) -> None:
    """Send password reset email. Designed to run in RQ worker."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping password reset email to %s", to_email
        )
        return

    reset_url = f"{FRONTEND_URL}/login?mode=reset&token={token}"
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Reset your Winnow password",
            "html": (
                "<p>Click the link below to reset your password. "
                "This link expires in 30 minutes.</p>"
                f'<p><a href="{reset_url}">Reset Password</a></p>'
                "<p>If you didn't request this, you can safely ignore this email.</p>"
            ),
        },
        "password_reset",
    )


def send_introduction_request_email(
    to_email: str,
    recruiter_company: str,
    job_title: str | None = None,
) -> None:
    """Notify candidate that a recruiter wants to connect."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping introduction request email to %s",
            to_email,
        )
        return

    dashboard_url = f"{FRONTEND_URL}/dashboard"
    job_line = f" for the <strong>{job_title}</strong> position" if job_title else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"{recruiter_company} wants to connect with you on Winnow",
            "html": (
                "<p>A recruiter from "
                f"<strong>{recruiter_company}</strong> "
                "is interested in connecting with "
                f"you{job_line}.</p>"
                "<p>Review their message and decide whether to share your contact "
                "information.</p>"
                f'<p><a href="{dashboard_url}">View Request on Winnow</a></p>'
                "<p>You are in control — your contact details are only shared if "
                "you accept the introduction.</p>"
            ),
        },
        "introduction_request",
    )


def send_introduction_accepted_email(
    to_email: str,
    candidate_name: str,
    candidate_email: str,
    job_title: str | None = None,
) -> None:
    """Notify recruiter that a candidate accepted their introduction request."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping introduction accepted email to %s",
            to_email,
        )
        return

    job_line = f" for <strong>{job_title}</strong>" if job_title else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"Introduction accepted — {candidate_name} on Winnow",
            "html": (
                f"<p>Great news! <strong>{candidate_name}</strong> has accepted your "
                f"introduction request{job_line}.</p>"
                "<p>You can now reach them at:</p>"
                f"<p><strong>Email:</strong> {candidate_email}</p>"
                "<p>We recommend reaching out within "
                "48 hours while interest is fresh.</p>"
            ),
        },
        "introduction_accepted",
    )


def send_mfa_otp_email(to_email: str, otp_code: str) -> None:
    """Send MFA verification code email."""
    if not RESEND_API_KEY:
        logger.error("RESEND_API_KEY not set; skipping MFA OTP email to %s", to_email)
        return

    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"Your Winnow verification code: {otp_code}",
            "html": (
                "<p>Enter this code to complete your sign-in:</p>"
                '<p style="font-size:32px;font-family:monospace;font-weight:bold;'
                'letter-spacing:8px;text-align:center;padding:16px 0;">'
                f"{otp_code}</p>"
                "<p>This code expires in 10 minutes. If you didn't try to sign in, "
                "you can safely ignore this email.</p>"
            ),
        },
        "mfa_otp",
    )


def send_migration_complete_email(
    to_email: str,
    imported: int,
    skipped: int,
    errors: int,
    total: int,
    job_id: int,
) -> None:
    """Notify recruiter that their bulk resume migration is complete."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping migration complete email to %s", to_email
        )
        return

    results_url = f"{FRONTEND_URL}/recruiter/migrate?job={job_id}"
    pipeline_url = f"{FRONTEND_URL}/recruiter/candidates"
    error_line = f"&bull; {errors:,} files failed to parse<br>" if errors else ""
    skip_line = f"&bull; {skipped:,} duplicates skipped<br>" if skipped else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": (
                f"Your resume import is complete \u2014 {imported:,} candidates ready"
            ),
            "html": (
                "<p>Your bulk resume import has finished processing.</p>"
                f"<p><strong>{total:,}</strong> files processed:<br>"
                f"&bull; {imported:,} new candidates imported<br>"
                f"{skip_line}"
                f"{error_line}"
                "</p>"
                f'<p><a href="{pipeline_url}">View your candidates</a> | '
                f'<a href="{results_url}">View import details</a></p>'
            ),
        },
        "migration_complete",
    )


def send_mfa_otp_sms(to_phone: str, otp_code: str) -> None:
    """Send MFA verification code via SMS (Telnyx)."""
    if not TELNYX_API_KEY:
        logger.error("TELNYX_API_KEY not set; skipping MFA OTP SMS to %s", to_phone)
        return
    if not TELNYX_FROM_NUMBER:
        logger.error("TELNYX_FROM_NUMBER not set; skipping MFA OTP SMS to %s", to_phone)
        return

    try:
        import telnyx

        telnyx.api_key = TELNYX_API_KEY
        message = telnyx.Message.create(
            from_=TELNYX_FROM_NUMBER,
            to=to_phone,
            text=(
                f"Your Winnow verification code is "
                f"{otp_code}. It expires in 10 minutes."
            ),
        )
        logger.info("SMS sent: mfa_otp to=%s id=%s", to_phone, message.id)
    except Exception:
        logger.error("SMS FAILED: mfa_otp to=%s", to_phone, exc_info=True)
        raise


def send_verification_email(to_email: str, token: str) -> None:
    """Send email verification link. Designed to run in RQ worker."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping verification email to %s", to_email
        )
        return

    verify_url = f"{FRONTEND_URL}/login?mode=verify-email&token={token}"
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Verify your Winnow email",
            "html": (
                "<p>Click the link below to verify your email address. "
                "This link expires in 30 minutes.</p>"
                f'<p><a href="{verify_url}">Verify Email</a></p>'
                "<p>If you didn't create a Winnow "
                "account, you can safely ignore "
                "this email.</p>"
            ),
        },
        "verification",
    )
