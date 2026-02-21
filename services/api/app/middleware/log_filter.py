"""
PII redaction filter for Python logging.
Strips or masks sensitive data from log messages before they are emitted.
"""

import logging
import re

# Patterns to redact
PII_PATTERNS = [
    # Email addresses
    (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[EMAIL_REDACTED]",
    ),
    # Phone numbers (US and international)
    (
        re.compile(r"(\+?1?[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
        "[PHONE_REDACTED]",
    ),
    # SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    # JWT tokens (long base64 strings)
    (
        re.compile(
            r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"
            r"\.[A-Za-z0-9_-]{20,}"
        ),
        "[JWT_REDACTED]",
    ),
    # API keys (common patterns)
    (
        re.compile(r"sk[-_](?:test|live)[-_][A-Za-z0-9]{20,}"),
        "[STRIPE_KEY_REDACTED]",
    ),
    (
        re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        "[ANTHROPIC_KEY_REDACTED]",
    ),
    (
        re.compile(r"whsec_[A-Za-z0-9]{20,}"),
        "[WEBHOOK_SECRET_REDACTED]",
    ),
]

# Fields to redact entirely when they appear as keys in log messages
SENSITIVE_FIELD_NAMES = {
    "password",
    "password_hash",
    "token",
    "secret",
    "api_key",
    "extracted_text",
    "resume_text",
    "profile_json",
    "description_text",
    "cover_letter_text",
    "change_log",
}


class PIIRedactionFilter(logging.Filter):
    """Logging filter that redacts PII from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in PII_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        # Also redact args if they're strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: "[REDACTED]" if k.lower() in SENSITIVE_FIELD_NAMES else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(a) for a in record.args)

        return True

    def _redact_value(self, value):
        if isinstance(value, str):
            for pattern, replacement in PII_PATTERNS:
                value = pattern.sub(replacement, value)
        return value


def configure_safe_logging():
    """
    Configure Python logging with PII redaction.
    Call this once at application startup.
    """
    pii_filter = PIIRedactionFilter()

    # Apply to root logger so ALL log messages are filtered
    root_logger = logging.getLogger()
    root_logger.addFilter(pii_filter)

    # Also apply to uvicorn's access logger
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.addFilter(pii_filter)
