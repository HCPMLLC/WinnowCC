"""Stripe billing service — plan management, usage limits, webhook handling."""

from __future__ import annotations

import contextvars
import logging
import os
from datetime import UTC, date

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.usage_counter import UsageCounter
from app.models.user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_MONTHLY = os.getenv("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_ANNUAL = os.getenv("STRIPE_PRICE_ANNUAL", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Founder accounts — bypass all billing gates at highest tier, no Stripe.
# ---------------------------------------------------------------------------

_FOUNDER_EMAILS_DEFAULT = "rlevi@hcpm.llc"
FOUNDER_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.getenv("FOUNDER_EMAILS", _FOUNDER_EMAILS_DEFAULT).split(",")
    if e.strip()
}

_request_user_email: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_request_user_email", default=""
)


def set_request_user_email(email: str) -> None:
    """Set the current request's user email for founder-bypass checks."""
    _request_user_email.set(email.strip().lower())


def is_founder_email(email: str | None = None) -> bool:
    """Check if the given (or current-request) email belongs to a founder."""
    check = email.strip().lower() if email else _request_user_email.get("")
    return bool(check and check in FOUNDER_EMAILS)


# ---------------------------------------------------------------------------
# Unified Plan Limits (three segments)
# ---------------------------------------------------------------------------

CANDIDATE_PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "matches_visible": 5,
        "match_refreshes": 10,
        "tailor_requests": 1,
        "cover_letters": 1,
        "semantic_searches_per_day": 0,
        "sieve_messages_per_day": 3,
        "ips_detail": "breakdown",
        "data_export": False,
        "career_intelligence": False,
        "submission_details": "basic",
        "submission_notifications": False,
    },
    "starter": {
        "matches_visible": 25,
        "match_refreshes": 50,
        "tailor_requests": 10,
        "cover_letters": 10,
        "semantic_searches_per_day": 5,
        "sieve_messages_per_day": 50,
        "ips_detail": "breakdown",
        "data_export": True,
        "career_intelligence": False,
        "submission_details": "standard",
        "submission_notifications": True,
    },
    "pro": {
        "matches_visible": 9999,
        "match_refreshes": 9999,
        "tailor_requests": 9999,
        "cover_letters": 9999,
        "semantic_searches_per_day": 9999,
        "sieve_messages_per_day": 9999,
        "ips_detail": "full_coaching",
        "data_export": True,
        "career_intelligence": True,
        "submission_details": "full",
        "submission_notifications": True,
    },
}

EMPLOYER_PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "active_jobs": 1,
        "candidate_views_per_month": 5,
        "ai_job_parsing_per_month": 1,
        "intro_requests_per_month": 2,
        "multi_board_distribution": ["google_jobs"],
        "cross_board_analytics": False,
        "salary_intelligence": False,
        "bias_detection": False,
        "sieve_messages_per_day": 10,
        "submission_view": "basic",
        "duplicate_highlighting": False,
    },
    "starter": {
        "active_jobs": 5,
        "candidate_views_per_month": 50,
        "ai_job_parsing_per_month": 10,
        "intro_requests_per_month": 15,
        "multi_board_distribution": ["google_jobs", "indeed", "ziprecruiter"],
        "cross_board_analytics": "basic",
        "salary_intelligence": False,
        "bias_detection": "basic",
        "sieve_messages_per_day": 30,
        "submission_view": "standard",
        "duplicate_highlighting": True,
    },
    "pro": {
        "active_jobs": 25,
        "candidate_views_per_month": 200,
        "ai_job_parsing_per_month": 999,
        "intro_requests_per_month": 50,
        "multi_board_distribution": "all",
        "cross_board_analytics": "full",
        "salary_intelligence": True,
        "bias_detection": "full",
        "sieve_messages_per_day": 100,
        "submission_view": "full",
        "duplicate_highlighting": True,
    },
    "enterprise": {
        "active_jobs": 999,
        "candidate_views_per_month": 999,
        "ai_job_parsing_per_month": 999,
        "intro_requests_per_month": 999,
        "multi_board_distribution": "all",
        "cross_board_analytics": "full",
        "salary_intelligence": True,
        "bias_detection": "full",
        "sieve_messages_per_day": 999,
        "submission_view": "full",
        "duplicate_highlighting": True,
    },
}

