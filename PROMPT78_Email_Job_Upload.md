# PROMPT78: Recruiter Email-to-Job Upload — Send a Job Posting via Email for Smart Parsing

Read CLAUDE.md, AGENTS.md, ARCHITECTURE.md, and PROMPT77_Unified_Job_Parser.md before making changes.

> **DEPENDENCY:** This prompt requires PROMPT77 (Unified Job Parser) to be implemented first
> so that the `parse_job_from_file()` function exists.

---

## Purpose

Allow recruiters and employers to submit job postings by emailing a `.docx` or `.pdf` attachment to `upload@jobs.winnowcc.ai`. The system receives the email, extracts the attachment, runs the unified AI job parser (PROMPT77), creates a **draft** job posting linked to the sender's account, and sends a confirmation email with a link to review and publish.

This removes friction for recruiters who live in their inbox and don't want to log into a web app just to upload a job description.

---

## How It Works (High-Level Flow)

```
Recruiter sends email with .docx to upload@jobs.winnowcc.ai
        ↓
    MX record routes email to SendGrid
        ↓
    SendGrid Inbound Parse extracts sender, subject, attachments
        ↓
    SendGrid POSTs multipart form data to:
      https://api.winnowcc.ai/api/email-ingest/webhook
        ↓
    Winnow API validates sender → saves attachment → enqueues parse job
        ↓
    Worker: runs parse_job_from_file() (PROMPT77 unified parser)
        ↓
    Creates employer_job with status='draft', parsed_from_document=true
        ↓
    Sends confirmation email to recruiter via Resend (existing email service)
```

---

## Triggers — When to Use This Prompt

- Adding email-based job submission for recruiters/employers.
- Extending PROMPT43/77's document upload to work via email (not just web UI).
- Product asks for "email a job posting" or "inbox job submission."

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Unified job parser:** `services/api/app/services/job_parser.py` — `parse_job_from_file()` handles `.docx` and `.pdf` with Claude extraction, fraud/quality scoring (PROMPT77).
2. **Employer job model:** `services/api/app/models/employer_job.py` — stores job postings with `parsed_from_document`, `parsing_confidence`, `source_document_url`.
3. **Queue service:** `services/api/app/services/queue.py` — RQ wrapper for background jobs.
4. **Auth service:** `services/api/app/services/auth.py` — user authentication.
5. **Resend email:** Already configured for transactional email (confirmation emails, notifications).

---

## Why SendGrid Inbound Parse (Not Gmail API)

| Concern | Gmail API Approach | SendGrid Inbound Parse |
|---------|-------------------|----------------------|
| Email receiving | Google Workspace seat ($7-14/mo) | Free subdomain MX record ($0) |
| Push notifications | Pub/Sub topic + subscription + OIDC | SendGrid POSTs directly to your URL |
| Authentication | Service account + domain delegation | Webhook signature or IP allowlist |
| Watch renewal | Cloud Scheduler every 7 days | None needed — always on |
| Attachment parsing | You fetch via Gmail API | SendGrid delivers as multipart form data |
| Reply emails | Gmail API send (requires modify scope) | Use existing Resend service |
| Dependencies added | 3 Python packages | 0 Python packages |
| Setup steps | 10 (GCP Console + Admin Console) | 3 (DNS + SendGrid dashboard) |

---

## Prerequisites

- ✅ PROMPT77 completed (unified job parser exists)
- ✅ DNS access for `winnowcc.ai` (to add MX record for `jobs.winnowcc.ai` subdomain)
- ✅ SendGrid account (free tier is fine — 100 emails/day)
- ✅ Backend deployed (or running locally with ngrok for testing)
- ✅ Redis worker running for async jobs

---

## Implementation Steps

Execute these steps **in order**. Each step builds on the previous one.

---

# PART 1: SENDGRID + DNS SETUP (Done in Browser)

These steps are done in your **web browser**, not in Cursor.

### Step 1: Create a SendGrid Account

**Where:** https://signup.sendgrid.com

1. Go to https://signup.sendgrid.com and create a free account.
2. Verify your email address when prompted.
3. You do NOT need to configure any outbound sending — Winnow uses Resend for that. SendGrid is only for inbound email receiving.

> **Note:** If you already have a SendGrid account, skip this step. The free tier supports inbound parse.

---

### Step 2: Add MX Record for the Ingest Subdomain

**Where:** Your DNS provider (wherever you manage `winnowcc.ai` DNS records — likely Google Cloud DNS or your domain registrar)

You need to add ONE DNS record that tells the internet to route all email sent to `anything@jobs.winnowcc.ai` to SendGrid's mail servers.

**Record to add:**

