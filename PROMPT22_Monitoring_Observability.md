# PROMPT22_Monitoring_Observability.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Implement production-grade monitoring and observability for the Winnow platform. Per ARCHITECTURE §6: "Error tracking: Sentry (web + api). Structured logging with PII redaction. Health endpoints: /health basic, /ready checks DB connection." This prompt adds Sentry error tracking for both API and web, structured JSON logging, GCP Cloud Monitoring dashboards and alerting, worker queue health tracking, uptime checks, and an admin observability endpoint.

---

## Triggers — When to Use This Prompt

- Integrating Sentry for error and performance tracking.
- Setting up structured logging for production Cloud Run.
- Creating GCP Cloud Monitoring dashboards or alert policies.
- Adding worker health/queue depth monitoring.
- Adding uptime checks for production endpoints.

---

## What Already Exists (DO NOT recreate)

1. **Health endpoints:** `/health` (returns `{"status": "ok"}`) and `/ready` (checks DB connection) already exist in `services/api/app/main.py`.
2. **PII log redaction:** `services/api/app/middleware/log_filter.py` — `PIIRedactionFilter` + `configure_safe_logging()` from PROMPT21. Already registered in `main.py`.
3. **Main app:** `services/api/app/main.py` — FastAPI app with middleware registrations (CORS, security headers, rate limiter from PROMPT21).
4. **Worker:** `services/api/app/worker.py` — RQ-based worker processes jobs from Redis queues.
5. **Queue service:** `services/api/app/services/queue.py` — RQ job queue wrapper for enqueuing background jobs.
6. **Cloud Run deployment:** Three services deployed — `winnow-api`, `winnow-worker`, `winnow-web` (from PROMPT16).
7. **CI/CD:** `.github/workflows/ci.yml` and `.github/workflows/deploy.yml` (from PROMPT16).
8. **Next.js config:** `apps/web/next.config.js` — already has security headers and `output: 'standalone'`.
9. **Environment vars:** `services/api/.env` and `apps/web/.env.local` with existing config.

---

## What to Build

This prompt covers 7 observability domains. Each is independent — implement in order but each stands alone.

---

# PART 1 — SENTRY: PYTHON API + WORKER

Sentry captures unhandled exceptions, performance traces, and lets you see errors in real time with full stack traces and request context.

### 1.1 Install dependency

**File to modify:** `services/api/requirements.txt`

Add:
```
sentry-sdk[fastapi]>=2.0.0
```

Then install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install "sentry-sdk[fastapi]"
```

### 1.2 Add environment variables

**File to modify:** `services/api/.env`

Add:
```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=dev
SENTRY_TRACES_SAMPLE_RATE=0.1
```

**File to modify:** `services/api/.env.example`

Add:
```env
# Sentry (error tracking)
SENTRY_DSN=https://YOUR_KEY@YOUR_ORG.ingest.sentry.io/YOUR_PROJECT_ID
SENTRY_ENVIRONMENT=dev
SENTRY_TRACES_SAMPLE_RATE=0.1
```

You will get the actual `SENTRY_DSN` value from the Sentry dashboard after creating your project (see Part 1.7).

### 1.3 Create Sentry initialization module

**File to create:** `services/api/app/services/sentry_init.py` (NEW)

```python
"""
Sentry SDK initialization for the Winnow API and worker.
Call init_sentry() once at application startup.
"""
import os
import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.rq import RqIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)


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

        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            RqIntegration(),
            LoggingIntegration(
                level=logging.WARNING,       # Capture WARNING+ as breadcrumbs
                event_level=logging.ERROR,   # Send ERROR+ as Sentry events
            ),
        ],

        # PII scrubbing — strip sensitive data before sending to Sentry
        send_default_pii=False,  # Do NOT send cookies, auth headers, user IPs

        # Custom before_send hook for additional PII scrubbing
        before_send=_scrub_event,

        # Release tracking (use git commit SHA if available)
        release=os.environ.get("GIT_SHA", "unknown"),
    )

    logger.info(f"Sentry initialized: env={environment}, traces={traces_sample_rate}")


