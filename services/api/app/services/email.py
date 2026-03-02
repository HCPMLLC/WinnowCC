"""Transactional email via Resend SDK and SMS via Telnyx."""

import logging
import os
import uuid

import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL", "Winnow <hello@winnowcc.ai>").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

# Telnyx SMS config
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()
TELNYX_FROM_NUMBER = (
    os.getenv("TELNYX_FROM_NUMBER", "").strip()
    or os.getenv("TELNYX_PHONE_NUMBER", "").strip()
)

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


def _send(payload: dict, description: str) -> str | None:
    """Send an email via Resend with logging and error context.

    Automatically injects headers that improve inbox placement:
    - ``X-Entity-Ref-ID``: unique per message to prevent thread-grouping
    - ``X-Priority``: marks transactional mail as normal priority

    Returns the Resend message ID on success, or ``None`` on failure.
    """
    # Inject deliverability headers (don't overwrite caller-supplied ones)
    headers = payload.get("headers", {})
    headers.setdefault("X-Entity-Ref-ID", uuid.uuid4().hex)
    headers.setdefault("List-Unsubscribe", "<mailto:unsubscribe@winnowcc.ai>")
    payload["headers"] = headers
    try:
        result = resend.Emails.send(payload)
        msg_id = result.get("id") if isinstance(result, dict) else result
        logger.info(
            "Email sent: %s to=%s id=%s",
            description,
            payload["to"],
            msg_id,
        )
        return msg_id
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
            "text": (
                "Click the link below to reset your password. "
                "This link expires in 30 minutes.\n\n"
                f"{reset_url}\n\n"
                "If you didn't request this, you can safely ignore this email."
            ),
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
    job_line_html = (
        f" for the <strong>{job_title}</strong> position" if job_title else ""
    )
    job_line_text = f" for the {job_title} position" if job_title else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"{recruiter_company} wants to connect with you on Winnow",
            "text": (
                f"A recruiter from {recruiter_company} is interested in connecting "
                f"with you{job_line_text}.\n\n"
                "Review their message and decide whether to share your contact "
                "information.\n\n"
                f"View Request on Winnow: {dashboard_url}\n\n"
                "You are in control — your contact details are only shared if "
                "you accept the introduction."
            ),
            "html": (
                "<p>A recruiter from "
                f"<strong>{recruiter_company}</strong> "
                "is interested in connecting with "
                f"you{job_line_html}.</p>"
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

    job_line_html = f" for <strong>{job_title}</strong>" if job_title else ""
    job_line_text = f" for {job_title}" if job_title else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": f"Introduction accepted — {candidate_name} on Winnow",
            "text": (
                f"Great news! {candidate_name} has accepted your "
                f"introduction request{job_line_text}.\n\n"
                f"You can now reach them at:\n"
                f"Email: {candidate_email}\n\n"
                "We recommend reaching out within "
                "48 hours while interest is fresh."
            ),
            "html": (
                f"<p>Great news! <strong>{candidate_name}</strong> has accepted your "
                f"introduction request{job_line_html}.</p>"
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
            "subject": "Your Winnow sign-in verification code",
            "text": (
                f"Your Winnow verification code is: {otp_code}\n\n"
                "Enter this code to complete your sign-in.\n"
                "This code expires in 10 minutes.\n\n"
                "If you didn't try to sign in, you can safely ignore this email."
            ),
            "html": (
                "<p>Enter this code to complete your sign-in:</p>"
                '<p style="font-size:28px;font-family:monospace;font-weight:bold;'
                'letter-spacing:6px;text-align:center;padding:12px 0;">'
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
    error_line_html = f"&bull; {errors:,} files failed to parse<br>" if errors else ""
    skip_line_html = f"&bull; {skipped:,} duplicates skipped<br>" if skipped else ""
    error_line_text = f"- {errors:,} files failed to parse\n" if errors else ""
    skip_line_text = f"- {skipped:,} duplicates skipped\n" if skipped else ""
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": (
                f"Your resume import is complete \u2014 {imported:,} candidates ready"
            ),
            "text": (
                "Your bulk resume import has finished processing.\n\n"
                f"{total:,} files processed:\n"
                f"- {imported:,} new candidates imported\n"
                f"{skip_line_text}"
                f"{error_line_text}"
                f"\nView your candidates: {pipeline_url}\n"
                f"View import details: {results_url}"
            ),
            "html": (
                "<p>Your bulk resume import has finished processing.</p>"
                f"<p><strong>{total:,}</strong> files processed:<br>"
                f"&bull; {imported:,} new candidates imported<br>"
                f"{skip_line_html}"
                f"{error_line_html}"
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

    # Normalize to E.164 (+1XXXXXXXXXX) — handles numbers missing country code
    digits = "".join(c for c in to_phone if c.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    to_phone = "+" + digits

    try:
        import time

        import telnyx

        client = telnyx.Telnyx(api_key=TELNYX_API_KEY)
        result = client.messages.send(
            from_=TELNYX_FROM_NUMBER,
            to=to_phone,
            text=(
                f"Your Winnow verification code is "
                f"{otp_code}. It expires in 10 minutes."
            ),
        )
        msg_id = None
        if hasattr(result, "data") and hasattr(result.data, "id"):
            msg_id = result.data.id
        else:
            msg_id = getattr(result, "id", None)
        logger.info("SMS queued: mfa_otp to=%s id=%s", to_phone, msg_id)

        # Poll delivery status — carrier may silently reject (e.g. 10DLC)
        if msg_id:
            time.sleep(2)
            status_result = client.messages.retrieve(str(msg_id))
            recipients = []
            if hasattr(status_result, "data") and hasattr(status_result.data, "to"):
                recipients = status_result.data.to or []
            for recipient in recipients:
                if getattr(recipient, "status", "") in (
                    "delivery_failed",
                    "sending_failed",
                ):
                    errors = getattr(status_result.data, "errors", [])
                    err_detail = errors[0].detail if errors else "carrier rejected"
                    raise RuntimeError(
                        f"SMS delivery failed for {to_phone}: {err_detail}"
                    )
        logger.info("SMS confirmed: mfa_otp to=%s id=%s", to_phone, msg_id)
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
            "text": (
                "Click the link below to verify your email address. "
                "This link expires in 30 minutes.\n\n"
                f"{verify_url}\n\n"
                "If you didn't create a Winnow account, "
                "you can safely ignore this email."
            ),
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


def send_trust_quarantine_email(
    to_email: str,
    status: str,
    reasons: list[dict],
) -> None:
    """Notify a candidate that their profile has entered soft or hard quarantine."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping trust quarantine email to %s", to_email
        )
        return

    _REASON_LABELS: dict[str, str] = {
        "identity_missing_core_fields": (
            "Your profile appears to be missing a name or work history."
        ),
        "resume_overlapping_dates": ("Your resume shows overlapping employment dates."),
        "resume_keyword_stuffing": (
            "Your resume contains unusually repetitive content."
        ),
        "online_malformed_urls": (
            "One or more profile URLs appear to be incorrectly formatted."
        ),
        "abuse_duplicate_resume_hash": (
            "Your resume file matches one already on file in our system."
        ),
        "abuse_frequent_uploads": (
            "We detected an unusually high number of resume uploads from your account."
        ),
    }

    settings_url = f"{FRONTEND_URL}/settings"
    reason_bullets_text = "\n".join(
        f"- {_REASON_LABELS.get(r['code'], r.get('message', r['code']))}"
        for r in reasons
    )
    reason_bullets_html = "".join(
        f"<li>{_REASON_LABELS.get(r['code'], r.get('message', r['code']))}</li>"
        for r in reasons
    )

    if status == "soft_quarantine":
        subject = "Action needed: Your Winnow profile needs a quick review"
        text_body = (
            "We noticed a few things on your Winnow profile that need a quick look "
            "before we can continue matching you with jobs.\n\n"
            "Here's what we noticed:\n"
            f"{reason_bullets_text}\n\n"
            "Matching has been paused temporarily while we sort this out. "
            "This is usually resolved quickly — just visit your settings to "
            "request a review and we'll take it from there.\n\n"
            f"Go to Settings: {settings_url}\n\n"
            "Thanks for your patience."
        )
        html_body = (
            "<p>We noticed a few things on your Winnow profile that need a quick look "
            "before we can continue matching you with jobs.</p>"
            "<p><strong>Here's what we noticed:</strong></p>"
            f"<ul>{reason_bullets_html}</ul>"
            "<p>Matching has been paused temporarily while we sort this out. "
            "This is usually resolved quickly — just visit your settings to "
            "request a review and we'll take it from there.</p>"
            f'<p><a href="{settings_url}">Go to Settings</a></p>'
            "<p>Thanks for your patience.</p>"
        )
    else:  # hard_quarantine
        subject = "Your Winnow account is under review"
        text_body = (
            "Your Winnow account access has been temporarily restricted while our "
            "team reviews some concerns with your profile.\n\n"
            "Here's what triggered the review:\n"
            f"{reason_bullets_text}\n\n"
            "Our team will review your account within 2–3 business days. "
            "In the meantime, you can visit your settings to see your current status "
            "or submit additional information.\n\n"
            f"Go to Settings: {settings_url}\n\n"
            "We appreciate your patience."
        )
        html_body = (
            "<p>Your Winnow account access has been temporarily restricted while our "
            "team reviews some concerns with your profile.</p>"
            "<p><strong>Here's what triggered the review:</strong></p>"
            f"<ul>{reason_bullets_html}</ul>"
            "<p>Our team will review your account within 2–3 business days. "
            "In the meantime, you can visit your settings to see your current status "
            "or submit additional information.</p>"
            f'<p><a href="{settings_url}">Go to Settings</a></p>'
            "<p>We appreciate your patience.</p>"
        )

    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        },
        "trust_quarantine",
    )


def send_payment_failed_email(to_email: str) -> None:
    """Notify a user that their payment failed (FTC compliance)."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping payment failed email to %s",
            to_email,
        )
        return

    settings_url = f"{FRONTEND_URL}/settings"
    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Action required: Your Winnow payment was unsuccessful",
            "text": (
                "We were unable to process your most recent Winnow "
                "subscription payment. Your account has been marked as "
                "past due.\n\n"
                "To avoid any interruption in service, please update "
                "your payment method in Settings.\n\n"
                f"Update payment: {settings_url}\n\n"
                "If you believe this is an error, reply to this email "
                "or contact hello@winnowcc.ai.\n\n"
                "Thank you,\nThe Winnow Team"
            ),
            "html": (
                "<p>We were unable to process your most recent Winnow "
                "subscription payment. Your account has been marked as "
                "past due.</p>"
                "<p>To avoid any interruption in service, please "
                '<a href="' + settings_url + '">update your payment '
                "method in Settings</a>.</p>"
                "<p>If you believe this is an error, reply to this email "
                "or contact "
                '<a href="mailto:hello@winnowcc.ai">hello@winnowcc.ai'
                "</a>.</p>"
                "<p>Thank you,<br>The Winnow Team</p>"
            ),
        },
        "payment_failed",
    )


def send_subscription_canceled_email(to_email: str, end_date: str) -> None:
    """Confirm subscription cancellation (FTC negative option rule)."""
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping cancellation email to %s",
            to_email,
        )
        return

    resend.api_key = RESEND_API_KEY
    _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": "Your Winnow subscription has been canceled",
            "text": (
                "This confirms that your Winnow subscription has been "
                "canceled.\n\n"
                f"You will continue to have access to paid features "
                f"until {end_date}. After that date, your account will "
                "revert to the free tier.\n\n"
                "Your data will be retained for 30 days after the end "
                "of your billing period. You can resubscribe at any "
                "time from Settings.\n\n"
                "If you did not request this cancellation, please "
                "contact hello@winnowcc.ai immediately.\n\n"
                "Thank you for being a Winnow user,\nThe Winnow Team"
            ),
            "html": (
                "<p>This confirms that your Winnow subscription has "
                "been canceled.</p>"
                f"<p>You will continue to have access to paid features "
                f"until <strong>{end_date}</strong>. After that date, "
                "your account will revert to the free tier.</p>"
                "<p>Your data will be retained for 30 days after the "
                "end of your billing period. You can resubscribe at "
                "any time from Settings.</p>"
                "<p>If you did not request this cancellation, please "
                "contact "
                '<a href="mailto:hello@winnowcc.ai">hello@winnowcc.ai'
                "</a> immediately.</p>"
                "<p>Thank you for being a Winnow user,<br>"
                "The Winnow Team</p>"
            ),
        },
        "subscription_canceled",
    )