RECRUITER_PLAN_LIMITS: dict[str, dict] = {
    "trial": {
        "seats": 1,
        "candidate_briefs_per_month": 999,
        "chrome_extension": True,
        "salary_lookups_per_month": 999,
        "smart_job_parsing_per_month": 10,
        "migration_toolkit": "full",
        "client_crm": "full",
        "trial_duration_days": 14,
        "active_job_orders": 999,
        "pipeline_candidates": 999,
        "clients": 999,
        "activities_per_day": 999,
        "intro_requests_per_month": 999,
        "resume_imports_per_month": 50,
        "resume_imports_per_batch": 10,
        "sieve_messages_per_day": 30,
        "outreach_sequences": False,
        "active_sequences": 0,
        "enrollments_per_month": 0,
        "cross_vendor_duplicate_check": True,
        "contract_vehicle_management": True,
        "client_hierarchy": True,
        "submission_analytics": True,
    },
    "solo": {
        "seats": 1,
        "candidate_briefs_per_month": 20,
        "chrome_extension": True,
        "salary_lookups_per_month": 5,
        "smart_job_parsing_per_month": 0,
        "migration_toolkit": "full",
        "client_crm": "basic",
        "active_job_orders": 10,
        "pipeline_candidates": 100,
        "clients": 5,
        "activities_per_day": 999,
        "intro_requests_per_month": 20,
        "resume_imports_per_month": 25,
        "resume_imports_per_batch": 10,
        "sieve_messages_per_day": 30,
        "outreach_sequences": False,
        "active_sequences": 0,
        "enrollments_per_month": 0,
        "cross_vendor_duplicate_check": False,
        "contract_vehicle_management": False,
        "client_hierarchy": False,
        "submission_analytics": False,
    },
    "team": {
        "seats": 10,
        "candidate_briefs_per_month": 100,
        "chrome_extension": True,
        "salary_lookups_per_month": 50,
        "smart_job_parsing_per_month": 10,
        "migration_toolkit": "full",
        "client_crm": "full",
        "active_job_orders": 50,
        "pipeline_candidates": 500,
        "clients": 25,
        "activities_per_day": 999,
        "intro_requests_per_month": 75,
        "resume_imports_per_month": 200,
        "resume_imports_per_batch": 25,
        "sieve_messages_per_day": 30,
        "outreach_sequences": True,
        "active_sequences": 3,
        "enrollments_per_month": 50,
        "cross_vendor_duplicate_check": True,
        "contract_vehicle_management": True,
        "client_hierarchy": True,
        "submission_analytics": True,
    },
    "agency": {
        "seats": 999,
        "candidate_briefs_per_month": 500,
        "chrome_extension": True,
        "salary_lookups_per_month": 999,
        "smart_job_parsing_per_month": 999,
        "migration_toolkit": "full",
        "client_crm": "full",
        "active_job_orders": 999,
        "pipeline_candidates": 999,
        "clients": 999,
        "activities_per_day": 999,
        "intro_requests_per_month": 999,
        "resume_imports_per_month": 999,
        "resume_imports_per_batch": 50,
        "sieve_messages_per_day": 30,
        "outreach_sequences": True,
        "active_sequences": 10,
        "enrollments_per_month": 200,
        "cross_vendor_duplicate_check": True,
        "contract_vehicle_management": True,
        "client_hierarchy": True,
        "submission_analytics": True,
    },
}

# Backward compat
PLAN_LIMITS = CANDIDATE_PLAN_LIMITS

# ---------------------------------------------------------------------------
# Stripe Price ID Map
# ---------------------------------------------------------------------------