def _scrub_event(event, hint):
    """
    Scrub PII from Sentry events before they leave the server.
    This runs AFTER the SDK's default scrubbing.
    """
    # Remove request body (may contain resume text, profile JSON, etc.)
    if "request" in event:
        request = event["request"]
        if "data" in request:
            content_type = request.get("headers", {}).get("content-type", "")
            # Keep JSON structure but redact values for large payloads
            if isinstance(request["data"], dict):
                for key in ("extracted_text", "profile_json", "resume_text",
                            "description_text", "password", "password_hash"):
                    if key in request["data"]:
                        request["data"][key] = "[REDACTED]"
            elif isinstance(request["data"], str) and len(request["data"]) > 1000:
                request["data"] = f"[REDACTED: {len(request['data'])} chars]"

    # Scrub any exception messages that might contain PII
    if "exception" in event:
        for exc in event["exception"].get("values", []):
            value = exc.get("value", "")
            if isinstance(value, str) and "@" in value:
                # Likely contains an email — redact it
                import re
                exc["value"] = re.sub(
                    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                    '[EMAIL_REDACTED]',
                    value,
                )

    return event
```

### 1.4 Initialize Sentry at API startup

**File to modify:** `services/api/app/main.py`

Add near the top, BEFORE the FastAPI app is created, AFTER `load_dotenv`:

```python
from app.services.sentry_init import init_sentry
init_sentry()
```

**Why before `FastAPI()`?** The Sentry FastAPI integration needs to be active before the app processes any requests. Initializing early ensures all middleware and routes are instrumented.

### 1.5 Initialize Sentry in the worker

**File to modify:** `services/api/app/worker.py`

Add near the top, before the worker starts processing jobs:

```python
from app.services.sentry_init import init_sentry
init_sentry()
```

This captures errors in background jobs (resume parsing, matching, tailoring, etc.).

### 1.6 Add Sentry user context to requests

**File to create:** `services/api/app/middleware/sentry_context.py` (NEW)

```python
"""
Middleware to set Sentry user context on each request.
Allows Sentry to group errors by user and show which users are affected.
"""
import os
import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SentryUserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Try to extract user ID from JWT cookie (without failing)
        cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
        token = request.cookies.get(cookie_name)

        if token:
            try:
                from app.services.auth import decode_jwt
                payload = decode_jwt(token)
                user_id = payload.get("sub") or payload.get("user_id")
                if user_id:
                    sentry_sdk.set_user({"id": str(user_id)})
            except Exception:
                pass  # Don't fail the request over Sentry context

        response = await call_next(request)

        # Clear user context after request
        sentry_sdk.set_user(None)

        return response
```

**File to modify:** `services/api/app/main.py`

Register the middleware (add AFTER the SecurityHeadersMiddleware):

```python
from app.middleware.sentry_context import SentryUserContextMiddleware

app.add_middleware(SentryUserContextMiddleware)
```

### 1.7 Create Sentry project (one-time setup in browser)

These steps are performed in the Sentry web dashboard at https://sentry.io (or your self-hosted Sentry instance):

1. Go to https://sentry.io and create an account (if you haven't already).
2. Create an **Organization** (e.g., "Winnow").
3. Create a **Project** — choose platform **Python** → **FastAPI**. Name it `winnow-api`.
4. Copy the **DSN** (looks like `https://abc123@o123.ingest.sentry.io/456`).
5. Paste the DSN into `services/api/.env` as `SENTRY_DSN`.
6. Create a second project — platform **JavaScript** → **Next.js**. Name it `winnow-web`.
7. Copy that DSN for Part 2 below.

---

# PART 2 — SENTRY: NEXT.JS FRONTEND

### 2.1 Install dependency

```powershell
cd apps/web
npm install @sentry/nextjs
```

### 2.2 Initialize Sentry for Next.js

Run the Sentry wizard (it creates the config files for you):

```powershell
cd apps/web
npx @sentry/wizard@latest -i nextjs
```

The wizard will ask for your auth token and project — follow the prompts. It creates these files:

- `apps/web/sentry.client.config.ts`
- `apps/web/sentry.server.config.ts`
- `apps/web/sentry.edge.config.ts`
- Updates `apps/web/next.config.js` to wrap with `withSentryConfig`

### 2.3 If the wizard doesn't work, create configs manually

**File to create:** `apps/web/sentry.client.config.ts` (NEW)

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "dev",

  // Performance monitoring
  tracesSampleRate: 0.1,

  // Session replay (optional — captures user sessions on error)
  replaysSessionSampleRate: 0,    // Don't record normal sessions
  replaysOnErrorSampleRate: 0.1,  // Record 10% of sessions with errors

  // Don't send PII
  sendDefaultPii: false,
});
```

**File to create:** `apps/web/sentry.server.config.ts` (NEW)

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "dev",
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});
```