| Type | Host/Name        | Value              | Priority | TTL  |
|------|------------------|--------------------|----------|------|
| MX   | jobs.winnowcc.ai | mx.sendgrid.net    | 10       | 3600 |

**Step-by-step for Google Cloud DNS (since your project is on GCP):**

1. Go to https://console.cloud.google.com → **Network services → Cloud DNS**.
2. Click on your `winnowcc.ai` zone.
3. Click **Add record set**.
4. DNS name: `jobs.winnowcc.ai.` (note the trailing dot — GCP adds it automatically).
5. Resource record type: **MX**.
6. TTL: `3600`.
7. Priority: `10`.
8. Mail server: `mx.sendgrid.net.`
9. Click **Create**.

**Wait 5-30 minutes** for DNS propagation before testing.

**To verify the MX record is live**, open a terminal and run:

```powershell
nslookup -type=MX jobs.winnowcc.ai
```

You should see `mx.sendgrid.net` in the response.

---

### Step 3: Configure SendGrid Inbound Parse

**Where:** SendGrid Dashboard → https://app.sendgrid.com

1. Log in to SendGrid.
2. In the left sidebar, click **Settings → Inbound Parse**.
3. Click **Add Host & URL**.
4. In the **Receiving Domain** field:
   - Subdomain: `jobs`
   - Domain: Select `winnowcc.ai` from dropdown (or type it if it's not listed — you may need to authenticate the domain first).
5. In the **Destination URL** field:
   - Production: `https://api.winnowcc.ai/api/email-ingest/webhook`
   - Local testing: Use an ngrok URL like `https://abc123.ngrok.io/api/email-ingest/webhook`
6. Check the box: **POST the raw, full MIME message** — this ensures attachments are included in full.
7. **Do NOT** check "Check incoming emails for spam" (we'll handle validation ourselves).
8. Click **Add**.

That's it for the external setup. No Pub/Sub, no service accounts, no watch renewals.

---

# PART 2: DATABASE — INGEST LOG TABLE

### Step 4: Create the Alembic Migration

**Where:** Terminal (PowerShell)

```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "C:\Users\ronle\Documents\resumematch\services\api"
alembic revision -m "add_email_ingest_log"
```

This creates a new file in `services/api/alembic/versions/` with a name like `xxxx_add_email_ingest_log.py`.

### Step 5: Edit the Migration File

**File to edit:** `services/api/alembic/versions/XXXX_add_email_ingest_log.py` (the file just created)

**How:** In Cursor, navigate to `services/api/alembic/versions/` and open the newest file. Replace its contents with:

```python
"""add email ingest log

Revision ID: (auto-generated)
Revises: (auto-generated)
Create Date: (auto-generated)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = ...  # KEEP THE AUTO-GENERATED VALUE
down_revision = ...  # KEEP THE AUTO-GENERATED VALUE
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_ingest_log",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("sendgrid_message_id", sa.String(255), nullable=True),
        sa.Column("sender_email", sa.String(255), nullable=False),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("status_detail", sa.Text, nullable=True),
        sa.Column("attachment_filename", sa.String(500), nullable=True),
        sa.Column("attachment_content_type", sa.String(100), nullable=True),
        sa.Column("attachment_size_bytes", sa.Integer, nullable=True),
        sa.Column("matched_user_id", sa.String(36), nullable=True),
        sa.Column("matched_employer_id", sa.String(36), nullable=True),
        sa.Column("created_job_id", sa.String(36), nullable=True),
        sa.Column("parsing_confidence", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_email_ingest_log_sender", "email_ingest_log", ["sender_email"])
    op.create_index("ix_email_ingest_log_status", "email_ingest_log", ["status"])
    op.create_index("ix_email_ingest_log_received", "email_ingest_log", ["received_at"])


def downgrade() -> None:
    op.drop_table("email_ingest_log")
```

**Important:** Do NOT change the `revision` and `down_revision` values — those are auto-generated by Alembic and link to your migration chain.

### Step 6: Run the Migration

**Where:** Terminal (PowerShell)

```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "C:\Users\ronle\Documents\resumematch\services\api"
alembic upgrade head
```

You should see output like: `INFO  [alembic.runtime.migration] Running upgrade ... -> ... add email ingest log`

---

# PART 3: BACKEND — DATABASE MODEL

### Step 7: Create the SQLAlchemy Model

**File to create:** `services/api/app/models/email_ingest_log.py`

**How:** In Cursor, right-click the `services/api/app/models/` folder → New File → name it `email_ingest_log.py`

**Paste this entire code:**

```python
"""
EmailIngestLog model — tracks every email received at the ingest address.

Stores sender info, processing status, matched user, created job reference,
and parsing confidence for monitoring and debugging.
"""
from sqlalchemy import Column, String, Text, Float, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class EmailIngestLog(Base):
    __tablename__ = "email_ingest_log"

    id = Column(String(36), primary_key=True, server_default=func.gen_random_uuid().cast(String))
    sendgrid_message_id = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)

    # Processing status: received → processing → parsed → draft_created | failed | ignored
    status = Column(String(50), nullable=False, default="received", index=True)
    status_detail = Column(Text, nullable=True)

    # Attachment info
    attachment_filename = Column(String(500), nullable=True)
    attachment_content_type = Column(String(100), nullable=True)
    attachment_size_bytes = Column(Integer, nullable=True)

    # Linked records
    matched_user_id = Column(String(36), nullable=True)
    matched_employer_id = Column(String(36), nullable=True)
    created_job_id = Column(String(36), nullable=True)

    # Parsing results
    parsing_confidence = Column(Float, nullable=True)

    # Raw metadata (headers, diagnostics)
    metadata = Column(JSONB, nullable=True)

    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<EmailIngestLog {self.id} from={self.sender_email} status={self.status}>"
```

### Step 8: Register the Model

**File to edit:** `services/api/app/models/__init__.py`

**What to do:** Open this file in Cursor and add one import line alongside the other model imports:

```python
from app.models.email_ingest_log import EmailIngestLog  # noqa: F401
```

---

# PART 4: BACKEND — EMAIL INGEST SERVICE

### Step 9: Create the Email Ingest Service

This is the core service. It receives the parsed email data from SendGrid's webhook, validates the sender, saves the attachment, calls the unified parser, and creates the draft job.

**File to create:** `services/api/app/services/email_ingest.py`

**How:** In Cursor, right-click the `services/api/app/services/` folder → New File → name it `email_ingest.py`

**Paste this entire code:**

```python
"""
Email Ingest Service — processes inbound emails via SendGrid Inbound Parse.

SendGrid receives emails at upload@jobs.winnowcc.ai, extracts sender/subject/
attachments, and POSTs everything as multipart form data to our webhook.

This service:
  1. Validates the sender is a registered recruiter/employer
  2. Saves the attachment to a temp file
  3. Calls parse_job_from_file() from the unified parser (PROMPT77)
  4. Creates a draft employer_job
  5. Sends confirmation/error emails via Resend (existing email service)
  6. Logs everything in email_ingest_log
"""
import os
import re
import tempfile
import logging
from typing import Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.email_ingest_log import EmailIngestLog
from app.services.job_parser import parse_job_from_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INGEST_EMAIL = os.getenv("EMAIL_INGEST_ADDRESS", "upload@jobs.winnowcc.ai")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://winnowcc.ai")

ALLOWED_EXTENSIONS = {".docx", ".pdf", ".doc"}
ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "application/msword",
}
MAX_ATTACHMENT_SIZE_MB = 10


# ---------------------------------------------------------------------------
# Core Processing Function
# ---------------------------------------------------------------------------

async def process_inbound_email(
    sender_email: str,
    sender_name: str,
    subject: str,
    attachment_file,
    attachment_filename: str,
    attachment_content_type: str,
    db: Session,
    raw_headers: dict = None,
) -> dict:
    """
    Process one inbound email from SendGrid Inbound Parse.

    Args:
        sender_email: The sender's email address (extracted from 'from' field)
        sender_name: The sender's display name
        subject: Email subject line
        attachment_file: The file-like object (from FastAPI UploadFile)
        attachment_filename: Original filename of the attachment
        attachment_content_type: MIME type of the attachment
        db: Database session
        raw_headers: Optional dict of raw email headers for logging

    Returns:
        dict with status and details
    """
    # 1. Create log entry
    log_entry = EmailIngestLog(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        attachment_filename=attachment_filename,
        attachment_content_type=attachment_content_type,
        status="processing",
        metadata=raw_headers or {},
    )
    db.add(log_entry)
    db.flush()

    # 2. Validate file type
    file_ext = _get_file_extension(attachment_filename)
    if file_ext not in ALLOWED_EXTENSIONS and attachment_content_type not in ALLOWED_CONTENT_TYPES:
        log_entry.status = "ignored"
        log_entry.status_detail = f"Unsupported file type: {file_ext} ({attachment_content_type})"
        db.commit()
        await _send_no_attachment_reply(sender_email, subject)
        return {"status": "ignored", "reason": "unsupported_file_type"}

    # 3. Read and validate file size
    file_data = await attachment_file.read()
    size_bytes = len(file_data)
    size_mb = size_bytes / (1024 * 1024)
    log_entry.attachment_size_bytes = size_bytes

    if size_mb > MAX_ATTACHMENT_SIZE_MB:
        log_entry.status = "failed"
        log_entry.status_detail = f"File too large: {size_mb:.1f}MB (max {MAX_ATTACHMENT_SIZE_MB}MB)"
        db.commit()
        return {"status": "failed", "reason": "file_too_large"}

    # 4. Match sender to a registered Winnow user
    user, employer = _match_sender_to_user(sender_email, db)

    if not user:
        log_entry.status = "failed"
        log_entry.status_detail = f"Sender {sender_email} not found in Winnow"
        db.commit()
        await _send_unregistered_reply(sender_email, subject)
        return {"status": "failed", "reason": "sender_not_registered"}

    log_entry.matched_user_id = str(user.id)
    if employer:
        log_entry.matched_employer_id = str(employer.id)

    # 5. Save attachment to temp file
    suffix = file_ext if file_ext else ".docx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    # 6. Parse with the unified job parser (PROMPT77)
    try:
        parsed_data = await parse_job_from_file(
            file_path=tmp_path,
            source="email_upload",
            employer_id=str(employer.id) if employer else None,
            user_id=str(user.id),
        )
        confidence = parsed_data.get("confidence", 0.0)
        log_entry.parsing_confidence = confidence
        log_entry.status = "parsed"
    except Exception as e:
        logger.error(f"Parse failed for {attachment_filename} from {sender_email}: {e}", exc_info=True)
        log_entry.status = "failed"
        log_entry.status_detail = f"Parsing failed: {str(e)}"
        log_entry.processed_at = datetime.now(timezone.utc)
        db.commit()
        await _send_parse_error_reply(sender_email, subject, attachment_filename)
        _cleanup_temp(tmp_path)
        return {"status": "failed", "reason": "parse_error"}

    # 7. Create draft employer_job
    try:
        job_id = _create_draft_job(parsed_data, user, employer, attachment_filename, db)
        log_entry.created_job_id = str(job_id)
        log_entry.status = "draft_created"
        log_entry.status_detail = f"Draft job created: {job_id}"
        log_entry.processed_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Job creation failed for {attachment_filename}: {e}", exc_info=True)
        log_entry.status = "failed"
        log_entry.status_detail = f"Job creation failed: {str(e)}"
        log_entry.processed_at = datetime.now(timezone.utc)
        db.commit()
        _cleanup_temp(tmp_path)
        return {"status": "failed", "reason": "job_creation_error"}

    db.commit()

    # 8. Send confirmation email
    await _send_success_reply(sender_email, subject, parsed_data, job_id)

    # 9. Clean up temp file
    _cleanup_temp(tmp_path)

    logger.info(f"Draft job {job_id} created from email by {sender_email}")
    return {"status": "draft_created", "job_id": str(job_id)}


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


def extract_email_address(from_field: str) -> Tuple[str, str]:
    """
    Extract email and display name from RFC 5322 'From' field.

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


def _match_sender_to_user(sender_email: str, db: Session) -> Tuple:
    """
    Look up the sender's email in the users table.
    Also checks employer_profile.billing_email as fallback.
    Returns (user, employer_profile) or (None, None).
    """
    from app.models.user import User
    from app.models.employer_profile import EmployerProfile

    # Primary lookup: user email matches sender
    user = db.query(User).filter(User.email == sender_email).first()

    if not user:
        # Fallback: check employer billing email
        employer = db.query(EmployerProfile).filter(
            EmployerProfile.billing_email == sender_email
        ).first()
        if employer:
            user = db.query(User).filter(User.id == employer.user_id).first()
            return (user, employer)
        return (None, None)

    # Found user — look up their employer profile
    employer = db.query(EmployerProfile).filter(
        EmployerProfile.user_id == user.id
    ).first()

    return (user, employer)


def _create_draft_job(
    parsed_data: dict,
    user,
    employer,
    original_filename: str,
    db: Session,
) -> str:
    """
    Create an employer_job in 'draft' status from parsed data.
    Returns the new job's ID.
    """
    from app.models.employer_job import EmployerJob

    job = EmployerJob(
        employer_id=employer.id if employer else None,
        user_id=user.id,
        title=parsed_data.get("title", "Untitled Position"),
        description=parsed_data.get("description", ""),
        requirements=parsed_data.get("requirements", parsed_data.get("requirements_text", "")),
        location=parsed_data.get("location", ""),
        remote_policy=parsed_data.get("remote_policy", ""),
        employment_type=parsed_data.get("employment_type", "full-time"),
        salary_min=parsed_data.get("salary_min"),
        salary_max=parsed_data.get("salary_max"),
        salary_currency=parsed_data.get("salary_currency", "USD"),
        status="draft",
        parsed_from_document=True,
        parsing_confidence=parsed_data.get("confidence", 0.0),
        source_document_url=f"email-upload://{original_filename}",
        # PROMPT43 enhanced fields
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
    return job.id


def _cleanup_temp(file_path: str):
    """Remove a temporary file, ignoring errors."""
    try:
        os.unlink(file_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Reply Emails (sent via Resend — your existing email service)
# ---------------------------------------------------------------------------

async def _send_success_reply(to_email: str, original_subject: str, parsed_data: dict, job_id):
    """Send confirmation email with review link."""
    try:
        from app.services.email import send_email  # Your existing Resend wrapper

        title = parsed_data.get("title", "your job posting")
        confidence = parsed_data.get("confidence", 0.0)
        confidence_pct = f"{confidence * 100:.0f}%"
        review_url = f"{FRONTEND_URL}/employer/jobs/{job_id}"

        await send_email(
            to=to_email,
            subject=f"Re: {original_subject} — Job Draft Created",
            html=f"""
            <p>Hi,</p>
            <p>Your job posting has been received and parsed successfully!</p>
            <ul>
                <li><strong>Job Title:</strong> {title}</li>
                <li><strong>Parsing Confidence:</strong> {confidence_pct}</li>
                <li><strong>Status:</strong> Draft (awaiting your review)</li>
            </ul>
            <p>Please review and publish your job posting here:<br>
            <a href="{review_url}">{review_url}</a></p>
            <p>The AI extracted all available fields from your document. Please review
            everything before publishing — especially salary, location, and requirements
            — and make any corrections needed.</p>
            <p>Thank you for using Winnow!</p>
            <p>— Winnow Career Concierge<br>
            <a href="{FRONTEND_URL}">{FRONTEND_URL}</a></p>
            """,
        )
    except Exception as e:
        logger.error(f"Failed to send success reply to {to_email}: {e}")


async def _send_no_attachment_reply(to_email: str, original_subject: str):
    """Reply explaining no valid attachment was found."""
    try:
        from app.services.email import send_email

        await send_email(
            to=to_email,
            subject=f"Re: {original_subject} — Attachment Needed",
            html=f"""
            <p>Hi,</p>
            <p>We received your email but couldn't find a valid job description attachment.</p>
            <p>Please re-send with a <strong>.docx</strong> or <strong>.pdf</strong> file
            attached (max {MAX_ATTACHMENT_SIZE_MB}MB) and we'll parse it automatically.</p>
            <p>You can also upload directly at:
            <a href="{FRONTEND_URL}/employer/jobs/new">{FRONTEND_URL}/employer/jobs/new</a></p>
            <p>— Winnow Career Concierge</p>
            """,
        )
    except Exception as e:
        logger.error(f"Failed to send no-attachment reply to {to_email}: {e}")


async def _send_unregistered_reply(to_email: str, original_subject: str):
    """Reply explaining the sender needs a Winnow account."""
    try:
        from app.services.email import send_email

        await send_email(
            to=to_email,
            subject=f"Re: {original_subject} — Winnow Account Required",
            html=f"""
            <p>Hi,</p>
            <p>We received your job posting, but we couldn't find a Winnow account
            associated with <strong>{to_email}</strong>.</p>
            <p>To use the email upload feature:</p>
            <ol>
                <li>Sign up at <a href="{FRONTEND_URL}/signup">{FRONTEND_URL}/signup</a>
                as a Recruiter or Employer</li>
                <li>Use the same email address you're sending from</li>
                <li>Then re-send your job description file</li>
            </ol>
            <p>Already have an account? Make sure you're sending from the email
            address you registered with.</p>
            <p>— Winnow Career Concierge</p>
            """,
        )
    except Exception as e:
        logger.error(f"Failed to send unregistered reply to {to_email}: {e}")


async def _send_parse_error_reply(to_email: str, original_subject: str, filename: str):
    """Reply explaining the document couldn't be parsed."""
    try:
        from app.services.email import send_email

        await send_email(
            to=to_email,
            subject=f"Re: {original_subject} — Parsing Issue",
            html=f"""
            <p>Hi,</p>
            <p>We received your file "<strong>{filename}</strong>" but had trouble
            extracting the job details.</p>
            <p>This can happen if:</p>
            <ul>
                <li>The document is heavily formatted with tables/images</li>
                <li>The file is password-protected</li>
                <li>The content isn't a standard job description</li>
            </ul>
            <p>Please try:</p>
            <ol>
                <li>Saving your job description as a clean .docx with plain text</li>
                <li>Or uploading it directly at
                <a href="{FRONTEND_URL}/employer/jobs/new">{FRONTEND_URL}/employer/jobs/new</a></li>
            </ol>
            <p>If this keeps happening, contact us at hello@winnowcc.com.</p>
            <p>— Winnow Career Concierge</p>
            """,
        )
    except Exception as e:
        logger.error(f"Failed to send parse-error reply to {to_email}: {e}")
```

---

# PART 5: BACKEND — WEBHOOK ROUTER

### Step 10: Create the Email Ingest Webhook Router

**File to create:** `services/api/app/routers/email_ingest.py`

**How:** In Cursor, right-click `services/api/app/routers/` → New File → name it `email_ingest.py`

**Paste this entire code:**

```python
"""
Email Ingest Webhook Router — receives parsed emails from SendGrid Inbound Parse.

SendGrid POSTs multipart form data containing:
  - from: sender email + name
  - subject: email subject
  - text: plain text body
  - html: HTML body
  - attachmentN: file attachments (attachment1, attachment2, etc.)
  - attachment-info: JSON describing attachments
  - headers: raw email headers
  - envelope: JSON with sender and recipients
  - charsets: JSON with character set info

Endpoints:
  POST /api/email-ingest/webhook  — SendGrid Inbound Parse webhook
  GET  /api/email-ingest/logs     — Admin: view ingest log
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.email_ingest import (
    process_inbound_email,
    extract_email_address,
    ALLOWED_EXTENSIONS,
)
from app.models.email_ingest_log import EmailIngestLog
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email-ingest", tags=["email-ingest"])


@router.post("/webhook")
async def sendgrid_inbound_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives inbound emails from SendGrid Inbound Parse.

    SendGrid POSTs multipart/form-data with email fields and attachments.
    This endpoint does NOT require authentication — SendGrid cannot send auth
    headers. Security is handled via:
      1. Only processing emails from registered Winnow users
      2. Optional: IP allowlisting for SendGrid's IP ranges
    """
    try:
        form = await request.form()
    except Exception as e:
        logger.error(f"Failed to parse form data: {e}")
        raise HTTPException(status_code=400, detail="Invalid form data")

    # ── Extract email fields from SendGrid's POST ────────────────────────
    from_field = form.get("from", "")
    subject = form.get("subject", "")
    envelope_raw = form.get("envelope", "{}")
    headers_raw = form.get("headers", "")
    attachment_info_raw = form.get("attachment-info", "{}")

    # Parse sender email from the 'from' field
    sender_email, sender_name = extract_email_address(from_field)

    if not sender_email:
        logger.warning("Received inbound email with no sender")
        return {"status": "ignored", "reason": "no_sender"}

    logger.info(f"Inbound email from {sender_email}: {subject}")

    # ── Find attachments ─────────────────────────────────────────────────
    # SendGrid sends attachments as 'attachment1', 'attachment2', etc.
    # The 'attachment-info' field is a JSON dict describing each attachment.
    try:
        attachment_info = json.loads(attachment_info_raw)
    except (json.JSONDecodeError, TypeError):
        attachment_info = {}

    # Find the first valid .docx/.pdf attachment
    valid_attachment = None
    valid_attachment_key = None
    valid_attachment_meta = None

    for key, meta in attachment_info.items():
        filename = meta.get("filename", "")
        content_type = meta.get("type", "")
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        if ext in ALLOWED_EXTENSIONS:
            valid_attachment_key = key
            valid_attachment_meta = meta
            break

    if valid_attachment_key:
        valid_attachment = form.get(valid_attachment_key)

    if not valid_attachment or not hasattr(valid_attachment, "read"):
        # No valid attachment found — log and reply
        log_entry = EmailIngestLog(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            status="ignored",
            status_detail="No valid .docx or .pdf attachment",
            metadata={"from": from_field, "attachment_info": attachment_info_raw},
        )
        db.add(log_entry)
        db.commit()

        from app.services.email_ingest import _send_no_attachment_reply
        await _send_no_attachment_reply(sender_email, subject)

        return {"status": "ignored", "reason": "no_valid_attachment"}

    # ── Process the email with attachment ─────────────────────────────────
    filename = valid_attachment_meta.get("filename", "unknown.docx")
    content_type = valid_attachment_meta.get("type", "application/octet-stream")

    result = await process_inbound_email(
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        attachment_file=valid_attachment,
        attachment_filename=filename,
        attachment_content_type=content_type,
        db=db,
        raw_headers={
            "from": from_field,
            "subject": subject,
            "envelope": envelope_raw,
        },
    )

    # Always return 200 to SendGrid so it doesn't retry
    return result


@router.get("/logs")
async def get_ingest_logs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Admin endpoint: View email ingest log entries.
    Useful for monitoring and debugging the email ingest pipeline.
    """
    if not getattr(current_user, "is_admin", False) and getattr(current_user, "role", "") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(EmailIngestLog).order_by(EmailIngestLog.received_at.desc())

    if status:
        query = query.filter(EmailIngestLog.status == status)

    total = query.count()
    logs = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "sender_email": log.sender_email,
                "sender_name": log.sender_name,
                "subject": log.subject,
                "status": log.status,
                "status_detail": log.status_detail,
                "attachment_filename": log.attachment_filename,
                "attachment_size_bytes": log.attachment_size_bytes,
                "parsing_confidence": log.parsing_confidence,
                "created_job_id": str(log.created_job_id) if log.created_job_id else None,
                "received_at": log.received_at.isoformat() if log.received_at else None,
                "processed_at": log.processed_at.isoformat() if log.processed_at else None,
            }
            for log in logs
        ],
    }
```

---

# PART 6: REGISTER THE ROUTER

### Step 11: Add the Router to main.py

**File to edit:** `services/api/app/main.py`

**What to do:** Open this file in Cursor. Find the section where other routers are registered (look for lines like `app.include_router(...)`). Add this line in the same area:

```python
from app.routers.email_ingest import router as email_ingest_router
app.include_router(email_ingest_router)
```

---

# PART 7: ENVIRONMENT VARIABLES

### Step 12: Add Environment Variables

**File to edit:** `services/api/.env`

**Add these lines:**

```env
# Email Ingest (SendGrid Inbound Parse)
EMAIL_INGEST_ADDRESS=upload@jobs.winnowcc.ai
```

That's it — just one env var. The rest of the configuration (Resend for replies, database connection, etc.) already exists.

**For production (Cloud Run):** Add `EMAIL_INGEST_ADDRESS` to your Cloud Run service environment variables.

---

# PART 8: OPTIONAL — SENDGRID IP ALLOWLISTING

### Step 13: (Optional) Restrict Webhook to SendGrid IPs

Since the webhook has no authentication (SendGrid can't send auth headers), you can optionally restrict it to SendGrid's IP ranges. This is a defense-in-depth measure — the real security is that we only process emails from registered users.

**File to edit:** `services/api/app/routers/email_ingest.py`

**Add this at the very top of the `sendgrid_inbound_webhook` function**, right after `async def`:

```python
    # Optional: verify request comes from SendGrid
    # SendGrid publishes their IP ranges at:
    # https://docs.sendgrid.com/for-developers/parsing-email/setting-up-the-inbound-parse-webhook
    # For production hardening, add IP allowlisting here.
    # For now, we rely on sender validation (only registered users can create jobs).
    client_ip = request.client.host
    logger.debug(f"Inbound webhook from IP: {client_ip}")
```

You can add a proper IP allowlist later when hardening for production.

---

# PART 9: TESTING

### Step 14: Test Locally with cURL

Before connecting SendGrid, test the webhook locally by simulating what SendGrid would send.

**Where:** Terminal (PowerShell) — make sure your API is running first (`uvicorn app.main:app --reload`)

**Create a test file first** — save any `.docx` file as `test_job.docx` on your desktop.

Then run:

```powershell
curl -X POST http://127.0.0.1:8000/api/email-ingest/webhook `
  -F 'from="Test Recruiter <test@example.com>"' `
  -F 'subject=Senior Developer Position' `
  -F 'text=Please parse the attached job description.' `
  -F 'envelope={"to":["upload@jobs.winnowcc.ai"],"from":"test@example.com"}' `
  -F 'attachment-info={"attachment1":{"filename":"test_job.docx","type":"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}}' `
  -F 'attachment1=@C:\Users\ronle\Desktop\test_job.docx'
```

**Expected results:**

- If `test@example.com` is NOT a registered user → `{"status": "failed", "reason": "sender_not_registered"}`
- If `test@example.com` IS registered → `{"status": "draft_created", "job_id": "..."}`

### Step 15: Test with a Real Email via SendGrid

Once DNS has propagated and SendGrid Inbound Parse is configured:

1. Send an email from your registered Winnow email address to `upload@jobs.winnowcc.ai`.
2. Attach a `.docx` job description file.
3. Wait 30-60 seconds.
4. Check:
   - Did you receive a confirmation email?
   - Does a draft job appear in your employer dashboard?
   - Does the ingest log show the entry? (`GET /api/email-ingest/logs`)

---

## Complete File Summary

Here's every file created or modified, in the order you should do them:

| #  | Action   | File Path                                                    |
|----|----------|--------------------------------------------------------------|
| 1  | Browser  | Create SendGrid account (free) at signup.sendgrid.com        |
| 2  | Browser  | DNS: Add MX record `jobs.winnowcc.ai → mx.sendgrid.net`     |
| 3  | Browser  | SendGrid: Configure Inbound Parse for `jobs.winnowcc.ai`    |
| 4  | Terminal | `alembic revision -m "add_email_ingest_log"`                 |
| 5  | Edit     | `services/api/alembic/versions/XXXX_add_email_ingest_log.py` |
| 6  | Terminal | `alembic upgrade head`                                       |
| 7  | Create   | `services/api/app/models/email_ingest_log.py`                |
| 8  | Edit     | `services/api/app/models/__init__.py` (add import)           |
| 9  | Create   | `services/api/app/services/email_ingest.py`                  |
| 10 | Create   | `services/api/app/routers/email_ingest.py`                   |
| 11 | Edit     | `services/api/app/main.py` (add router)                      |
| 12 | Edit     | `services/api/.env` (add 1 env var)                          |
| 13 | Optional | IP allowlisting in router (production hardening)             |
| 14 | Terminal | Test with cURL locally                                       |
| 15 | Test     | Send real email to `upload@jobs.winnowcc.ai`                 |

---

## Testing Checklist

After implementation, verify:

- ✅ MX record resolves: `nslookup -type=MX jobs.winnowcc.ai` shows `mx.sendgrid.net`
- ✅ SendGrid Inbound Parse configured with correct webhook URL
- ✅ Database migration runs (`alembic upgrade head` succeeds)
- ✅ API starts without errors (`uvicorn app.main:app --reload`)
- ✅ Local cURL test returns expected response
- ✅ Registered sender + .docx → draft job created + confirmation email
- ✅ Unregistered sender → rejection email with signup link
- ✅ No attachment → reply requesting .docx/.pdf
- ✅ Parse failure → reply with troubleshooting tips
- ✅ Admin can view ingest logs at `GET /api/email-ingest/logs`
- ✅ File too large (>10MB) → rejected gracefully

---

## Success Criteria

- ✅ Recruiter emails a .docx to `upload@jobs.winnowcc.ai` → draft job appears in their dashboard
- ✅ Confirmation email sent within 60 seconds
- ✅ All parsing uses the unified PROMPT77 parser via `parse_job_from_file()` (no duplication)
- ✅ Unregistered senders get a helpful signup reply
- ✅ Admin monitoring via `GET /api/email-ingest/logs`
- ✅ Zero ongoing maintenance (no watch renewals, no Pub/Sub, no service accounts)

---

## Comparison: What Changed from the Gmail Version

| Item | Old (Gmail API) | New (SendGrid Inbound Parse) |
|------|----------------|------------------------------|
| Steps in this prompt | 23 | 15 |
| Browser setup steps | 7 (GCP Console + Admin) | 3 (SendGrid + DNS) |
| Python packages added | 3 | 0 |
| Environment variables | 4 | 1 |
| Files created | 6 | 3 |
| Recurring maintenance | Watch renewal every 7 days | None |
| Monthly cost | $7-14 (Workspace seat) + ~$0.40 (Pub/Sub) | $0 (SendGrid free tier) |
| Reply emails sent via | Gmail API (requires modify scope) | Resend (already configured) |

---

## Notes

- **Cost:** SendGrid free tier allows 100 inbound emails per day. That's 100 job submissions per day — more than enough for early-stage. Paid tiers start at $19.95/mo if you ever need more.
- **Subdomain isolation:** Using `jobs.winnowcc.ai` keeps ingest email completely separate from your main domain's email reputation. Spam or bounces on the ingest subdomain won't affect `winnowcc.ai` or `winnowcc.com` deliverability.
- **Reply emails:** Replies go through Resend (your existing transactional email service), NOT through SendGrid. This keeps outbound email on a single provider.
- **File types:** Supports `.docx`, `.pdf`, and `.doc`. The unified parser (PROMPT77) handles text extraction for all three.
- **Security layers:** (1) SendGrid only forwards emails to your webhook. (2) Your code only creates jobs for registered users. (3) Optional IP allowlisting blocks non-SendGrid traffic to the webhook.
- **Scaling:** If volume grows significantly, SendGrid handles the scaling — your webhook just processes each POST as it arrives. For very high volumes, enqueue to the RQ worker instead of processing synchronously.

---

**Status:** Ready for implementation
**Estimated Time:** 1-2 hours (down from 3-5 hours for the Gmail version)
**Dependencies:** PROMPT77 (Unified Job Parser), SendGrid free account, DNS access
**Required:** Anthropic API key (for job parsing via PROMPT77)

**Run in Cursor:**
```
Read PROMPT78_Email_Job_Upload.md and implement all steps. Read CLAUDE.md, AGENTS.md, and ARCHITECTURE.md first for context. Steps 1-3 are browser-based setup that I will do manually — start implementing from Step 4 (database migration) onward.
```
