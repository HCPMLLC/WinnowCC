"""
Structured JSON logging for Cloud Run.
Outputs logs as JSON objects that Cloud Logging automatically parses.
Includes request context (trace ID, user ID, method, path, status, latency).
"""

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for Cloud Logging.
    Cloud Logging recognizes these fields:
    - severity: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - message: The log message
    - timestamp: ISO 8601 timestamp
    - logging.googleapis.com/trace: Trace ID for correlating logs
    """

    SEVERITY_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": self.SEVERITY_MAP.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "timestamp": datetime.now(UTC).isoformat(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in (
            "trace_id",
            "user_id",
            "method",
            "path",
            "status_code",
            "latency_ms",
            "worker_job",
            "queue_name",
            "job_id",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log every request/response with structured fields.
    Adds: method, path, status_code, latency_ms, user_id, trace_id.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # Extract trace ID from Cloud Run header (for log correlation)
        trace_header = request.headers.get("x-cloud-trace-context", "")
        trace_id = trace_header.split("/")[0] if trace_header else ""

        # Extract user ID from cookie (best-effort)
        user_id = None
        cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
        token = request.cookies.get(cookie_name)
        if token:
            try:
                from app.services.auth import decode_token

                payload = decode_token(token)
                user_id = payload.get("sub") or payload.get("user_id")
            except Exception:
                pass

        try:
            response = await call_next(request)
        except Exception:
            from starlette.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        latency_ms = round((time.time() - start_time) * 1000, 1)

        # Build the GCP trace resource name for log correlation
        project_id = os.environ.get("GCP_PROJECT_ID", "")
        trace_resource = (
            f"projects/{project_id}/traces/{trace_id}"
            if project_id and trace_id
            else ""
        )

        access_logger = logging.getLogger("winnow.access")
        access_logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "user_id": user_id,
                "trace_id": trace_id,
                "logging.googleapis.com/trace": trace_resource,
            },
        )

        return response


def configure_structured_logging():
    """
    Configure Python logging with JSON output for production,
    or human-readable output for local development.
    Call ONCE at application startup, AFTER configure_safe_logging().
    """
    env = os.environ.get("ENV", "dev")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    if env != "dev":
        # Production: JSON to stdout (Cloud Logging picks this up)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
    else:
        # Dev: human-readable format
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root_logger.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