**File to create:** `apps/web/sentry.edge.config.ts` (NEW)

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN || "",
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || "dev",
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});
```

### 2.4 Wrap Next.js config

**File to modify:** `apps/web/next.config.js`

Wrap the existing config with Sentry:

```javascript
const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // ... existing headers() and other config from PROMPT21
};

module.exports = withSentryConfig(nextConfig, {
  // Sentry build options
  silent: true,            // Suppress source map upload logs during build
  hideSourceMaps: true,    // Don't expose source maps publicly
  disableLogger: true,     // Disable Sentry's debug logger
});
```

### 2.5 Add environment variables

**File to modify:** `apps/web/.env.local`

Add:
```env
NEXT_PUBLIC_SENTRY_DSN=https://YOUR_KEY@YOUR_ORG.ingest.sentry.io/YOUR_WEB_PROJECT_ID
NEXT_PUBLIC_SENTRY_ENVIRONMENT=dev
```

### 2.6 Create a global error boundary page

**File to create:** `apps/web/app/global-error.tsx` (NEW)

```tsx
"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <div style={{ padding: "2rem", textAlign: "center" }}>
          <h2>Something went wrong</h2>
          <p>We&apos;ve been notified and are looking into it.</p>
          <button
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
```

---

# PART 3 — STRUCTURED JSON LOGGING

Cloud Run pipes stdout/stderr to Cloud Logging. Structured JSON logs are automatically parsed by Cloud Logging and become searchable/filterable.

### 3.1 Create structured logging configuration

**File to create:** `services/api/app/middleware/structured_logging.py` (NEW)

```python
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
from datetime import datetime, timezone

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

    # Map Python log levels to Cloud Logging severity
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields (request context, etc.)
        for key in ("trace_id", "user_id", "method", "path",
                     "status_code", "latency_ms", "worker_job",
                     "queue_name", "job_id"):
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
                from app.services.auth import decode_jwt
                payload = decode_jwt(token)
                user_id = payload.get("sub") or payload.get("user_id")
            except Exception:
                pass

        response = await call_next(request)

        latency_ms = round((time.time() - start_time) * 1000, 1)

        # Build the GCP trace resource name for log correlation
        project_id = os.environ.get("GCP_PROJECT_ID", "")
        trace_resource = (
            f"projects/{project_id}/traces/{trace_id}"
            if project_id and trace_id
            else ""
        )

        logger = logging.getLogger("winnow.access")
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} ({latency_ms}ms)",
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
```

### 3.2 Register structured logging at startup

**File to modify:** `services/api/app/main.py`

Add AFTER `configure_safe_logging()` and AFTER `init_sentry()`:

```python
from app.middleware.structured_logging import (
    configure_structured_logging,
    RequestLoggingMiddleware,
)

configure_structured_logging()

# After app = FastAPI(...):
app.add_middleware(RequestLoggingMiddleware)
```

### 3.3 Worker structured logging

**File to modify:** `services/api/app/worker.py`

Add at the top, before the worker starts:

```python
from app.middleware.structured_logging import configure_structured_logging
from app.middleware.log_filter import configure_safe_logging

configure_safe_logging()
configure_structured_logging()
```

Also add structured logging to worker job functions. Wherever a worker job logs something, include `extra` fields:

```python
import logging

logger = logging.getLogger("winnow.worker")

def run_parse_job(resume_document_id: int, user_id: int):
    logger.info(
        f"Starting resume parse job",
        extra={
            "worker_job": "parse_resume",
            "job_id": str(resume_document_id),
            "user_id": str(user_id),
        },
    )
    # ... existing parse logic ...
    logger.info(
        f"Resume parse complete",
        extra={
            "worker_job": "parse_resume",
            "job_id": str(resume_document_id),
            "user_id": str(user_id),
        },
    )
```

---

# PART 4 — WORKER HEALTH + QUEUE DEPTH MONITORING

Track the health of the RQ worker and the depth of each queue.

### 4.1 Create worker health service

**File to create:** `services/api/app/services/worker_health.py` (NEW)

```python
"""
Worker health and queue depth monitoring.
Provides queue stats for the admin dashboard and alerting.
"""
import os
import logging
from datetime import datetime, timezone

import redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)

# Queue names used by Winnow (must match what queue.py uses)
QUEUE_NAMES = [
    "default",
    "parse",
    "match",
    "tailor",
    "embed",
    "ingest",
]


def get_redis_connection():
    """Get the Redis connection used by RQ."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


def get_queue_stats() -> dict:
    """
    Return stats for each RQ queue.

    Returns dict like:
    {
        "queues": [
            {
                "name": "default",
                "pending": 5,
                "started": 1,
                "failed": 0,
                "deferred": 0,
            },
            ...
        ],
        "total_pending": 12,
        "total_failed": 2,
        "redis_connected": true,
        "checked_at": "2026-02-08T..."
    }
    """
    try:
        conn = get_redis_connection()
        conn.ping()  # Verify connection
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        return {
            "queues": [],
            "total_pending": -1,
            "total_failed": -1,
            "redis_connected": False,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }

    queues_data = []
    total_pending = 0
    total_failed = 0

    for name in QUEUE_NAMES:
        try:
            q = Queue(name, connection=conn)
            pending = q.count
            started = q.started_job_registry.count
            failed = q.failed_job_registry.count
            deferred = q.deferred_job_registry.count

            queues_data.append({
                "name": name,
                "pending": pending,
                "started": started,
                "failed": failed,
                "deferred": deferred,
            })

            total_pending += pending
            total_failed += failed
        except Exception as e:
            queues_data.append({
                "name": name,
                "error": str(e),
            })

    return {
        "queues": queues_data,
        "total_pending": total_pending,
        "total_failed": total_failed,
        "redis_connected": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_failed_jobs(queue_name: str = "default", limit: int = 20) -> list[dict]:
    """
    Return recent failed jobs for a queue.
    Useful for the admin dashboard to see what's breaking.
    """
    try:
        conn = get_redis_connection()
        q = Queue(queue_name, connection=conn)
        failed_registry = q.failed_job_registry
        job_ids = failed_registry.get_job_ids(0, limit)

        failed = []
        for job_id in job_ids:
            try:
                job = Job.fetch(job_id, connection=conn)
                failed.append({
                    "job_id": job_id,
                    "func_name": job.func_name if job.func_name else "unknown",
                    "enqueued_at": str(job.enqueued_at) if job.enqueued_at else None,
                    "ended_at": str(job.ended_at) if job.ended_at else None,
                    "exc_info": str(job.exc_info)[:500] if job.exc_info else None,
                })
            except Exception:
                failed.append({"job_id": job_id, "error": "Could not fetch job details"})

        return failed
    except Exception as e:
        return [{"error": str(e)}]
```

### 4.2 Create admin observability endpoint

**File to create:** `services/api/app/routers/observability.py` (NEW)

```python
"""
Admin observability endpoints.
Provides queue stats, failed jobs, and system health overview.
"""
import os
import logging
import platform
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.session import get_db
from app.services.worker_health import get_queue_stats, get_failed_jobs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/observability", tags=["admin-observability"])


def _verify_admin(admin_token: str = Query(..., alias="admin_token")):
    """Verify admin access via token."""
    expected = os.environ.get("ADMIN_TOKEN", "")
    if admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health")
async def system_health(
    _=Depends(_verify_admin),
    db: Session = Depends(get_db),
):
    """
    Comprehensive system health check.
    Returns status of: API, database, Redis, and queue depths.
    """
    health = {
        "api": {"status": "ok"},
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    # Database check
    try:
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        health["database"] = {"status": "ok"}
    except Exception as e:
        health["database"] = {"status": "error", "detail": str(e)[:200]}

    # Redis + queue stats
    queue_stats = get_queue_stats()
    health["redis"] = {
        "status": "ok" if queue_stats["redis_connected"] else "error",
    }
    health["queues"] = queue_stats

    # System info
    health["system"] = {
        "python_version": platform.python_version(),
        "environment": os.environ.get("ENV", "dev"),
    }

    return health


@router.get("/queues")
async def queue_overview(_=Depends(_verify_admin)):
    """Return queue depths and stats for all RQ queues."""
    return get_queue_stats()


@router.get("/queues/{queue_name}/failed")
async def failed_jobs(
    queue_name: str,
    limit: int = Query(default=20, le=100),
    _=Depends(_verify_admin),
):
    """Return recent failed jobs for a specific queue."""
    return get_failed_jobs(queue_name, limit)


@router.post("/queues/{queue_name}/retry-all")
async def retry_failed_jobs(
    queue_name: str,
    _=Depends(_verify_admin),
):
    """
    Retry all failed jobs in a queue.
    Moves them from the failed registry back to the queue.
    """
    from rq import Queue
    from app.services.worker_health import get_redis_connection

    try:
        conn = get_redis_connection()
        q = Queue(queue_name, connection=conn)
        failed_registry = q.failed_job_registry
        job_ids = failed_registry.get_job_ids()
        retried = 0

        for job_id in job_ids:
            try:
                failed_registry.requeue(job_id)
                retried += 1
            except Exception:
                pass

        return {"queue": queue_name, "retried": retried, "total_failed": len(job_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4.3 Register the observability router

**File to modify:** `services/api/app/main.py`

```python
from app.routers import observability

app.include_router(observability.router)
```

---

# PART 5 — ENHANCED HEALTH ENDPOINTS

Improve the existing `/health` and `/ready` endpoints with more detail.

### 5.1 Upgrade health endpoint

**File to modify:** `services/api/app/main.py`

Replace or enhance the existing `/health` and `/ready` handlers:

```python
import time
from datetime import datetime, timezone

_app_start_time = time.time()


@app.get("/health")
async def health():
    """Basic liveness probe. Always returns ok if the process is running."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _app_start_time),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