PRICE_IDS: dict[tuple[str, str, str], str] = {
    # Candidates
    ("candidate", "starter", "monthly"): os.getenv(
        "STRIPE_PRICE_CANDIDATE_STARTER_MO", ""
    ),
    ("candidate", "starter", "annual"): os.getenv(
        "STRIPE_PRICE_CANDIDATE_STARTER_YR", ""
    ),
    ("candidate", "pro", "monthly"): os.getenv("STRIPE_PRICE_CANDIDATE_PRO_MO", ""),
    ("candidate", "pro", "annual"): os.getenv("STRIPE_PRICE_CANDIDATE_PRO_YR", ""),
    # Employers
    ("employer", "starter", "monthly"): os.getenv(
        "STRIPE_PRICE_EMPLOYER_STARTER_MO", ""
    ),
    ("employer", "starter", "annual"): os.getenv(
        "STRIPE_PRICE_EMPLOYER_STARTER_YR", ""
    ),
    ("employer", "pro", "monthly"): os.getenv("STRIPE_PRICE_EMPLOYER_PRO_MO", ""),
    ("employer", "pro", "annual"): os.getenv("STRIPE_PRICE_EMPLOYER_PRO_YR", ""),
    # Recruiters
    ("recruiter", "solo", "monthly"): os.getenv("STRIPE_PRICE_RECRUITER_SOLO_MO", ""),
    ("recruiter", "solo", "annual"): os.getenv("STRIPE_PRICE_RECRUITER_SOLO_YR", ""),
    ("recruiter", "team", "monthly"): os.getenv("STRIPE_PRICE_RECRUITER_TEAM_MO", ""),
    ("recruiter", "team", "annual"): os.getenv("STRIPE_PRICE_RECRUITER_TEAM_YR", ""),
    ("recruiter", "agency", "monthly"): os.getenv(
        "STRIPE_PRICE_RECRUITER_AGENCY_MO", ""
    ),
    ("recruiter", "agency", "annual"): os.getenv(
        "STRIPE_PRICE_RECRUITER_AGENCY_YR", ""
    ),
}

# Published prices for the public plans endpoint (no auth required)
PUBLISHED_PRICES: dict[str, dict] = {
    "candidate": {
        "free": {"monthly": 0, "annual": 0},
        "starter": {"monthly": 9, "annual": 79},
        "pro": {"monthly": 29, "annual": 249},
    },
    "employer": {
        "free": {"monthly": 0, "annual": 0},
        "starter": {"monthly": 49, "annual": 399},
        "pro": {"monthly": 149, "annual": 1199},
        "enterprise": {"monthly": "custom", "annual": "custom"},
    },
    "recruiter": {
        "trial": {"monthly": 0, "annual": 0, "duration_days": 14},
        "solo": {"monthly": 39, "annual": 349},
        "team": {"monthly": 89, "annual": 799, "per_seat": True},
        "agency": {"monthly": 129, "annual": 1159, "per_seat": True},
    },
}

VALID_CHECKOUT_COMBOS: dict[str, list[str]] = {
    "candidate": ["starter", "pro"],
    "employer": ["starter", "pro"],
    "recruiter": ["solo", "team", "agency"],
}


def get_price_id(segment: str, tier: str, interval: str = "monthly") -> str:
    """Look up the Stripe Price ID for a segment/tier/interval combination."""
    price_id = PRICE_IDS.get((segment, tier, interval))
    if not price_id:
        raise ValueError(f"No Stripe price configured for {segment}/{tier}/{interval}")
    return price_id


def get_plan_limits(plan: str, segment: str = "candidate") -> dict:
    """Return the limits dict for a given plan and segment."""
    limits_map = {
        "candidate": CANDIDATE_PLAN_LIMITS,
        "employer": EMPLOYER_PLAN_LIMITS,
        "recruiter": RECRUITER_PLAN_LIMITS,
    }
    m = limits_map.get(segment, CANDIDATE_PLAN_LIMITS)
    return m.get(plan, next(iter(m.values())))


