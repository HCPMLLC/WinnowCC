"""Employer billing router — Stripe Checkout, Portal, webhooks, subscription details."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.middleware.rate_limit import limiter
from app.models.employer import EmployerProfile
from app.models.user import User
from app.services.auth import get_current_user, get_employer_profile
from app.services.employer_billing import (
    create_checkout_session,
    create_portal_session,
    get_subscription_details,
    handle_webhook_event,
)

router = APIRouter(prefix="/api/employer/billing", tags=["employer-billing"])


# ---------- Schemas ----------


class CheckoutRequest(BaseModel):
    tier: str  # "starter" or "pro"


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


class SubscriptionResponse(BaseModel):
    tier: str
    status: str
    has_subscription: bool
    current_period_start: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False


# ---------- POST /api/employer/billing/checkout ----------


@router.post("/checkout", response_model=CheckoutResponse)
def employer_billing_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for employer subscription upgrade."""
    if body.tier not in ("starter", "pro"):
        raise HTTPException(
            status_code=400,
            detail="tier must be 'starter' or 'pro'.",
        )

    url = create_checkout_session(session, employer, user.email, body.tier)
    session.commit()
    return CheckoutResponse(url=url)


# ---------- POST /api/employer/billing/portal ----------


@router.post("/portal", response_model=PortalResponse)
def employer_billing_portal(
    user: User = Depends(get_current_user),
    employer: EmployerProfile = Depends(get_employer_profile),
    session: Session = Depends(get_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    if not employer.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer found. Please subscribe first.",
        )

    url = create_portal_session(session, employer, user.email)
    session.commit()
    return PortalResponse(url=url)


# ---------- GET /api/employer/billing/subscription ----------


@router.get("/subscription", response_model=SubscriptionResponse)
def employer_subscription_details(
    employer: EmployerProfile = Depends(get_employer_profile),
) -> SubscriptionResponse:
    """Get current employer subscription details."""
    details = get_subscription_details(employer)
    return SubscriptionResponse(**details)


# ---------- POST /api/employer/billing/webhook ----------


@router.post("/webhook")
@limiter.limit("100/minute")
async def employer_billing_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> dict:
    """Handle Stripe webhook events for employer subscriptions."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = handle_webhook_event(payload, sig_header, session)
    session.commit()
    return result
