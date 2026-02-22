"""Billing router — plan status, Stripe Checkout, Portal, webhooks, admin override."""

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.middleware.rate_limit import limiter
from app.models.candidate import Candidate
from app.models.user import User
from app.schemas.billing import (
    AdminPlanOverrideRequest,
    AdminPlanOverrideResponse,
    BillingStatusResponse,
    CheckoutSessionResponse,
    FeatureAccess,
    PlanTierDetail,
    PlansResponse,
    PortalSessionResponse,
    UnifiedCheckoutRequest,
    UsageSummary,
)
from app.services.auth import get_client_platform, get_current_user
from app.services.billing import (
    CANDIDATE_PLAN_LIMITS,
    EMPLOYER_PLAN_LIMITS,
    PUBLISHED_PRICES,
    RECRUITER_PLAN_LIMITS,
    VALID_CHECKOUT_COMBOS,
    check_feature_access,
    create_checkout_session,
    create_portal_session,
    create_unified_checkout,
    get_or_create_usage,
    get_plan_tier,
    get_tier_limit,
    handle_webhook_event,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

_LIMITS_MAP = {
    "candidate": CANDIDATE_PLAN_LIMITS,
    "employer": EMPLOYER_PLAN_LIMITS,
    "recruiter": RECRUITER_PLAN_LIMITS,
}


def _get_candidate(session: Session, user_id: int) -> Candidate | None:
    return session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()


# ---------- GET /api/billing/status ----------
@router.get("/status")
def billing_status(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    candidate = _get_candidate(session, user.id)
    tier = get_plan_tier(candidate)

    # Mobile clients get a minimal response (Apple App Store compliance)
    platform = get_client_platform(request)
    if platform == "mobile":
        return {"plan_tier": tier, "platform": "mobile"}

    usage = get_or_create_usage(session, user.id)

    # Daily counters
    from app.models.daily_usage_counter import DailyUsageCounter

    sieve_today = DailyUsageCounter.get_today_count(session, user.id, "sieve_messages")
    search_today = DailyUsageCounter.get_today_count(session, user.id, "semantic_searches")
    session.commit()

    # Tier limits for response
    tier_limits = CANDIDATE_PLAN_LIMITS.get(tier, CANDIDATE_PLAN_LIMITS["free"])
    match_refresh_limit = get_tier_limit(tier, "match_refreshes")
    tailor_limit = get_tier_limit(tier, "tailor_requests")

    return BillingStatusResponse(
        plan_tier=tier,
        billing_cycle=candidate.plan_billing_cycle if candidate else None,
        subscription_status=candidate.subscription_status if candidate else None,
        match_refreshes_used=usage.match_refreshes,
        match_refreshes_limit=int(match_refresh_limit) if int(match_refresh_limit) < 9999 else None,
        tailor_requests_used=usage.tailor_requests,
        tailor_requests_limit=int(tailor_limit) if int(tailor_limit) < 9999 else None,
        usage=UsageSummary(
            match_refreshes=usage.match_refreshes,
            tailor_requests=usage.tailor_requests,
            sieve_messages_today=sieve_today,
            semantic_searches_today=search_today,
        ),
        limits=tier_limits,
        features=FeatureAccess(
            data_export=check_feature_access(tier, "data_export"),
            career_intelligence=check_feature_access(tier, "career_intelligence"),
            ips_detail=str(get_tier_limit(tier, "ips_detail")),
        ),
    )


# ---------- POST /api/billing/checkout ----------
@router.post("/checkout", response_model=CheckoutSessionResponse)
def checkout(
    billing_cycle: str = "monthly",
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CheckoutSessionResponse:
    if billing_cycle not in ("monthly", "annual"):
        raise HTTPException(
            status_code=400,
            detail="billing_cycle must be 'monthly' or 'annual'.",
        )

    candidate = _get_candidate(session, user.id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Complete onboarding first.")

    url = create_checkout_session(session, user, candidate, billing_cycle)
    session.commit()
    return CheckoutSessionResponse(checkout_url=url)


# ---------- GET /api/billing/plans/{segment} ---------- (public, no auth)
@router.get("/plans/{segment}", response_model=PlansResponse)
def get_plans(segment: str) -> PlansResponse:
    """Return published plan tiers, limits, and prices for a segment."""
    if segment not in _LIMITS_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown segment: {segment}")

    limits = _LIMITS_MAP[segment]
    prices = PUBLISHED_PRICES.get(segment, {})

    tiers = []
    for tier_name, tier_limits in limits.items():
        tiers.append(
            PlanTierDetail(
                tier=tier_name,
                limits=tier_limits,
                prices=prices.get(tier_name, {}),
            )
        )
    return PlansResponse(segment=segment, tiers=tiers)


# ---------- POST /api/billing/unified-checkout ----------
@router.post("/unified-checkout", response_model=CheckoutSessionResponse)
def unified_checkout(
    body: UnifiedCheckoutRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for any segment/tier/interval."""
    if body.segment not in VALID_CHECKOUT_COMBOS:
        raise HTTPException(status_code=400, detail=f"Unknown segment: {body.segment}")
    if body.tier not in VALID_CHECKOUT_COMBOS[body.segment]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier '{body.tier}' for segment '{body.segment}'.",
        )
    if body.interval not in ("monthly", "annual"):
        raise HTTPException(
            status_code=400, detail="interval must be 'monthly' or 'annual'."
        )

    candidate = (
        _get_candidate(session, user.id) if body.segment == "candidate" else None
    )
    url = create_unified_checkout(
        session,
        user,
        candidate=candidate,
        segment=body.segment,
        tier=body.tier,
        interval=body.interval,
    )
    session.commit()
    return CheckoutSessionResponse(checkout_url=url)


# ---------- POST /api/billing/portal ----------
@router.post("/portal", response_model=PortalSessionResponse)
def portal(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PortalSessionResponse:
    candidate = _get_candidate(session, user.id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Complete onboarding first.")

    url = create_portal_session(session, user, candidate)
    session.commit()
    return PortalSessionResponse(portal_url=url)


# ---------- POST /api/billing/webhook ----------
@router.post("/webhook")
@limiter.limit("100/minute")
async def webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = handle_webhook_event(payload, sig_header, session)
    session.commit()
    return result


# ---------- POST /api/billing/admin/override/{user_id} ----------
@router.post("/admin/override/{user_id}", response_model=AdminPlanOverrideResponse)
def admin_override(
    user_id: int,
    body: AdminPlanOverrideRequest,
    session: Session = Depends(get_session),
    x_admin_token: str = Header(default=""),
) -> AdminPlanOverrideResponse:
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    segment = body.segment or "candidate"

    if segment == "employer":
        from app.models.employer import EmployerProfile

        profile = session.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == user_id)
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Employer not found.")
        profile.subscription_tier = body.plan_tier
        profile.subscription_status = None
        session.commit()
        return AdminPlanOverrideResponse(
            user_id=user_id,
            plan_tier=profile.subscription_tier,
            billing_cycle=body.billing_cycle,
            segment="employer",
        )

    if segment == "recruiter":
        from app.models.recruiter import RecruiterProfile

        profile = session.execute(
            select(RecruiterProfile).where(RecruiterProfile.user_id == user_id)
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Recruiter not found.")
        profile.subscription_tier = body.plan_tier
        profile.subscription_status = body.billing_cycle and "active" or None
        # Clear trial dates if moving from trial to a paid tier
        if body.plan_tier != "trial":
            profile.trial_started_at = None
            profile.trial_ends_at = None
        session.commit()
        return AdminPlanOverrideResponse(
            user_id=user_id,
            plan_tier=profile.subscription_tier,
            billing_cycle=body.billing_cycle,
            segment="recruiter",
        )

    # Default: candidate
    candidate = _get_candidate(session, user_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    candidate.plan_tier = body.plan_tier
    candidate.plan_billing_cycle = body.billing_cycle
    # Clear subscription status for admin overrides so get_plan_tier() uses the None path
    candidate.subscription_status = None
    session.commit()

    return AdminPlanOverrideResponse(
        user_id=user_id,
        plan_tier=candidate.plan_tier,
        billing_cycle=candidate.plan_billing_cycle,
        segment="candidate",
    )