def _stripe_client() -> stripe.StripeClient:
    """Return a configured Stripe client.  Raises 503 if key is missing."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")
    return stripe.StripeClient(STRIPE_SECRET_KEY)


# ---------------------------------------------------------------------------
# Plan helpers
# ---------------------------------------------------------------------------


def get_plan_tier(candidate: Candidate | None) -> str:
    """Derive effective plan tier from candidate record."""
    if is_founder_email():
        return "pro"
    if candidate is None:
        return "free"
    tier = candidate.plan_tier or "free"
    if tier in ("pro", "starter"):
        if candidate.subscription_status in ("active", "trialing"):
            return tier
        # Admin override: plan_tier set with no subscription means manually set
        if candidate.subscription_status is None:
            return tier
    return "free"


# ---------------------------------------------------------------------------
# Tier limit helpers
# ---------------------------------------------------------------------------


def get_tier_limit(tier: str, key: str) -> int | bool | str:
    """Look up a specific limit for a candidate, employer, or recruiter tier."""
    # Check candidate limits first, then employer, then recruiter limits
    if tier in CANDIDATE_PLAN_LIMITS:
        limits = CANDIDATE_PLAN_LIMITS[tier]
        if key in limits:
            return limits[key]
    if tier in EMPLOYER_PLAN_LIMITS:
        limits = EMPLOYER_PLAN_LIMITS[tier]
        if key in limits:
            return limits[key]
    if tier in RECRUITER_PLAN_LIMITS:
        limits = RECRUITER_PLAN_LIMITS[tier]
        if key in limits:
            return limits[key]
    # Fallback to candidate free tier
    return CANDIDATE_PLAN_LIMITS.get("free", {}).get(key, 0)


def check_feature_access(tier: str, feature: str) -> bool:
    """Check if a boolean feature is enabled for a tier."""
    return bool(get_tier_limit(tier, feature))


def check_daily_limit(
    session: Session,
    user_id: int,
    tier: str,
    counter_name: str,
    limit_key: str,
    request=None,
) -> None:
    """Raise 429 if the user has exceeded a daily limit for their tier."""
    from app.models.daily_usage_counter import DailyUsageCounter

    is_mobile = (
        request is not None
        and getattr(request, "headers", None) is not None
        and request.headers.get("X-Client-Platform") == "mobile"
    )

    limit = get_tier_limit(tier, limit_key)
    if isinstance(limit, int) and limit >= 9999:
        return  # unlimited
    if isinstance(limit, int) and limit == 0:
        detail = (
            "This feature is available on WinnowCC.ai."
            if is_mobile
            else "This feature requires a Starter or Pro plan."
        )
        raise HTTPException(status_code=403, detail=detail)

    current = DailyUsageCounter.get_today_count(session, user_id, counter_name)
    if current >= int(limit):
        detail = (
            "For the best experience with all features, please visit WinnowCC.ai."
            if is_mobile
            else f"Daily limit reached ({limit} per day). Upgrade your plan for more."
        )
        raise HTTPException(status_code=429, detail=detail)


def increment_daily_counter(session: Session, user_id: int, counter_name: str) -> int:
    """Increment a daily usage counter. Returns the new count."""
    from app.models.daily_usage_counter import DailyUsageCounter

    return DailyUsageCounter.increment(session, user_id, counter_name)


# ---------------------------------------------------------------------------
# Monthly usage counters
# ---------------------------------------------------------------------------


def _current_period_start() -> date:
    """First day of the current month."""
    today = date.today()
    return today.replace(day=1)


def get_or_create_usage(session: Session, user_id: int) -> UsageCounter:
    period = _current_period_start()
    usage = session.execute(
        select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.period_start == period,
        )
    ).scalar_one_or_none()
    if usage is None:
        usage = UsageCounter(user_id=user_id, period_start=period)
        session.add(usage)
        session.flush()
    return usage


def check_match_refresh_limit(
    session: Session,
    user: User,
    candidate: Candidate | None,
) -> None:
    """Raise 429 if user has exceeded match refresh limit for their tier."""
    tier = get_plan_tier(candidate)
    limit = get_tier_limit(tier, "match_refreshes")
    if isinstance(limit, int) and limit >= 9999:
        return
    usage = get_or_create_usage(session, user.id)
    if usage.match_refreshes >= int(limit):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Plan limit reached: {limit} match refreshes per month. "
                "Upgrade for more."
            ),
        )


def increment_match_refreshes(session: Session, user_id: int) -> None:
    usage = get_or_create_usage(session, user_id)
    usage.match_refreshes += 1
    session.flush()


def check_tailor_limit(
    session: Session,
    user: User,
    candidate: Candidate | None,
) -> None:
    """Raise 429 if user has exceeded tailor request limit for their tier."""
    tier = get_plan_tier(candidate)
    limit = get_tier_limit(tier, "tailor_requests")
    if isinstance(limit, int) and limit >= 9999:
        return
    usage = get_or_create_usage(session, user.id)
    if usage.tailor_requests >= int(limit):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Plan limit reached: {limit} tailored documents per month. "
                "Upgrade for more."
            ),
        )


def increment_tailor_requests(session: Session, user_id: int) -> None:
    usage = get_or_create_usage(session, user_id)
    usage.tailor_requests += 1
    session.flush()


# ---------------------------------------------------------------------------
# Recruiter tier helpers
# ---------------------------------------------------------------------------


def get_recruiter_tier(profile) -> str:
    """Derive effective tier from a RecruiterProfile."""
    if is_founder_email():
        return "agency"
    tier = (profile.subscription_tier or "trial").lower()
    # Billing-exempt accounts always get their stored tier
    if getattr(profile, "billing_exempt", False):
        return tier
    if tier == "trial":
        if profile.is_trial_active:
            return "trial"
        return "trial"  # expired trial still gets trial limits (read-only)
    if profile.subscription_status in ("active", "trialing"):
        return tier
    # Admin override: tier set with no subscription means manually set
    if profile.subscription_status is None:
        return tier
    return "trial"


def get_recruiter_limit(tier: str, key: str):
    """Look up a specific limit for a recruiter tier."""
    limits = RECRUITER_PLAN_LIMITS.get(tier, RECRUITER_PLAN_LIMITS["trial"])
    return limits.get(key, 0)


def _maybe_reset_recruiter_counters(profile, session: Session) -> None:
    """Reset monthly counters if the current period has rolled over."""
    from datetime import datetime as _dt

    now = _dt.now(UTC)
    reset_at = profile.usage_reset_at
    if reset_at is None or reset_at.month != now.month or reset_at.year != now.year:
        profile.candidate_briefs_used = 0
        profile.salary_lookups_used = 0
        profile.job_uploads_used = 0
        profile.intro_requests_used = 0
        profile.resume_imports_used = 0
        profile.outreach_enrollments_used = 0
        profile.usage_reset_at = now
        session.flush()


def check_recruiter_monthly_limit(
    profile,
    counter_attr: str,
    limit_key: str,
    session: Session,
) -> None:
    """Raise 429 if the recruiter has exceeded a monthly limit for their tier."""
    _maybe_reset_recruiter_counters(profile, session)
    tier = get_recruiter_tier(profile)
    limit = get_recruiter_limit(tier, limit_key)
    if isinstance(limit, int) and limit >= 999:
        return  # unlimited
    current = getattr(profile, counter_attr, 0) or 0
    if current >= int(limit):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly limit reached ({limit} per month on {tier} plan). "
                "Upgrade your plan for more."
            ),
        )


def increment_recruiter_counter(
    profile,
    counter_attr: str,
    session: Session,
) -> int:
    """Increment a recruiter monthly usage counter. Returns new count."""
    _maybe_reset_recruiter_counters(profile, session)
    current = getattr(profile, counter_attr, 0) or 0
    new_val = current + 1
    setattr(profile, counter_attr, new_val)
    session.flush()
    return new_val


def check_recruiter_feature(profile, feature_key: str) -> bool:
    """Check if a feature is available for the recruiter's tier."""
    tier = get_recruiter_tier(profile)
    val = get_recruiter_limit(tier, feature_key)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val != "none"
    return bool(val)


