## services/api/app/main.py

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Always load services/api/.env regardless of current working directory ---
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

# --- PII-safe logging (before any log calls) ---
from app.middleware.log_filter import configure_safe_logging  # noqa: E402

configure_safe_logging()

# --- Sentry (must be initialized before FastAPI app is created) ---
from app.services.sentry_init import init_sentry  # noqa: E402

init_sentry()

# --- Structured logging (after PII filter + Sentry, before any other imports) ---
from app.middleware.structured_logging import (  # noqa: E402
    RequestLoggingMiddleware,
    configure_structured_logging,
)

configure_structured_logging()

logger = logging.getLogger(__name__)

# IMPORTANT: import routers only AFTER env is loaded
# --- Rate limiting ---
from slowapi.errors import RateLimitExceeded  # noqa: E402

from app.middleware.rate_limit import limiter  # noqa: E402

# --- Security headers middleware ---
from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402
from app.routers.account import router as account_router  # noqa: E402
from app.routers.admin_candidates import router as admin_candidates_router  # noqa: E402
from app.routers.admin_career_pages import router as admin_career_pages_router  # noqa: E402
from app.routers.admin_employers import router as admin_employers_router  # noqa: E402
from app.routers.admin_jobs import router as admin_jobs_router  # noqa: E402
from app.routers.admin_profile import router as admin_profile_router  # noqa: E402
from app.routers.admin_recruiters import router as admin_recruiters_router  # noqa: E402
from app.routers.admin_settings import router as admin_settings_router  # noqa: E402
from app.routers.admin_support import router as admin_support_router  # noqa: E402
from app.routers.admin_trust import router as admin_trust_router  # noqa: E402
from app.routers.auth import router as auth_router  # noqa: E402
from app.routers.billing import router as billing_router  # noqa: E402
from app.routers.bulk_attach import router as bulk_attach_router  # noqa: E402
from app.routers.candidate_insights import (
    router as candidate_insights_router,  # noqa: E402
)
from app.routers.career_intelligence import (  # noqa: E402
    router as career_intelligence_router,
)
from app.routers.career_pages import router as career_pages_router  # noqa: E402
from app.routers.career_pages_apply import (
    router as career_pages_apply_router,  # noqa: E402
)
from app.routers.career_pages_public import (
    router as career_pages_public_router,  # noqa: E402
)
from app.routers.dashboard import router as dashboard_router  # noqa: E402
from app.routers.distribution import router as distribution_router  # noqa: E402
from app.routers.email_ingest import router as email_ingest_router  # noqa: E402
from app.routers.employer import router as employer_router  # noqa: E402
from app.routers.employer_analytics import (  # noqa: E402
    router as employer_analytics_router,
)
from app.routers.employer_billing import router as employer_billing_router  # noqa: E402
from app.routers.employer_compliance import (  # noqa: E402
    router as employer_compliance_router,
)
from app.routers.employer_introductions import (  # noqa: E402
    router as employer_introductions_router,
)
from app.routers.health import router as health_router  # noqa: E402
from app.routers.hiring_workspace import router as hiring_workspace_router  # noqa: E402
from app.routers.interview_prep import router as interview_prep_router  # noqa: E402
from app.routers.job_forms import router as job_forms_router  # noqa: E402
from app.routers.jobs import router as jobs_router  # noqa: E402
from app.routers.market_intelligence import (  # noqa: E402
    router as market_intelligence_router,
)
from app.routers.match import router as match_router  # noqa: E402
from app.routers.matches import router as matches_router  # noqa: E402
from app.routers.migration import router as migration_router  # noqa: E402
from app.routers.mjass import router as mjass_router  # noqa: E402
from app.routers.observability import router as observability_router  # noqa: E402
from app.routers.onboarding import router as onboarding_router  # noqa: E402
from app.routers.onboarding_v1 import router as onboarding_v1_router  # noqa: E402
from app.routers.outreach import router as outreach_router  # noqa: E402
from app.routers.outreach import unsubscribe_router  # noqa: E402
from app.routers.profile import router as profile_router  # noqa: E402
from app.routers.ready import router as ready_router  # noqa: E402
from app.routers.recruiter import router as recruiter_router  # noqa: E402
from app.routers.recruiter_actions import (  # noqa: E402
    router as recruiter_actions_router,
)
from app.routers.recruiter_migration import (  # noqa: E402
    router as recruiter_migration_router,
)
from app.routers.references import router as references_router  # noqa: E402
from app.routers.resume import router as resume_router  # noqa: E402
from app.routers.scheduler import router as scheduler_router  # noqa: E402
from app.routers.security_check import router as security_check_router  # noqa: E402
from app.routers.sieve import router as sieve_router  # noqa: E402
from app.routers.sms_otp import router as sms_otp_router  # noqa: E402
from app.routers.support import router as support_router  # noqa: E402
from app.routers.support_ws import router as support_ws_router  # noqa: E402
from app.routers.tailor import router as tailor_router  # noqa: E402
from app.routers.talent_pipeline import router as talent_pipeline_router  # noqa: E402
from app.routers.telnyx_webhook import router as telnyx_webhook_router  # noqa: E402
from app.routers.trust import router as trust_router  # noqa: E402
from app.routers.upload_batches import router as upload_batches_router  # noqa: E402
from app.routers.webhooks import router as webhooks_router  # noqa: E402
from app.routers.widget_keys import router as widget_keys_router  # noqa: E402

