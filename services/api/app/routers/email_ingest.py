"""Email Ingest Webhook Router — receives parsed emails from SendGrid Inbound Parse.

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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.email_ingest_log import EmailIngestLog
from app.services.auth import get_current_user
from app.services.email_ingest import (
    ALLOWED_EXTENSIONS,
    extract_email_address,
    process_inbound_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email-ingest", tags=["email-ingest"])


@router.post("/webhook")
async def sendgrid_inbound_webhook(
    request: Request, db: Session = Depends(get_session)
):
    """Receives inbound emails from SendGrid Inbound Parse.

    SendGrid POSTs multipart/form-data with email fields and attachments.
    This endpoint does NOT require authentication — SendGrid cannot send auth
    headers. Security is handled via:
      1. Only processing emails from registered Winnow users
      2. Optional: IP allowlisting for SendGrid's IP ranges
    """
    # Log source IP for monitoring / future IP allowlisting
    client_ip = request.client.host if request.client else "unknown"
    logger.debug("Inbound webhook from IP: %s", client_ip)

    try:
        form = await request.form()
    except Exception as e:
        logger.error("Failed to parse form data: %s", e)
        raise HTTPException(status_code=400, detail="Invalid form data") from e

    # ── Extract email fields from SendGrid's POST ────────────────────────
    from_field = form.get("from", "")
    subject = form.get("subject", "")
    envelope_raw = form.get("envelope", "{}")
    attachment_info_raw = form.get("attachment-info", "{}")

    # Parse sender email from the 'from' field
    sender_email, sender_name = extract_email_address(from_field)

    if not sender_email:
        logger.warning("Received inbound email with no sender")
        return {"status": "ignored", "reason": "no_sender"}

    logger.info("Inbound email from %s: %s", sender_email, subject)

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
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        else:
            ext = ""

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
            metadata_={"from": from_field, "attachment_info": attachment_info_raw},
        )
        db.add(log_entry)
        db.commit()

        from app.services.email_ingest import _send_no_attachment_reply

        _send_no_attachment_reply(sender_email, subject)

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
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_session),
):
    """Admin endpoint: View email ingest log entries.

    Useful for monitoring and debugging the email ingest pipeline.
    """
    if (
        not getattr(current_user, "is_admin", False)
        and getattr(current_user, "role", "") != "admin"
    ):
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
                "id": log.id,
                "sender_email": log.sender_email,
                "sender_name": log.sender_name,
                "subject": log.subject,
                "status": log.status,
                "status_detail": log.status_detail,
                "attachment_filename": log.attachment_filename,
                "attachment_size_bytes": log.attachment_size_bytes,
                "parsing_confidence": log.parsing_confidence,
                "created_job_id": log.created_job_id,
                "received_at": (
                    log.received_at.isoformat() if log.received_at else None
                ),
                "processed_at": (
                    log.processed_at.isoformat() if log.processed_at else None
                ),
            }
            for log in logs
        ],
    }
