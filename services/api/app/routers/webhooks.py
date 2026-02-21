"""Webhook receiver for board callbacks (P45)."""

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/board/{board_type}")
async def receive_board_webhook(
    board_type: str,
    request: Request,
    x_webhook_signature: str | None = Header(None),
) -> JSONResponse:
    """Receive webhook callbacks from job boards.

    Boards send notifications when a job's status changes on
    their side (expired, flagged, removed by moderation).

    No auth required — webhooks are verified by signature.
    """
    body = await request.body()

    # Verify signature if configured
    secret = os.environ.get(f"WEBHOOK_SECRET_{board_type.upper()}", "")
    if secret and x_webhook_signature:
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_webhook_signature):
            logger.warning("Invalid webhook signature for %s", board_type)
            return JSONResponse({"error": "Invalid signature"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    event_type = payload.get("event", "unknown")
    external_job_id = payload.get("job_id") or payload.get("external_id")

    if not external_job_id:
        return JSONResponse({"error": "Missing job_id"}, status_code=400)

    # Process the webhook
    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.distribution import (
        DistributionEvent,
        JobDistribution,
    )

    session = get_session_factory()()
    try:
        stmt = select(JobDistribution).where(
            JobDistribution.external_job_id == str(external_job_id),
        )
        dist = session.execute(stmt).scalar_one_or_none()

        if not dist:
            logger.info(
                "Webhook for unknown distribution: %s (%s)",
                external_job_id,
                board_type,
            )
            return JSONResponse({"status": "ignored"})

        # Map board event to distribution status
        status_map = {
            "expired": "expired",
            "removed": "removed",
            "flagged": "failed",
            "live": "live",
            "confirmed": "live",
            "pending": "pending",
        }
        new_status = status_map.get(event_type)
        if new_status:
            dist.status = new_status

        # Log event
        event = DistributionEvent(
            distribution_id=dist.id,
            event_type=f"webhook_{event_type}",
            event_data={
                "board_type": board_type,
                "payload": payload,
            },
        )
        session.add(event)
        session.commit()

        logger.info(
            "Processed %s webhook for dist %s: %s",
            board_type,
            dist.id,
            event_type,
        )
        return JSONResponse({"status": "processed"})

    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)
        session.rollback()
        return JSONResponse({"error": "Processing failed"}, status_code=500)
    finally:
        session.close()
