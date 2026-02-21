"""
Sentry SDK initialization for the Winnow API and worker.
Call init_sentry() once at application startup.
"""

import logging
import os
import re

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.rq import RqIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def init_sentry():
    """
    Initialize Sentry SDK if SENTRY_DSN is configured.
    Safe to call even if DSN is empty — it simply does nothing.
    """
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        logger.info("SENTRY_DSN not set — Sentry disabled")
        return

    environment = os.environ.get("SENTRY_ENVIRONMENT", "dev")
    traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            RqIntegration(),
            LoggingIntegration(
                level=logging.WARNING,
                event_level=logging.ERROR,
            ),
        ],
        send_default_pii=False,
        before_send=_scrub_event,
        release=os.environ.get("GIT_SHA", "unknown"),
    )

    logger.info(
        "Sentry initialized: env=%s, traces=%s", environment, traces_sample_rate
    )


_REDACT_KEYS = {
    "extracted_text",
    "profile_json",
    "resume_text",
    "description_text",
    "password",
    "password_hash",
}


def _scrub_event(event, hint):
    """
    Scrub PII from Sentry events before they leave the server.
    This runs AFTER the SDK's default scrubbing.
    """
    if "request" in event:
        request = event["request"]
        if "data" in request:
            if isinstance(request["data"], dict):
                for key in _REDACT_KEYS:
                    if key in request["data"]:
                        request["data"][key] = "[REDACTED]"
            elif isinstance(request["data"], str) and len(request["data"]) > 1000:
                request["data"] = f"[REDACTED: {len(request['data'])} chars]"

    if "exception" in event:
        for exc in event["exception"].get("values", []):
            value = exc.get("value", "")
            if isinstance(value, str) and "@" in value:
                exc["value"] = _EMAIL_RE.sub("[EMAIL_REDACTED]", value)

    return event
