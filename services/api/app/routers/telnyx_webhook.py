"""Inbound SMS webhook for Telnyx (STOP / HELP auto-responses)."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import get_session_factory
from app.services.sms_service import send_help_response, send_stop_confirmation

router = APIRouter(prefix="/api/webhooks/telnyx", tags=["telnyx-webhook"])
logger = logging.getLogger(__name__)


@router.post("/inbound")
async def telnyx_inbound(request: Request) -> JSONResponse:
    """Receive inbound SMS from Telnyx and auto-respond to STOP / HELP."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Telnyx wraps the event in data.payload
    data = payload.get("data", {})
    event_type = data.get("event_type", "")

    # We only care about inbound messages
    if event_type != "message.received":
        return JSONResponse({"status": "ignored"})

    msg_payload = data.get("payload", {})
    from_number = msg_payload.get("from", {}).get("phone_number", "")
    body = (msg_payload.get("text", "") or "").strip().upper()

    if not from_number:
        return JSONResponse({"error": "Missing from number"}, status_code=400)

    if body in ("STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"):
        _revoke_sms_consent(from_number)
        send_stop_confirmation(from_number)
        logger.info("STOP processed for %s", from_number)
        return JSONResponse({"status": "stop_processed"})

    if body in ("HELP", "INFO"):
        send_help_response(from_number)
        logger.info("HELP processed for %s", from_number)
        return JSONResponse({"status": "help_processed"})

    # Any other inbound message — acknowledge but ignore
    return JSONResponse({"status": "ignored"})


def _revoke_sms_consent(phone_e164: str) -> None:
    """Revoke SMS consent for any user matching this phone number."""
    session = get_session_factory()()
    try:
        # Find user by phone
        row = session.execute(
            text("SELECT id FROM users WHERE phone = :phone LIMIT 1"),
            {"phone": phone_e164},
        ).first()

        if not row:
            logger.warning("STOP from unknown number %s — no user found", phone_e164)
            return

        user_id = row[0]

        # Revoke consent
        session.execute(
            text(
                """
                UPDATE consents
                SET sms_consent = false, sms_consent_at = NULL
                WHERE user_id = :uid AND active = true
                """
            ),
            {"uid": user_id},
        )
        session.commit()
        logger.info("SMS consent revoked for user %s via STOP", user_id)

    except Exception as e:
        logger.exception("Failed to revoke SMS consent for %s: %s", phone_e164, e)
        session.rollback()
    finally:
        session.close()