app = FastAPI(title="Winnow API", version="0.1.0")

# Rate limiter state + CORS-aware exception handler
app.state.limiter = limiter


async def _rate_limit_exceeded_handler_cors(request, exc):
    """Return 429 with CORS headers so the browser doesn't block the response."""
    from starlette.responses import JSONResponse

    origin = request.headers.get("origin", "")
    headers = {}
    if origin in ALLOWED_ORIGINS:
        headers["access-control-allow-origin"] = origin
        headers["access-control-allow-credentials"] = "true"
        headers["vary"] = "Origin"
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc.detail)
            if hasattr(exc, "detail")
            else "Rate limit exceeded. Please try again shortly."
        },
        headers=headers,
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler_cors)


# Global unhandled-exception handler — ensures all errors return a proper
# JSONResponse so CORS middleware can add headers (BaseHTTPMiddleware can
# otherwise swallow CORS headers on raw 500s).
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc):  # noqa: ARG001
    import logging as _logging
    import traceback

    _logging.getLogger("winnow.errors").error(
        "Unhandled %s: %s\n%s",
        type(exc).__name__,
        exc,
        traceback.format_exc(),
    )
    from starlette.responses import JSONResponse

    env = os.environ.get("ENV", "dev")
    if env == "dev":
        detail = f"{type(exc).__name__}: {exc}"
    else:
        detail = "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )


# Security headers middleware (applied BEFORE CORS so headers are added after CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Sentry user context middleware (sets user ID on each request for error grouping)
from app.middleware.sentry_context import SentryUserContextMiddleware  # noqa: E402

app.add_middleware(SentryUserContextMiddleware)

# Request logging middleware (structured access logs)
app.add_middleware(RequestLoggingMiddleware)

# CORS — local dev origins plus optional production origin
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Local dev
    "http://127.0.0.1:3000",  # Local dev alt
    "http://localhost:8081",  # Expo dev server
    "http://localhost:19006",  # Expo web
    "https://winnowcc.ai",  # Production — primary
    "https://www.winnowcc.ai",  # Production — www
    "https://winnow-web-cdn2d6pc5q-uc.a.run.app",  # Cloud Run direct
]

# Also keep the dynamic CORS_ORIGIN env var for flexibility
PROD_WEB_URL = os.environ.get("CORS_ORIGIN")
if PROD_WEB_URL and PROD_WEB_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(PROD_WEB_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # TODO: Restrict to published extension ID once Chrome extension is in the store
    allow_origin_regex=r"^chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Admin-Token",
        "X-CSRF-Token",
        "Sentry-Trace",
        "Baggage",
    ],
)

# Founder email context propagation (sets ContextVar in async context so
# all sync billing helpers see it via run_in_threadpool context copies)
from app.middleware.founder_email import FounderEmailMiddleware  # noqa: E402

app.add_middleware(FounderEmailMiddleware)