# ---------------------------------------------------------------------------
# Employer tier helpers
# ---------------------------------------------------------------------------


def get_employer_tier(profile) -> str:
    """Derive effective tier from an EmployerProfile."""
    if is_founder_email():
        return "enterprise"
    tier = (profile.subscription_tier or "free").lower()
    if tier == "free":
        return "free"
    if tier in ("starter", "pro", "enterprise"):
        if profile.subscription_status in ("active", "trialing"):
            return tier
        # Manually-set tier with no subscription status
        if profile.subscription_status is None:
            return tier
    return "free"


def get_employer_limit(tier: str, key: str):
    """Look up a specific limit for an employer tier."""
    limits = EMPLOYER_PLAN_LIMITS.get(tier, EMPLOYER_PLAN_LIMITS["free"])
    return limits.get(key, 0)


def _maybe_reset_employer_counters(profile, session: Session) -> None:
    """Reset monthly counters if the current period has rolled over."""
    from datetime import datetime as _dt

    now = _dt.now(UTC)
    reset_at = profile.usage_reset_at
    if reset_at is None or reset_at.month != now.month or reset_at.year != now.year:
        profile.ai_parsing_used = 0
        profile.intro_requests_used = 0
        profile.usage_reset_at = now
        session.flush()


def check_employer_monthly_limit(
    profile,
    counter_attr: str,
    limit_key: str,
    session: Session,
) -> None:
    """Raise 429 if the employer has exceeded a monthly limit for their tier."""
    _maybe_reset_employer_counters(profile, session)
    tier = get_employer_tier(profile)
    limit = get_employer_limit(tier, limit_key)
    if isinstance(limit, int) and limit >= 999:
        return  # unlimited
    current = getattr(profile, counter_attr, 0) or 0
    if current >= int(limit):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly limit reached ({limit} per month on {tier} plan). "
                "Upgrade your plan for more."
            ),
        )