def send_weekly_digest_email(
    to_email: str,
    first_name: str | None,
    summary_text: str,
    top_matches: list[dict],
    hidden_gem: dict | None,
    market_stats: dict,
    new_match_count: int,
) -> str | None:
    """Send personalized weekly job market digest.

    Returns the Resend message ID on success, or ``None`` if skipped.
    """
    if not RESEND_API_KEY:
        logger.error(
            "RESEND_API_KEY not set; skipping weekly digest email to %s", to_email
        )
        return None

    greeting = first_name or "there"
    matches_url = f"{FRONTEND_URL}/matches"
    settings_url = f"{FRONTEND_URL}/settings"

    # Build top matches rows
    matches_text = ""
    matches_html = ""
    for m in top_matches:
        title = m.get("title", "Unknown")
        company = m.get("company", "Unknown")
        score = m.get("score", 0)
        matches_text += f"  - {title} at {company} (match: {score}%)\n"
        matches_html += (
            f"<tr><td style='padding:4px 8px'>{title}</td>"
            f"<td style='padding:4px 8px'>{company}</td>"
            f"<td style='padding:4px 8px;text-align:center'>{score}%</td></tr>"
        )

    # Build hidden gem section
    gem_text = ""
    gem_html = ""
    if hidden_gem:
        gem_title = hidden_gem.get("title", "Unknown")
        gem_company = hidden_gem.get("company", "Unknown")
        gem_score = hidden_gem.get("score", 0)
        gem_id = hidden_gem.get("job_id", "")
        gem_url = f"{matches_url}?highlight={gem_id}"
        gem_text = (
            f"\nHidden Gem: {gem_title} at {gem_company} "
            f"(match: {gem_score}%)\n"
            f"Check it out: {gem_url}\n"
        )
        gem_html = (
            "<div style='margin:16px 0;padding:12px;background:#f0f9ff;"
            "border-left:4px solid #0284c7;border-radius:4px'>"
            "<p style='margin:0 0 4px 0;font-weight:bold'>"
            "Hidden Gem You Might Have Missed</p>"
            f"<p style='margin:0'>{gem_title} at {gem_company} "
            f"(match: {gem_score}%)</p>"
            f"<p style='margin:8px 0 0 0'><a href=\"{gem_url}\" "
            "style='color:#0284c7'>View this match &rarr;</a></p>"
            "</div>"
        )

    # Market stats
    total_jobs = market_stats.get("total_active_jobs", 0)
    new_jobs = market_stats.get("new_this_week", 0)
    avg_salary = market_stats.get("avg_salary", 0)
    remote_pct = market_stats.get("remote_pct", 0)
    salary_display = f"${avg_salary:,.0f}" if avg_salary else "N/A"

    stats_text = (
        f"\nMarket Snapshot:\n"
        f"  Active jobs: {total_jobs:,}\n"
        f"  New this week: {new_jobs:,}\n"
        f"  Avg salary: {salary_display}\n"
        f"  Remote: {remote_pct:.0f}%\n"
    )
    stats_html = (
        "<table style='width:100%;border-collapse:collapse;margin:12px 0'>"
        "<tr style='background:#f8fafc'>"
        f"<td style='padding:6px 10px'><strong>Active jobs</strong></td>"
        f"<td style='padding:6px 10px'>{total_jobs:,}</td>"
        f"<td style='padding:6px 10px'><strong>New this week</strong></td>"
        f"<td style='padding:6px 10px'>{new_jobs:,}</td></tr>"
        "<tr>"
        f"<td style='padding:6px 10px'><strong>Avg salary</strong></td>"
        f"<td style='padding:6px 10px'>{salary_display}</td>"
        f"<td style='padding:6px 10px'><strong>Remote</strong></td>"
        f"<td style='padding:6px 10px'>{remote_pct:.0f}%</td></tr>"
        "</table>"
    )

    subject = (
        f"Your Weekly Job Market Digest \u2014 "
        f"{new_match_count} new match{'es' if new_match_count != 1 else ''}"
    )

    text_body = (
        f"Hi {greeting},\n\n"
        f"{summary_text}\n\n"
        f"Your Top Matches This Week:\n{matches_text}"
        f"{gem_text}"
        f"{stats_text}\n"
        f"View all matches: {matches_url}\n\n"
        "Happy job hunting!\nThe Winnow Team\n\n"
        "---\n"
        f"Manage email preferences: {settings_url}\n"
        "You're receiving this because you have a Winnow account "
        "with marketing emails enabled."
    )

    html_body = (
        f"<p>Hi {greeting},</p>"
        f"<p>{summary_text.replace(chr(10), '<br>')}</p>"
        "<h3 style='margin:16px 0 8px 0'>Your Top Matches This Week</h3>"
        "<table style='width:100%;border-collapse:collapse'>"
        "<tr style='background:#f1f5f9'>"
        "<th style='padding:6px 8px;text-align:left'>Role</th>"
        "<th style='padding:6px 8px;text-align:left'>Company</th>"
        "<th style='padding:6px 8px;text-align:center'>Match</th></tr>"
        f"{matches_html}</table>"
        f"{gem_html}"
        "<h3 style='margin:16px 0 8px 0'>Market Snapshot</h3>"
        f"{stats_html}"
        f"<p><a href=\"{matches_url}\" style='display:inline-block;"
        "padding:10px 20px;background:#0284c7;color:#fff;"
        "text-decoration:none;border-radius:6px'>View All Matches</a></p>"
        "<p>Happy job hunting!<br>The Winnow Team</p>"
        "<hr style='margin:24px 0;border:none;border-top:1px solid #e2e8f0'>"
        "<p style='font-size:12px;color:#94a3b8'>"
        f"<a href=\"{settings_url}\" style='color:#94a3b8'>"
        "Manage email preferences</a> &middot; "
        "You\u2019re receiving this because you have a Winnow account "
        "with marketing emails enabled.</p>"
    )

    resend.api_key = RESEND_API_KEY
    return _send(
        {
            "from": RESEND_FROM,
            "to": [to_email],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        },
        "weekly_digest",
    )
