"""Stripe billing service for employer subscriptions."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employer import EmployerProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_EMPLOYER_WEBHOOK_SECRET", "") or os.getenv(
    "STRIPE_WEBHOOK_SECRET", ""
)
STRIPE_PRICE_EMPLOYER_STARTER = os.getenv("STRIPE_PRICE_EMPLOYER_STARTER_MO", "")
STRIPE_PRICE_EMPLOYER_PRO = os.getenv("STRIPE_PRICE_EMPLOYER_PRO_MO", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

TIER_PRICE_MAP = {
    "starter": STRIPE_PRICE_EMPLOYER_STARTER,
    "pro": STRIPE_PRICE_EMPLOYER_PRO,
}


def _stripe_client():
    """Return a configured Stripe client. Raises 503 if key is missing."""
    import stripe

    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")
    return stripe.StripeClient(STRIPE_SECRET_KEY)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------


def get_or_create_stripe_customer(
    session: Session, employer: EmployerProfile, email: str
) -> str:
    """Return or create a Stripe customer for this employer."""
    if employer.stripe_customer_id:
        return employer.stripe_customer_id

    client = _stripe_client()
    customer = client.customers.create(
        params={
            "email": employer.billing_email or email,
            "name": employer.company_name,
            "metadata": {"employer_id": str(employer.id), "platform": "winnow"},
        }
    )
    employer.stripe_customer_id = customer.id
    session.flush()
    return customer.id


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


def create_checkout_session(
    session: Session,
    employer: EmployerProfile,
    email: str,
    tier: str,
) -> str:
    """Create a Stripe Checkout session for an employer subscription upgrade."""
    price_id = TIER_PRICE_MAP.get(tier)

    # Dev mode: when Stripe is not configured, directly upgrade the tier and
    # return the success URL.  Without a webhook secret, Stripe checkout would
    # succeed but the tier would never get updated.
    if not price_id or not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        employer.subscription_tier = tier
        employer.subscription_status = "active"
        session.flush()
        logger.info(
            "Dev mode: upgraded employer %s to %s (no Stripe configured)",
            employer.id,
            tier,
        )
        return f"{FRONTEND_URL}/employer/settings?billing=success"

    customer_id = get_or_create_stripe_customer(session, employer, email)
    client = _stripe_client()

    checkout = client.checkout.sessions.create(
        params={
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": (
                f"{FRONTEND_URL}/employer/billing/success"
                f"?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            "cancel_url": f"{FRONTEND_URL}/employer/settings",
            "metadata": {"employer_id": str(employer.id), "tier": tier},
        }
    )
    return checkout.url


# ---------------------------------------------------------------------------
# Portal
# ---------------------------------------------------------------------------


def create_portal_session(
    session: Session, employer: EmployerProfile, email: str
) -> str:
    """Create a Stripe Customer Portal session."""
    customer_id = get_or_create_stripe_customer(session, employer, email)
    client = _stripe_client()
    portal = client.billing_portal.sessions.create(
        params={
            "customer": customer_id,
            "return_url": f"{FRONTEND_URL}/employer/settings",
        }
    )
    return portal.url


# ---------------------------------------------------------------------------
# Subscription details
# ---------------------------------------------------------------------------


def get_subscription_details(employer: EmployerProfile) -> dict:
    """Get subscription details from Stripe or local state."""
    result = {
        "tier": employer.subscription_tier or "free",
        "status": employer.subscription_status or "active",
        "has_subscription": bool(employer.stripe_subscription_id),
        "current_period_start": None,
        "current_period_end": None,
        "cancel_at_period_end": False,
    }

    if employer.current_period_start:
        result["current_period_start"] = employer.current_period_start.isoformat()
    if employer.current_period_end:
        result["current_period_end"] = employer.current_period_end.isoformat()

    if employer.stripe_subscription_id and STRIPE_SECRET_KEY:
        try:
            client = _stripe_client()
            sub = client.subscriptions.retrieve(employer.stripe_subscription_id)
            result["current_period_start"] = datetime.fromtimestamp(
                sub.current_period_start, tz=UTC
            ).isoformat()
            result["current_period_end"] = datetime.fromtimestamp(
                sub.current_period_end, tz=UTC
            ).isoformat()
            result["cancel_at_period_end"] = sub.cancel_at_period_end
        except Exception:
            logger.warning(
                "Could not fetch Stripe subscription %s",
                employer.stripe_subscription_id,
            )

    return result


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------


def handle_webhook_event(payload: bytes, sig_header: str, session: Session) -> dict:
    """Verify and dispatch a Stripe webhook event for employer subscriptions."""
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
        logger.debug("Unhandled employer Stripe event type: %s", event_type)

    return {"status": "ok"}


def _find_employer_by_stripe_customer(
    session: Session, customer_id: str
) -> EmployerProfile | None:
    return session.execute(
        select(EmployerProfile).where(EmployerProfile.stripe_customer_id == customer_id)
    ).scalar_one_or_none()


def _handle_checkout_completed(checkout_session: object, session: Session) -> None:
    customer_id = getattr(checkout_session, "customer", None)
    subscription_id = getattr(checkout_session, "subscription", None)
    metadata = getattr(checkout_session, "metadata", {}) or {}
    if not customer_id:
        return

    employer = _find_employer_by_stripe_customer(session, customer_id)
    if employer is None:
        logger.warning("No employer for Stripe customer %s", customer_id)
        return

    employer.stripe_subscription_id = subscription_id
    employer.subscription_status = "active"

    # Determine tier from metadata or price
    tier = metadata.get("tier")
    if tier in ("starter", "pro"):
        employer.subscription_tier = tier
    else:
        # Fallback: look up from the subscription price
        if subscription_id:
            try:
                client = _stripe_client()
                sub = client.subscriptions.retrieve(subscription_id)
                price_id = sub.items.data[0].price.id if sub.items.data else None
                if price_id == STRIPE_PRICE_EMPLOYER_STARTER:
                    employer.subscription_tier = "starter"
                elif price_id == STRIPE_PRICE_EMPLOYER_PRO:
                    employer.subscription_tier = "pro"
            except Exception:
                logger.warning(
                    "Could not determine tier for sub %s",
                    subscription_id,
                )

    # Update period dates
    if subscription_id:
        try:
            client = _stripe_client()
            sub = client.subscriptions.retrieve(subscription_id)
            employer.current_period_start = datetime.fromtimestamp(
                sub.current_period_start, tz=UTC
            )
            employer.current_period_end = datetime.fromtimestamp(
                sub.current_period_end, tz=UTC
            )
        except Exception:
            pass

    session.flush()


def _handle_subscription_change(subscription: object, session: Session) -> None:
    customer_id = getattr(subscription, "customer", None)
    status = getattr(subscription, "status", None)
    sub_id = getattr(subscription, "id", None)
    if not customer_id:
        return

    employer = _find_employer_by_stripe_customer(session, customer_id)
    if employer is None:
        return

    employer.stripe_subscription_id = sub_id
    employer.subscription_status = status

    if status in ("canceled", "unpaid"):
        employer.subscription_tier = "free"
    elif status in ("active", "trialing"):
        # Keep existing tier (starter or pro) for active subscriptions
        pass

    # Update period dates
    current_period_start = getattr(subscription, "current_period_start", None)
    current_period_end = getattr(subscription, "current_period_end", None)
    if current_period_start:
        employer.current_period_start = datetime.fromtimestamp(
            current_period_start, tz=UTC
        )
    if current_period_end:
        employer.current_period_end = datetime.fromtimestamp(current_period_end, tz=UTC)

    session.flush()


def _handle_payment_failed(invoice: object, session: Session) -> None:
    customer_id = getattr(invoice, "customer", None)
    if not customer_id:
        return

    employer = _find_employer_by_stripe_customer(session, customer_id)
    if employer is None:
        return

    employer.subscription_status = "past_due"
    session.flush()