def increment_employer_counter(
    profile,
    counter_attr: str,
    session: Session,
) -> int:
    """Increment an employer monthly usage counter. Returns new count."""
    _maybe_reset_employer_counters(profile, session)
    current = getattr(profile, counter_attr, 0) or 0
    new_val = current + 1
    setattr(profile, counter_attr, new_val)
    session.flush()
    return new_val


def check_employer_feature(profile, feature_key: str):
    """Check if a feature is available for the employer's tier.

    Returns the feature value: bool, str level, or list.
    """
    tier = get_employer_tier(profile)
    val = get_employer_limit(tier, feature_key)
    return val


# ---------------------------------------------------------------------------
# Stripe Customer
# ---------------------------------------------------------------------------


def get_or_create_stripe_customer(
    session: Session, user: User, candidate: Candidate
) -> str:
    """Return the Stripe customer ID, creating one if needed."""
    if candidate.stripe_customer_id:
        return candidate.stripe_customer_id

    client = _stripe_client()
    customer = client.customers.create(
        params={"email": user.email, "metadata": {"user_id": str(user.id)}}
    )
    candidate.stripe_customer_id = customer.id
    session.flush()
    return customer.id


# ---------------------------------------------------------------------------
# Checkout & Portal
# ---------------------------------------------------------------------------


def create_checkout_session(
    session: Session, user: User, candidate: Candidate, billing_cycle: str
) -> str:
    """Create a Stripe Checkout session and return the URL (legacy candidate-only)."""
    return create_unified_checkout(
        session,
        user,
        candidate=candidate,
        segment="candidate",
        tier="pro",
        interval=billing_cycle,
    )