# Routes
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(onboarding_v1_router)
app.include_router(resume_router)
app.include_router(profile_router)
app.include_router(references_router)
app.include_router(trust_router)
app.include_router(admin_trust_router)
app.include_router(admin_profile_router)
app.include_router(admin_candidates_router)
app.include_router(admin_settings_router)
app.include_router(admin_support_router)
app.include_router(admin_employers_router)
app.include_router(admin_career_pages_router)
app.include_router(admin_recruiters_router)
app.include_router(match_router)
app.include_router(matches_router)
app.include_router(tailor_router)
app.include_router(mjass_router)
app.include_router(dashboard_router)
app.include_router(email_ingest_router)
app.include_router(employer_router)
app.include_router(employer_billing_router)
app.include_router(distribution_router)
app.include_router(scheduler_router)
app.include_router(admin_jobs_router)
app.include_router(job_forms_router)
app.include_router(jobs_router)
app.include_router(billing_router)
app.include_router(sieve_router)
app.include_router(support_router)
app.include_router(support_ws_router)
app.include_router(account_router)
app.include_router(security_check_router)
app.include_router(observability_router)
app.include_router(webhooks_router)
app.include_router(telnyx_webhook_router)
app.include_router(employer_analytics_router)
app.include_router(employer_compliance_router)
app.include_router(employer_introductions_router)
app.include_router(talent_pipeline_router)
app.include_router(recruiter_router)
app.include_router(bulk_attach_router)
app.include_router(recruiter_actions_router)
app.include_router(recruiter_migration_router)
app.include_router(outreach_router)
app.include_router(unsubscribe_router)
app.include_router(hiring_workspace_router)
app.include_router(market_intelligence_router)
app.include_router(career_intelligence_router)
app.include_router(candidate_insights_router)
app.include_router(interview_prep_router)
app.include_router(migration_router)
app.include_router(upload_batches_router)
app.include_router(sms_otp_router)
app.include_router(career_pages_router)
app.include_router(career_pages_public_router)
app.include_router(widget_keys_router)
app.include_router(career_pages_apply_router)


@app.on_event("startup")
async def _validate_security_config():
    """Validate critical security configuration on startup."""
    auth_secret = os.environ.get("AUTH_SECRET", "")
    env = os.environ.get("ENV", "dev")

    if env != "dev":
        # In production, require a strong secret
        if len(auth_secret) < 32:
            raise RuntimeError(
                "AUTH_SECRET must be at least 32 characters in production. "
                'Generate one with: python -c "import secrets; '
                'print(secrets.token_hex(32))"'
            )
        if auth_secret in (
            "dev-secret-change-me",
            "secret",
            "changeme",
        ):
            raise RuntimeError(
                "AUTH_SECRET is using a default value. Set a real secret."
            )

    logger.info("Security config validated (env=%s)", env)


@app.on_event("startup")
async def _load_admin_test_emails():
    """Load dynamic admin test emails from DB into the in-memory set."""
    from app.db.session import get_session_factory
    from app.services.billing import reload_admin_test_emails

    session = get_session_factory()()
    try:
        reload_admin_test_emails(session)
    except Exception:
        logger.exception("Failed to load admin test emails from DB")
    finally:
        session.close()


@app.on_event("startup")
async def _provision_founder_accounts():
    """Ensure founder accounts have admin + highest-tier DB records."""
    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.candidate import Candidate
    from app.models.employer import EmployerProfile
    from app.models.recruiter import RecruiterProfile
    from app.models.user import User
    from app.services.billing import FOUNDER_EMAILS

    if not FOUNDER_EMAILS:
        return

    session = get_session_factory()()
    try:
        for email in FOUNDER_EMAILS:
            user = session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            if user is None:
                logger.info("Founder %s not in DB yet — skipping provisioning", email)
                continue

            changed = False

            # Admin flag
            if not user.is_admin:
                user.is_admin = True
                changed = True

            # Candidate tier
            candidate = session.execute(
                select(Candidate).where(Candidate.user_id == user.id)
            ).scalar_one_or_none()
            if candidate is not None:
                if (
                    candidate.plan_tier != "pro"
                    or candidate.subscription_status is not None
                ):
                    candidate.plan_tier = "pro"
                    candidate.subscription_status = None
                    changed = True

            # Recruiter tier
            rp = session.execute(
                select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
            ).scalar_one_or_none()
            if rp is not None:
                updates = {}
                if rp.subscription_tier != "agency":
                    updates["subscription_tier"] = "agency"
                if rp.subscription_status is not None:
                    updates["subscription_status"] = None
                if not rp.billing_exempt:
                    updates["billing_exempt"] = True
                if updates:
                    for k, v in updates.items():
                        setattr(rp, k, v)
                    changed = True

            # Employer tier
            ep = session.execute(
                select(EmployerProfile).where(EmployerProfile.user_id == user.id)
            ).scalar_one_or_none()
            if ep is not None:
                if (
                    ep.subscription_tier != "enterprise"
                    or ep.subscription_status is not None
                ):
                    ep.subscription_tier = "enterprise"
                    ep.subscription_status = None
                    changed = True

            if changed:
                session.commit()
                logger.info("Provisioned founder account: %s", email)
            else:
                logger.info("Founder account already provisioned: %s", email)
    except Exception:
        session.rollback()
        logger.exception("Failed to provision founder accounts")
    finally:
        session.close()