async def ready(db: Session = Depends(get_db)):
    """
    Readiness probe. Checks database connectivity.
    Cloud Run uses this to determine if the instance can receive traffic.
    """
    checks = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"

    # Redis
    try:
        from app.services.worker_health import get_redis_connection
        conn = get_redis_connection()
        conn.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"

    all_ok = all(v == "ok" for v in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

# PART 6 — GCP CLOUD MONITORING: DASHBOARDS + ALERTS

Configure monitoring in GCP Console. These are manual steps — no code.

### 6.1 Create a Cloud Monitoring Dashboard

Go to **GCP Console** → **Monitoring** → **Dashboards** → **Create Dashboard**.

Name it: **Winnow Production Overview**

Add these widgets:

**Widget 1 — Cloud Run Request Count (API)**
- Resource: Cloud Run Revision → `winnow-api`
- Metric: `run.googleapis.com/request_count`
- Group by: `response_code_class` (shows 2xx, 4xx, 5xx breakdown)
- Chart type: Stacked bar

**Widget 2 — Cloud Run Request Latency (API)**
- Resource: Cloud Run Revision → `winnow-api`
- Metric: `run.googleapis.com/request_latencies`
- Aggregation: 50th percentile (p50) and 99th percentile (p99)
- Chart type: Line

**Widget 3 — Cloud Run Instance Count**
- Resource: Cloud Run Revision → `winnow-api`
- Metric: `run.googleapis.com/container/instance_count`
- Chart type: Line (shows scaling)

**Widget 4 — Cloud Run CPU + Memory (API)**
- Resource: Cloud Run Revision → `winnow-api`
- Metric: `run.googleapis.com/container/cpu/utilizations` (CPU)
- Metric: `run.googleapis.com/container/memory/utilizations` (Memory)
- Chart type: Line (dual-axis)

**Widget 5 — Cloud Run Request Count (Worker)**
- Same as Widget 1 but for `winnow-worker`

**Widget 6 — Cloud SQL CPU + Memory**
- Resource: Cloud SQL → `winnow-db`
- Metric: `cloudsql.googleapis.com/database/cpu/utilization`
- Metric: `cloudsql.googleapis.com/database/memory/utilization`
- Chart type: Line

**Widget 7 — Cloud SQL Connections**
- Metric: `cloudsql.googleapis.com/database/network/connections`
- Chart type: Line (watch for connection exhaustion)

**Widget 8 — Cloud SQL Disk Usage**
- Metric: `cloudsql.googleapis.com/database/disk/bytes_used`
- Chart type: Line

### 6.2 Create Alert Policies

Go to **GCP Console** → **Monitoring** → **Alerting** → **Create Policy**.

**Alert 1 — High Error Rate (API 5xx)**
- Condition: `run.googleapis.com/request_count` filtered by `response_code_class = 5xx` on `winnow-api`
- Threshold: > 10 errors in 5 minutes
- Notification: Email (your email)
- Documentation: "High error rate on winnow-api. Check Sentry for details and Cloud Run logs."

**Alert 2 — High Latency (API p99)**
- Condition: `run.googleapis.com/request_latencies` 99th percentile on `winnow-api`
- Threshold: > 10,000 ms (10 seconds)
- Window: 5 minutes
- Notification: Email

**Alert 3 — Cloud SQL CPU Spike**
- Condition: `cloudsql.googleapis.com/database/cpu/utilization` on `winnow-db`
- Threshold: > 80% for 10 minutes
- Notification: Email

**Alert 4 — Cloud SQL Connection Exhaustion**
- Condition: `cloudsql.googleapis.com/database/network/connections` on `winnow-db`
- Threshold: > 90 (db-f1-micro has ~100 max)
- Notification: Email

**Alert 5 — Cloud SQL Disk Full Warning**
- Condition: `cloudsql.googleapis.com/database/disk/bytes_used` on `winnow-db`
- Threshold: > 8 GB (of 10 GB provisioned)
- Notification: Email

### 6.3 Create Uptime Checks

Go to **GCP Console** → **Monitoring** → **Uptime checks** → **Create Uptime Check**.

**Check 1 — API Health**
- Protocol: HTTPS
- Host: Your API Cloud Run URL (e.g., `winnow-api-xxxxx-uc.a.run.app`)
- Path: `/health`
- Check frequency: Every 5 minutes
- Response match: Body contains `"status": "ok"`
- Alert on failure: Email

**Check 2 — API Readiness**
- Same host
- Path: `/ready`
- Check frequency: Every 5 minutes
- Response match: Body contains `"status"`

**Check 3 — Web App**
- Host: Your web Cloud Run URL
- Path: `/`
- Check frequency: Every 5 minutes
- Response: HTTP 200

---

# PART 7 — PRODUCTION DEPLOYMENT: ENV VARS + SECRETS

### 7.1 Add Sentry DSN to Secret Manager

```powershell
echo -n "https://YOUR_KEY@o123.ingest.sentry.io/456" | gcloud secrets create SENTRY_DSN --data-file=-
```

### 7.2 Update Cloud Run API deployment

```powershell
gcloud run services update winnow-api `
  --set-secrets="SENTRY_DSN=SENTRY_DSN:latest" `
  --update-env-vars="SENTRY_ENVIRONMENT=production,SENTRY_TRACES_SAMPLE_RATE=0.1,ENV=production,GCP_PROJECT_ID=YOUR_PROJECT_ID"
```

### 7.3 Update Cloud Run Worker deployment

```powershell
gcloud run services update winnow-worker `
  --set-secrets="SENTRY_DSN=SENTRY_DSN:latest" `
  --update-env-vars="SENTRY_ENVIRONMENT=production,SENTRY_TRACES_SAMPLE_RATE=0.2,ENV=production"
```

### 7.4 Update Web build args

```powershell
docker build `
  --build-arg NEXT_PUBLIC_SENTRY_DSN=https://YOUR_WEB_KEY@o123.ingest.sentry.io/789 `
  --build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT=production `
  -t winnow-web .
```

### 7.5 Update deploy workflow

**File to modify:** `.github/workflows/deploy.yml`

Add the Sentry auth token for source map uploads:

```yaml
env:
  SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
```

Add to GitHub Secrets:

| Secret Name | Value |
|-------------|-------|
| `SENTRY_AUTH_TOKEN` | Get from Sentry → Settings → Auth Tokens |

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Sentry init module | `services/api/app/services/sentry_init.py` | CREATE |
| Sentry user context middleware | `services/api/app/middleware/sentry_context.py` | CREATE |
| Structured logging config | `services/api/app/middleware/structured_logging.py` | CREATE |
| Worker health service | `services/api/app/services/worker_health.py` | CREATE |
| Observability router | `services/api/app/routers/observability.py` | CREATE |
| Main app (register all) | `services/api/app/main.py` | MODIFY |
| Worker (add Sentry + logging) | `services/api/app/worker.py` | MODIFY |
| Health/ready endpoints | `services/api/app/main.py` | MODIFY |
| Sentry client config | `apps/web/sentry.client.config.ts` | CREATE |
| Sentry server config | `apps/web/sentry.server.config.ts` | CREATE |
| Sentry edge config | `apps/web/sentry.edge.config.ts` | CREATE |
| Global error boundary | `apps/web/app/global-error.tsx` | CREATE |
| Next.js config (Sentry wrap) | `apps/web/next.config.js` | MODIFY |
| Requirements.txt | `services/api/requirements.txt` | MODIFY — add `sentry-sdk[fastapi]` |
| API .env + .env.example | `services/api/.env`, `.env.example` | MODIFY |
| Web .env.local | `apps/web/.env.local` | MODIFY |
| Deploy workflow | `.github/workflows/deploy.yml` | MODIFY |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Sentry Setup (Steps 1–4)

1. **Step 1:** Go to https://sentry.io. Create an account and organization. Create two projects: `winnow-api` (Python/FastAPI) and `winnow-web` (JavaScript/Next.js). Copy both DSNs.
2. **Step 2:** Add `sentry-sdk[fastapi]>=2.0.0` to `services/api/requirements.txt`. Install:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   pip install "sentry-sdk[fastapi]"
   ```
3. **Step 3:** Add Sentry env vars to `services/api/.env` and `services/api/.env.example` (Part 1.2). Paste your API DSN.
4. **Step 4:** Create `services/api/app/services/sentry_init.py` (Part 1.3).

### Phase 2: API + Worker Integration (Steps 5–8)

5. **Step 5:** Open `services/api/app/main.py`. Add `init_sentry()` call near the top (Part 1.4).
6. **Step 6:** Create `services/api/app/middleware/sentry_context.py` (Part 1.6). Register it in `main.py`.
7. **Step 7:** Open `services/api/app/worker.py`. Add `init_sentry()` call near the top (Part 1.5).
8. **Step 8:** Test Sentry — add a test route temporarily:
   ```python
   @app.get("/debug-sentry")
   async def trigger_error():
       raise ValueError("Test Sentry error")
   ```
   Hit `http://localhost:8000/debug-sentry`. Check Sentry dashboard — the error should appear within 30 seconds. Delete the test route after confirming.

### Phase 3: Frontend Sentry (Steps 9–12)

9. **Step 9:** Install Sentry for Next.js:
   ```powershell
   cd apps/web
   npm install @sentry/nextjs
   ```
10. **Step 10:** Create `sentry.client.config.ts`, `sentry.server.config.ts`, and `sentry.edge.config.ts` (Part 2.3).
11. **Step 11:** Wrap `next.config.js` with `withSentryConfig` (Part 2.4).
12. **Step 12:** Create `apps/web/app/global-error.tsx` (Part 2.6). Add `NEXT_PUBLIC_SENTRY_DSN` to `apps/web/.env.local`.

### Phase 4: Structured Logging (Steps 13–15)

13. **Step 13:** Create `services/api/app/middleware/structured_logging.py` (Part 3.1).
14. **Step 14:** Register `configure_structured_logging()` and `RequestLoggingMiddleware` in `services/api/app/main.py` (Part 3.2).
15. **Step 15:** Add logging setup to `services/api/app/worker.py` (Part 3.3).

### Phase 5: Worker Health + Observability (Steps 16–18)

16. **Step 16:** Create `services/api/app/services/worker_health.py` (Part 4.1).
17. **Step 17:** Create `services/api/app/routers/observability.py` (Part 4.2). Register in `main.py` (Part 4.3).
18. **Step 18:** Enhance `/health` and `/ready` endpoints (Part 5.1).

### Phase 6: Test Locally (Steps 19–21)

19. **Step 19:** Start the API:
    ```powershell
    cd services/api
    .\.venv\Scripts\Activate.ps1
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
20. **Step 20:** Test observability endpoints:
    ```powershell
    # Health
    curl http://localhost:8000/health

    # Ready
    curl http://localhost:8000/ready

    # Queue stats (admin)
    curl "http://localhost:8000/api/admin/observability/health?admin_token=dev-admin-token"

    # Queue overview
    curl "http://localhost:8000/api/admin/observability/queues?admin_token=dev-admin-token"
    ```
21. **Step 21:** Verify structured logging — check the terminal output. In dev mode you should see human-readable logs. Set `ENV=production` temporarily and restart — you should see JSON logs.

### Phase 7: GCP Monitoring (Steps 22–24)

22. **Step 22:** Create the Cloud Monitoring dashboard in GCP Console (Part 6.1).
23. **Step 23:** Create the 5 alert policies in GCP Console (Part 6.2).
24. **Step 24:** Create the 3 uptime checks in GCP Console (Part 6.3).

### Phase 8: Deploy + Lint (Steps 25–27)

25. **Step 25:** Add Sentry DSN to Secret Manager and update Cloud Run deployments (Part 7.1–7.4).
26. **Step 26:** Update `.github/workflows/deploy.yml` with `SENTRY_AUTH_TOKEN` secret (Part 7.5).
27. **Step 27:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd ../../apps/web
    npm run lint
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- Custom metrics backend (Prometheus, Grafana, Datadog) — use Sentry + GCP built-in
- Log-based alerting rules (start with metric-based, add log-based later)
- Real User Monitoring (RUM) beyond what Sentry provides
- Distributed tracing across API → worker (Sentry's RQ integration handles basics)
- Cost dashboards (use GCP Billing Console)
- SLA/SLO definitions (premature for v1)
- On-call rotation / PagerDuty (use email alerts to start)
- Custom Sentry dashboards or performance metrics (use Sentry defaults)

---

## Summary Checklist

### Sentry (API + Worker)
- [ ] `sentry-sdk[fastapi]` installed
- [ ] `sentry_init.py` created with PII scrubbing, integrations (FastAPI, SQLAlchemy, Redis, RQ, Logging)
- [ ] Sentry initialized in `main.py` (API) and `worker.py` (worker)
- [ ] Sentry user context middleware captures user_id per request
- [ ] `send_default_pii=False` — no cookies, IPs, or auth headers sent
- [ ] `_scrub_event` hook removes resume text, profile JSON, passwords, emails from error reports
- [ ] Test error triggers correctly on Sentry dashboard

### Sentry (Frontend)
- [ ] `@sentry/nextjs` installed
- [ ] Client, server, and edge configs created
- [ ] `next.config.js` wrapped with `withSentryConfig`
- [ ] `global-error.tsx` boundary captures and reports errors
- [ ] `NEXT_PUBLIC_SENTRY_DSN` set in `.env.local`
- [ ] Source maps hidden from public access (`hideSourceMaps: true`)

### Structured Logging
- [ ] `JSONFormatter` outputs Cloud Logging-compatible JSON in production
- [ ] Human-readable format in dev mode
- [ ] `RequestLoggingMiddleware` logs every request with: method, path, status, latency, user_id, trace_id
- [ ] Cloud trace ID extracted from `x-cloud-trace-context` header for log correlation
- [ ] Worker jobs include structured log fields (worker_job, job_id, user_id)
- [ ] Noisy libraries silenced (uvicorn.access, sqlalchemy.engine, httpx)

### Worker Health + Observability
- [ ] `worker_health.py` reads queue stats from RQ: pending, started, failed, deferred per queue
- [ ] `GET /api/admin/observability/health` returns full system health (API + DB + Redis + queues)
- [ ] `GET /api/admin/observability/queues` returns queue depths for all queues
- [ ] `GET /api/admin/observability/queues/{name}/failed` returns recent failed jobs with error details
- [ ] `POST /api/admin/observability/queues/{name}/retry-all` retries all failed jobs
- [ ] All admin endpoints gated by `admin_token`

### Health Endpoints
- [ ] `/health` returns uptime_seconds + timestamp
- [ ] `/ready` checks both DB and Redis, returns per-service status

### GCP Cloud Monitoring
- [ ] Dashboard created: request count, latency, instance count, CPU/memory (API + worker), Cloud SQL CPU/memory/connections/disk
- [ ] Alert: API 5xx error rate > 10 in 5 min
- [ ] Alert: API p99 latency > 10 seconds
- [ ] Alert: Cloud SQL CPU > 80% for 10 min
- [ ] Alert: Cloud SQL connections > 90
- [ ] Alert: Cloud SQL disk > 80% capacity
- [ ] Uptime check: API /health every 5 min
- [ ] Uptime check: API /ready every 5 min
- [ ] Uptime check: Web / every 5 min

### Production Deployment
- [ ] SENTRY_DSN in Secret Manager
- [ ] Cloud Run API updated with Sentry env vars
- [ ] Cloud Run Worker updated with Sentry env vars
- [ ] Web Docker build includes NEXT_PUBLIC_SENTRY_DSN
- [ ] Deploy workflow has SENTRY_AUTH_TOKEN for source maps
- [ ] Linted and formatted

Return code changes only.