def create_unified_checkout(
    session: Session,
    user: User,
    *,
    candidate: Candidate | None = None,
    segment: str = "candidate",
    tier: str = "pro",
    interval: str = "monthly",
) -> str:
    """Create a Stripe Checkout session for any segment/tier/interval."""
    if is_founder_email(user.email):
        raise HTTPException(
            status_code=400,
            detail="Founder accounts do not require billing.",
        )
    # Dev mode: when Stripe webhooks are not configured, directly upgrade the
    # plan tier and return the success URL.  Without a webhook secret, Stripe
    # checkout would succeed but the plan_tier would never get updated because
    # the webhook handler can't verify or receive the subscription event.
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        if segment == "candidate" and candidate is not None:
            candidate.plan_tier = tier
            session.flush()
        success_url = f"{FRONTEND_URL}/settings?billing=success"
        logger.info(
            "Dev mode: upgraded %s to %s/%s (no webhook)", user.email, segment, tier
        )
        return success_url

    price_id = get_price_id(segment, tier, interval)

    # Determine Stripe customer ID based on segment
    if segment == "candidate":
        if candidate is None:
            raise HTTPException(status_code=404, detail="Complete onboarding first.")
        customer_id = get_or_create_stripe_customer(session, user, candidate)
    elif segment == "recruiter":
        from app.models.recruiter import RecruiterProfile

        rp = session.execute(
            select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
        ).scalar_one_or_none()
        if rp is None:
            raise HTTPException(
                status_code=404, detail="Complete recruiter registration first."
            )
        if rp.stripe_customer_id:
            customer_id = rp.stripe_customer_id
        else:
            client = _stripe_client()
            cust = client.customers.create(
                params={"email": user.email, "metadata": {"user_id": str(user.id)}}
            )
            rp.stripe_customer_id = cust.id
            session.flush()
            customer_id = cust.id
    else:
        # employer
        from app.models.employer import EmployerProfile

        ep = session.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == user.id)
        ).scalar_one_or_none()
        if ep is None:
            raise HTTPException(
                status_code=404, detail="Complete employer registration first."
            )
        if ep.stripe_customer_id:
            customer_id = ep.stripe_customer_id
        else:
            client = _stripe_client()
            cust = client.customers.create(
                params={"email": user.email, "metadata": {"user_id": str(user.id)}}
            )
            ep.stripe_customer_id = cust.id
            session.flush()
            customer_id = cust.id

    # Determine quantity (recruiter team/agency plans are per-seat)
    quantity = 1

    # Success/cancel URLs per segment
    success_paths = {
        "candidate": "/settings?billing=success",
        "employer": "/employer?billing=success",
        "recruiter": "/settings?billing=success",
    }
    cancel_paths = {
        "candidate": "/settings?canceled=true",
        "employer": "/employer?canceled=true",
        "recruiter": "/settings?canceled=true",
    }

    client = _stripe_client()
    checkout = client.checkout.sessions.create(
        params={
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": quantity}],
            "success_url": (
                f"{FRONTEND_URL}"
                f"{success_paths.get(segment, '/settings?billing=success')}"
            ),
            "cancel_url": (
                f"{FRONTEND_URL}{cancel_paths.get(segment, '/settings?canceled=true')}"
            ),
            "metadata": {
                "user_id": str(user.id),
                "segment": segment,
                "tier": tier,
            },
        }
    )
    return checkout.url


def create_portal_session(session: Session, user: User, candidate: Candidate) -> str:
    """Create a Stripe Customer Portal session and return the URL."""
    if not STRIPE_SECRET_KEY:
        return f"{FRONTEND_URL}/settings"
    customer_id = get_or_create_stripe_customer(session, user, candidate)
    client = _stripe_client()
    portal = client.billing_portal.sessions.create(
        params={
            "customer": customer_id,
            "return_url": f"{FRONTEND_URL}/settings",
        }
    )
    return portal.url


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------


def handle_webhook_event(payload: bytes, sig_header: str, session: Session) -> dict:
    """Verify and dispatch a Stripe webhook event."""
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured.")

    client = _stripe_client()
    try:
        event = client.webhooks.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature.") from exc

    event_type = event.type
    data_object = event.data.object

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data_object, session)
    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _handle_subscription_change(data_object, session)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data_object, session)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"status": "ok"}


def _find_candidate_by_stripe_customer(
    session: Session,
    customer_id: str,
) -> Candidate | None:
    return session.execute(
        select(Candidate).where(Candidate.stripe_customer_id == customer_id)
    ).scalar_one_or_none()


def _handle_checkout_completed(checkout_session: object, session: Session) -> None:
    customer_id = getattr(checkout_session, "customer", None)
    subscription_id = getattr(checkout_session, "subscription", None)
    metadata = getattr(checkout_session, "metadata", {}) or {}
    segment = metadata.get("segment", "candidate")
    tier = metadata.get("tier", "pro")
    if not customer_id:
        return

    # Determine billing interval from Stripe subscription
    billing_interval = "monthly"
    if subscription_id:
        try:
            client = _stripe_client()
            sub = client.subscriptions.retrieve(subscription_id)
            interval = (
                sub.items.data[0].price.recurring.interval if sub.items.data else None
            )
            billing_interval = "annual" if interval == "year" else "monthly"
        except Exception:
            pass

    if segment == "recruiter":
        from app.models.recruiter import RecruiterProfile

        rp = session.execute(
            select(RecruiterProfile).where(
                RecruiterProfile.stripe_customer_id == customer_id
            )
        ).scalar_one_or_none()
        if rp is None:
            logger.warning("No recruiter for Stripe customer %s", customer_id)
            return
        if rp.billing_exempt:
            logger.info(
                "Skipping checkout for billing-exempt recruiter %s", rp.company_name
            )
            return
        rp.stripe_subscription_id = subscription_id
        rp.subscription_status = "active"
        rp.subscription_tier = tier
        rp.billing_interval = billing_interval
    elif segment == "employer":
        from app.models.employer import EmployerProfile

        ep = session.execute(
            select(EmployerProfile).where(
                EmployerProfile.stripe_customer_id == customer_id
            )
        ).scalar_one_or_none()
        if ep is None:
            logger.warning("No employer for Stripe customer %s", customer_id)
            return
        ep.stripe_subscription_id = subscription_id
        ep.subscription_status = "active"
        ep.subscription_tier = tier
        ep.billing_interval = billing_interval
    else:
        # candidate (default)
        candidate = _find_candidate_by_stripe_customer(session, customer_id)
        if candidate is None:
            logger.warning("No candidate for Stripe customer %s", customer_id)
            return
        candidate.stripe_subscription_id = subscription_id
        candidate.subscription_status = "active"
        candidate.plan_tier = tier
        candidate.plan_billing_cycle = billing_interval
    session.flush()


def _handle_subscription_change(subscription: object, session: Session) -> None:
    customer_id = getattr(subscription, "customer", None)
    status = getattr(subscription, "status", None)
    sub_id = getattr(subscription, "id", None)
    getattr(subscription, "metadata", {}) or {}
    if not customer_id:
        return

    # Try candidate first (most common)
    candidate = _find_candidate_by_stripe_customer(session, customer_id)
    if candidate is not None:
        candidate.stripe_subscription_id = sub_id
        candidate.subscription_status = status
        if status in ("canceled", "unpaid"):
            candidate.plan_tier = "free"
        elif status in ("active", "trialing"):
            candidate.plan_tier = candidate.plan_tier or "pro"
        session.flush()
        return

    # Try recruiter
    from app.models.recruiter import RecruiterProfile

    rp = session.execute(
        select(RecruiterProfile).where(
            RecruiterProfile.stripe_customer_id == customer_id
        )
    ).scalar_one_or_none()
    if rp is not None:
        if rp.billing_exempt:
            logger.info(
                "Skipping sub change for billing-exempt recruiter %s", rp.company_name
            )
            return
        rp.stripe_subscription_id = sub_id
        rp.subscription_status = status
        if status in ("canceled", "unpaid"):
            rp.subscription_tier = "trial"
        session.flush()
        return

    # Try employer
    from app.models.employer import EmployerProfile

    ep = session.execute(
        select(EmployerProfile).where(EmployerProfile.stripe_customer_id == customer_id)
    ).scalar_one_or_none()
    if ep is not None:
        ep.stripe_subscription_id = sub_id
        ep.subscription_status = status
        if status in ("canceled", "unpaid"):
            ep.subscription_tier = "free"
        session.flush()


def _handle_payment_failed(invoice: object, session: Session) -> None:
    customer_id = getattr(invoice, "customer", None)
    if not customer_id:
        return

    # Try all segments
    candidate = _find_candidate_by_stripe_customer(session, customer_id)
    if candidate is not None:
        candidate.subscription_status = "past_due"
        session.flush()
        return

    from app.models.recruiter import RecruiterProfile

    rp = session.execute(
        select(RecruiterProfile).where(
            RecruiterProfile.stripe_customer_id == customer_id
        )
    ).scalar_one_or_none()
    if rp is not None:
        if rp.billing_exempt:
            logger.info(
                "Skipping payment_failed for billing-exempt recruiter %s",
                rp.company_name,
            )
            return
        rp.subscription_status = "past_due"
        session.flush()
        return

    from app.models.employer import EmployerProfile

    ep = session.execute(
        select(EmployerProfile).where(EmployerProfile.stripe_customer_id == customer_id)
    ).scalar_one_or_none()
    if ep is not None:
        ep.subscription_status = "past_due"
        session.flush()
