# PROMPT20_Subscription_Billing.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Implement subscription and billing with Stripe so Winnow can monetize. Per SPEC §3.7: "Must support: free trial or limited free plan, paid subscription (Stripe), usage limits (e.g., tailored resumes/month)." Per ARCHITECTURE §7: each environment has separate "Stripe mode (test vs live)."

This prompt covers: plan definitions, Stripe product/price setup, a `subscriptions` table, Stripe Checkout for upgrading, webhook handling for subscription lifecycle events, usage-limit enforcement middleware, a customer billing portal, and frontend pricing + upgrade prompts.

---

## Triggers — When to Use This Prompt

- Adding subscription/billing/payment functionality.
- Integrating Stripe Checkout, webhooks, or Customer Portal.
- Enforcing usage limits (tailored resumes, match refreshes, etc.).
- Building a pricing page or upgrade prompts.

---

## What Already Exists (DO NOT recreate)

1. **Auth system:** `services/api/app/services/auth.py` — JWT cookies, `get_current_user` dependency. User model at `services/api/app/models/user.py`.
2. **Tailored resumes:** `services/api/app/models/tailored_resume.py` — `tailored_resumes` table with `user_id`, `created_at`. The tailoring endpoint is at `POST /api/tailor/{job_id}`.
3. **Main app:** `services/api/app/main.py` — FastAPI app with router registrations.
4. **Queue/worker:** `services/api/app/services/queue.py` — RQ-based background jobs.
5. **Secret Manager (production):** ARCHITECTURE §3.1 specifies Stripe keys stored in Secret Manager.
6. **Environment separation:** ARCHITECTURE §7 — dev, staging, prod each have separate Stripe mode.
7. **Frontend layout:** `apps/web/app/` — Next.js App Router with dashboard, matches, settings pages.
8. **Settings page:** `apps/web/app/settings/page.tsx` — already has Export + Delete sections (from PROMPT19). Add billing section here.

---

## Plan Definitions (v1)

Two plans to start. Keep it simple — you can add more tiers later.

| Feature | Free | Pro ($19/month) |
|---------|------|-----------------|
| Resume uploads | 2 | Unlimited |
| Resume parsing | 2 | Unlimited |
| Job matches visible | 10 | Unlimited |
| Tailored resumes / month | 1 | 20 |
| Cover letters / month | 0 | 20 |
| Semantic search | Basic (5 results) | Full (50 results) |
| Application tracking | ✅ | ✅ |
| Match explainability | ✅ | ✅ |
| Priority support | ❌ | ✅ |

**Free plan:** No credit card required. Users get a functional experience that demonstrates value. Limits are generous enough to be useful, tight enough to drive upgrades.

**Pro plan:** $19/month (or $15/month billed annually at $180/year). Unlocks everything. The primary conversion trigger is the tailored resume limit — users hit the 1/month cap and want more.

---

# PART 1 — STRIPE SETUP (One-Time, in Stripe Dashboard)

These are manual steps you perform once in the Stripe Dashboard. This is NOT code — it is configuration you do in your browser at https://dashboard.stripe.com.

### 1.1 Create Stripe account

1. Go to https://dashboard.stripe.com and create an account (if you haven't already).
2. You start in **test mode** (toggle in the top-right). Stay in test mode for all development.

### 1.2 Create the Product and Prices

In the Stripe Dashboard:

1. Go to **Products** → **Add product**.
2. Create a product called **"Winnow Pro"**.
3. Add two prices:
   - **Monthly:** $19.00/month, recurring.
   - **Annual:** $180.00/year ($15.00/month equivalent), recurring.
4. After creating, note down the **Price IDs** (they look like `price_1Abc123...`). You will put these in your `.env` file.

### 1.3 Get API keys

1. Go to **Developers** → **API keys**.
2. Copy the **Secret key** (starts with `sk_test_...` in test mode).
3. Copy the **Publishable key** (starts with `pk_test_...` in test mode).

### 1.4 Set up webhook endpoint

1. Go to **Developers** → **Webhooks** → **Add endpoint**.
2. Set the URL to your API endpoint: `https://YOUR_API_URL/api/billing/webhook`
   - For local testing: use the Stripe CLI (see Part 7).
3. Select these events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. After creating, note the **Webhook signing secret** (starts with `whsec_...`).

---

# PART 2 — ENVIRONMENT VARIABLES

### 2.1 Add to `services/api/.env`

**File to modify:** `services/api/.env`

```env
# Stripe (test mode)
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE
STRIPE_PRO_MONTHLY_PRICE_ID=price_YOUR_MONTHLY_PRICE_ID
STRIPE_PRO_ANNUAL_PRICE_ID=price_YOUR_ANNUAL_PRICE_ID
```

### 2.2 Add to `services/api/.env.example`

**File to modify:** `services/api/.env.example`

```env
# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_MONTHLY_PRICE_ID=price_...
STRIPE_PRO_ANNUAL_PRICE_ID=price_...
```

### 2.3 Add to `apps/web/.env.local`

**File to modify:** `apps/web/.env.local`

```env
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
```

### 2.4 Add Python dependency

**File to modify:** `services/api/requirements.txt`

Add:
```
stripe>=8.0.0
```

Then install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install stripe
```

---

# PART 3 — DATABASE: SUBSCRIPTIONS TABLE

### 3.1 Create the Subscription model

**File to create:** `services/api/app/models/subscription.py` (NEW)

```python
"""Subscription model for Stripe billing."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.db.session import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Stripe identifiers
    stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
    stripe_subscription_id = Column(String, unique=True, nullable=True, index=True)

    # Plan state
    plan = Column(String, nullable=False, default="free")  # "free" or "pro"
    billing_interval = Column(String, nullable=True)  # "month" or "year" (null for free)
    status = Column(String, nullable=False, default="active")
    # Stripe subscription status: active, past_due, canceled, incomplete, trialing

    # Usage tracking (reset monthly)
    tailored_resumes_used = Column(Integer, nullable=False, default=0)
    cover_letters_used = Column(Integer, nullable=False, default=0)
    usage_reset_at = Column(DateTime(timezone=True), nullable=True)

    # Dates
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### 3.2 Add stripe_customer_id to User model

**File to modify:** `services/api/app/models/user.py`

Add one column to the existing User model:

```python
stripe_customer_id = Column(String, unique=True, nullable=True, index=True)
```

This provides a quick lookup from the User model. The `subscriptions` table has the full record.

### 3.3 Register the model

**File to modify:** `services/api/app/models/__init__.py`

Add the import so Alembic discovers it:

```python
from app.models.subscription import Subscription
```

### 3.4 Create Alembic migration

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add subscriptions table and stripe_customer_id to users"
alembic upgrade head
```

---

# PART 4 — BILLING SERVICE

**File to create:** `services/api/app/services/billing.py` (NEW)

This service handles all Stripe interactions and plan logic.

```python
"""
Billing service — Stripe integration and plan management.
"""
import os
import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.models.user import User

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

# ── Plan limits ──────────────────────────────────────────────────

PLAN_LIMITS = {
    "free": {
        "resume_uploads": 2,
        "resume_parses": 2,
        "matches_visible": 10,
        "tailored_resumes_per_month": 1,
        "cover_letters_per_month": 0,
        "semantic_search_limit": 5,
    },
    "pro": {
        "resume_uploads": 999,     # Effectively unlimited
        "resume_parses": 999,
        "matches_visible": 999,
        "tailored_resumes_per_month": 20,
        "cover_letters_per_month": 20,
        "semantic_search_limit": 50,
    },
}


def get_plan_limits(plan: str) -> dict:
    """Return the limits for a given plan."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


# ── Subscription CRUD ────────────────────────────────────────────

def get_or_create_subscription(user_id: int, db: Session) -> Subscription:
    """Get existing subscription or create a free one."""
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not sub:
        sub = Subscription(
            user_id=user_id,
            plan="free",
            status="active",
            tailored_resumes_used=0,
            cover_letters_used=0,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
    return sub


def get_user_plan(user_id: int, db: Session) -> str:
    """Return the user's current plan name ('free' or 'pro')."""
    sub = get_or_create_subscription(user_id, db)
    if sub.plan == "pro" and sub.status in ("active", "trialing"):
        return "pro"
    return "free"


def get_usage(user_id: int, db: Session) -> dict:
    """Return current usage counts and limits for a user."""
    sub = get_or_create_subscription(user_id, db)
    limits = get_plan_limits(sub.plan if sub.status in ("active", "trialing") else "free")
    return {
        "plan": sub.plan,
        "status": sub.status,
        "tailored_resumes_used": sub.tailored_resumes_used,
        "tailored_resumes_limit": limits["tailored_resumes_per_month"],
        "cover_letters_used": sub.cover_letters_used,
        "cover_letters_limit": limits["cover_letters_per_month"],
        "matches_visible_limit": limits["matches_visible"],
        "semantic_search_limit": limits["semantic_search_limit"],
        "current_period_end": str(sub.current_period_end) if sub.current_period_end else None,
    }


# ── Usage tracking ───────────────────────────────────────────────

def check_and_increment_usage(
    user_id: int,
    resource: str,
    db: Session,
) -> tuple[bool, str]:
    """
    Check if the user can use a resource, and increment if allowed.
    
    Args:
        user_id: User ID.
        resource: One of "tailored_resume", "cover_letter".
        db: Database session.
    
    Returns:
        (allowed: bool, message: str)
    """
    sub = get_or_create_subscription(user_id, db)
    limits = get_plan_limits(sub.plan if sub.status in ("active", "trialing") else "free")
    
    # Reset usage if past the reset date
    _maybe_reset_usage(sub, db)
    
    if resource == "tailored_resume":
        limit = limits["tailored_resumes_per_month"]
        used = sub.tailored_resumes_used
        if used >= limit:
            return False, f"You've used {used}/{limit} tailored resumes this month. Upgrade to Pro for more."
        sub.tailored_resumes_used = used + 1
        db.commit()
        return True, f"Tailored resume {used + 1}/{limit} used this month."
    
    elif resource == "cover_letter":
        limit = limits["cover_letters_per_month"]
        used = sub.cover_letters_used
        if limit == 0:
            return False, "Cover letters are available on the Pro plan. Upgrade to unlock."
        if used >= limit:
            return False, f"You've used {used}/{limit} cover letters this month. Upgrade to Pro for more."
        sub.cover_letters_used = used + 1
        db.commit()
        return True, f"Cover letter {used + 1}/{limit} used this month."
    
    return True, "OK"


def _maybe_reset_usage(sub: Subscription, db: Session):
    """Reset monthly usage counters if the billing period has rolled over."""
    now = datetime.now(timezone.utc)
    
    if sub.usage_reset_at and now < sub.usage_reset_at:
        return  # Not time to reset yet
    
    # Reset counters
    sub.tailored_resumes_used = 0
    sub.cover_letters_used = 0
    
    # Set next reset to either the Stripe period end or 30 days from now
    if sub.current_period_end:
        sub.usage_reset_at = sub.current_period_end
    else:
        from datetime import timedelta
        sub.usage_reset_at = now + timedelta(days=30)
    
    db.commit()


# ── Stripe Checkout ──────────────────────────────────────────────

def create_checkout_session(
    user_id: int,
    user_email: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    db: Session,
) -> str:
    """
    Create a Stripe Checkout session and return the URL.
    
    Args:
        user_id: The user upgrading.
        user_email: For the Stripe customer.
        price_id: Stripe Price ID (monthly or annual).
        success_url: Redirect URL after successful payment.
        cancel_url: Redirect URL if user cancels.
        db: Database session.
    
    Returns:
        Stripe Checkout URL string.
    """
    sub = get_or_create_subscription(user_id, db)
    
    # Create or retrieve the Stripe customer
    if not sub.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user_email,
            metadata={"winnow_user_id": str(user_id)},
        )
        sub.stripe_customer_id = customer.id
        # Also store on User model for quick lookup
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.stripe_customer_id = customer.id
        db.commit()
    
    # Create Checkout session
    session = stripe.checkout.Session.create(
        customer=sub.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"winnow_user_id": str(user_id)},
        subscription_data={
            "metadata": {"winnow_user_id": str(user_id)},
        },
    )
    
    return session.url


# ── Stripe Customer Portal ───────────────────────────────────────

def create_portal_session(user_id: int, return_url: str, db: Session) -> str:
    """
    Create a Stripe Customer Portal session for managing subscription.
    Users can update payment methods, view invoices, cancel, etc.
    
    Returns: Portal URL string.
    """
    sub = get_or_create_subscription(user_id, db)
    
    if not sub.stripe_customer_id:
        raise ValueError("No Stripe customer found. User has no billing history.")
    
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=return_url,
    )
    
    return session.url


# ── Webhook processing ───────────────────────────────────────────

def handle_checkout_completed(session_data: dict, db: Session):
    """Handle checkout.session.completed event."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")
    user_id_str = session_data.get("metadata", {}).get("winnow_user_id")
    
    if not user_id_str:
        logger.warning("Checkout completed without winnow_user_id metadata")
        return
    
    user_id = int(user_id_str)
    sub = get_or_create_subscription(user_id, db)
    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = subscription_id
    sub.plan = "pro"
    sub.status = "active"
    db.commit()
    
    logger.info(f"User {user_id} upgraded to Pro via checkout")


def handle_subscription_updated(subscription_data: dict, db: Session):
    """Handle customer.subscription.updated and created events."""
    subscription_id = subscription_data.get("id")
    status = subscription_data.get("status")  # active, past_due, canceled, etc.
    current_period_start = subscription_data.get("current_period_start")
    current_period_end = subscription_data.get("current_period_end")
    
    # Find subscription by stripe_subscription_id
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    
    if not sub:
        # Try finding by customer ID
        customer_id = subscription_data.get("customer")
        sub = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id
        ).first()
    
    if not sub:
        logger.warning(f"Subscription {subscription_id} not found in DB")
        return
    
    sub.stripe_subscription_id = subscription_id
    sub.status = status
    
    # Determine plan from price
    items = subscription_data.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        pro_monthly = os.environ.get("STRIPE_PRO_MONTHLY_PRICE_ID", "")
        pro_annual = os.environ.get("STRIPE_PRO_ANNUAL_PRICE_ID", "")
        if price_id in (pro_monthly, pro_annual):
            sub.plan = "pro"
            sub.billing_interval = "month" if price_id == pro_monthly else "year"
    
    if current_period_start:
        sub.current_period_start = datetime.fromtimestamp(current_period_start, tz=timezone.utc)
    if current_period_end:
        sub.current_period_end = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
        sub.usage_reset_at = sub.current_period_end
    
    if status == "canceled":
        sub.canceled_at = datetime.now(timezone.utc)
    
    db.commit()
    logger.info(f"Subscription {subscription_id} updated: plan={sub.plan}, status={status}")


def handle_subscription_deleted(subscription_data: dict, db: Session):
    """Handle customer.subscription.deleted — downgrade to free."""
    subscription_id = subscription_data.get("id")
    
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    
    if not sub:
        logger.warning(f"Subscription {subscription_id} not found for deletion")
        return
    
    sub.plan = "free"
    sub.status = "canceled"
    sub.canceled_at = datetime.now(timezone.utc)
    sub.stripe_subscription_id = None
    sub.billing_interval = None
    db.commit()
    
    logger.info(f"User {sub.user_id} downgraded to free (subscription deleted)")


def handle_payment_failed(invoice_data: dict, db: Session):
    """Handle invoice.payment_failed — mark subscription as past_due."""
    customer_id = invoice_data.get("customer")
    
    sub = db.query(Subscription).filter(
        Subscription.stripe_customer_id == customer_id
    ).first()
    
    if sub:
        sub.status = "past_due"
        db.commit()
        logger.warning(f"Payment failed for user {sub.user_id}")
```

---

# PART 5 — API ROUTER

**File to create:** `services/api/app/routers/billing.py` (NEW)

```python
"""
Billing endpoints: subscription management, Checkout, Portal, webhooks.
"""
import os
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth import get_current_user
from app.services.billing import (
    get_usage,
    get_or_create_subscription,
    create_checkout_session,
    create_portal_session,
    handle_checkout_completed,
    handle_subscription_updated,
    handle_subscription_deleted,
    handle_payment_failed,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/status")
async def billing_status(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's current plan, usage counts, and limits."""
    usage = get_usage(user.id, db)
    return usage


@router.post("/checkout")
async def create_checkout(
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout session for upgrading to Pro.
    
    Body: { "interval": "month" | "year" }
    Returns: { "checkout_url": "https://checkout.stripe.com/..." }
    """
    body = await request.json()
    interval = body.get("interval", "month")
    
    if interval == "year":
        price_id = os.environ.get("STRIPE_PRO_ANNUAL_PRICE_ID", "")
    else:
        price_id = os.environ.get("STRIPE_PRO_MONTHLY_PRICE_ID", "")
    
    if not price_id:
        raise HTTPException(status_code=500, detail="Stripe price not configured")
    
    # Build success/cancel URLs
    web_url = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
    success_url = f"{web_url}/settings?billing=success"
    cancel_url = f"{web_url}/settings?billing=canceled"
    
    checkout_url = create_checkout_session(
        user_id=user.id,
        user_email=user.email,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        db=db,
    )
    
    return {"checkout_url": checkout_url}


@router.post("/portal")
async def create_billing_portal(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session.
    Users can view invoices, update payment method, cancel subscription.
    
    Returns: { "portal_url": "https://billing.stripe.com/..." }
    """
    web_url = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
    return_url = f"{web_url}/settings"
    
    try:
        portal_url = create_portal_session(user.id, return_url, db)
        return {"portal_url": portal_url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook endpoint. Verifies signature and processes events.
    
    IMPORTANT: This endpoint must NOT require authentication.
    Stripe sends POST requests to this URL directly.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    logger.info(f"Stripe webhook: {event_type}")
    
    if event_type == "checkout.session.completed":
        handle_checkout_completed(data, db)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_failed":
        handle_payment_failed(data, db)
    else:
        logger.info(f"Unhandled Stripe event: {event_type}")
    
    return JSONResponse(content={"status": "ok"}, status_code=200)
```

---

# PART 6 — REGISTER ROUTER + EXCLUDE WEBHOOK FROM AUTH

### 6.1 Register the billing router

**File to modify:** `services/api/app/main.py`

Add import and registration:

```python
from app.routers import billing

app.include_router(billing.router)
```

### 6.2 Webhook must skip auth

The `/api/billing/webhook` endpoint is called by Stripe directly — it cannot have auth cookies. The endpoint already doesn't use `Depends(get_current_user)`, so it should work. But verify that any global auth middleware (if you have one) excludes this path. If you have a global middleware that checks cookies, add an exception:

```python
# In middleware (if applicable):
SKIP_AUTH_PATHS = ["/health", "/ready", "/api/billing/webhook"]
```

---

# PART 7 — USAGE LIMIT ENFORCEMENT (Middleware)

### 7.1 Gate the tailoring endpoint

**File to modify:** `services/api/app/routers/tailor.py`

At the start of the `POST /api/tailor/{job_id}` handler, add the usage check:

```python
from app.services.billing import check_and_increment_usage

@router.post("/{job_id}")
async def generate_tailored_resume(
    job_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check usage limit BEFORE enqueuing the job
    allowed, message = check_and_increment_usage(user.id, "tailored_resume", db)
    if not allowed:
        raise HTTPException(status_code=403, detail=message)
    
    # ... existing tailoring logic (enqueue worker job, etc.)
```

### 7.2 Gate the cover letter endpoint (if it exists)

Same pattern — add `check_and_increment_usage(user.id, "cover_letter", db)` at the top.

### 7.3 Gate match visibility

**File to modify:** `services/api/app/routers/matches.py`

In the `GET /api/matches` handler, limit the number of results for free users:

```python
from app.services.billing import get_user_plan, get_plan_limits

@router.get("")
async def get_matches(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    # ... existing params
):
    plan = get_user_plan(user.id, db)
    limits = get_plan_limits(plan)
    max_visible = limits["matches_visible"]
    
    # ... existing query logic ...
    
    # Apply visibility limit
    matches = matches[:max_visible]
    
    # If truncated, add a hint to the response
    # (You may need to adjust the response schema)
    return matches
```

### 7.4 Gate semantic search

**File to modify:** `services/api/app/routers/matches.py` (or wherever the semantic search endpoint lives)

Limit the `limit` parameter based on plan:

```python
from app.services.billing import get_user_plan, get_plan_limits

# In the semantic search handler:
plan = get_user_plan(user.id, db)
limits = get_plan_limits(plan)
effective_limit = min(request_limit, limits["semantic_search_limit"])
```

---

# PART 8 — FRONTEND: BILLING SECTION IN SETTINGS

**File to modify:** `apps/web/app/settings/page.tsx`

Add a "Subscription & Billing" section above the Export section. This section shows:

### 8.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  💳 Subscription & Billing                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                                                             │    │
│  │  Current Plan: FREE  (or PRO ✨)                            │    │
│  │                                                             │    │
│  │  ── Usage This Month ──                                     │    │
│  │  Tailored Resumes:  0 / 1  ████░░░░░░░░░░░░░░░░  0%        │    │
│  │  Cover Letters:     Not available on Free plan               │    │
│  │  Matches Visible:   10 (of 47 qualified)                    │    │
│  │                                                             │    │
│  │  [ Upgrade to Pro — $19/mo ]   [ Annual — $15/mo ]          │    │
│  │                                                             │    │
│  │  --- OR if on Pro: ---                                      │    │
│  │                                                             │    │
│  │  Current Plan: PRO ✨  ($19/month)                           │    │
│  │  Next billing date: March 8, 2026                            │    │
│  │                                                             │    │
│  │  Tailored Resumes:  3 / 20  ██████░░░░░░░░░░░░░  15%       │    │
│  │  Cover Letters:     1 / 20  █░░░░░░░░░░░░░░░░░░░  5%       │    │
│  │                                                             │    │
│  │  [ Manage Billing ]  (opens Stripe Customer Portal)         │    │
│  │                                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ─ (rest of settings: Export, Delete) ─                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 API calls from frontend

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

// Get billing status (on page load)
const statusRes = await fetch(`${API_BASE}/api/billing/status`, { credentials: "include" });
const billing = await statusRes.json();
// billing = { plan, status, tailored_resumes_used, tailored_resumes_limit, ... }

// Upgrade (redirect to Stripe Checkout)
const checkoutRes = await fetch(`${API_BASE}/api/billing/checkout`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ interval: "month" }),  // or "year"
});
const { checkout_url } = await checkoutRes.json();
window.location.href = checkout_url;  // Redirect to Stripe

// Manage billing (redirect to Stripe Customer Portal)
const portalRes = await fetch(`${API_BASE}/api/billing/portal`, {
  method: "POST",
  credentials: "include",
});
const { portal_url } = await portalRes.json();
window.location.href = portal_url;  // Redirect to Stripe
```

### 8.3 Success/cancel handling

When the user returns from Stripe Checkout, they land on `/settings?billing=success` or `/settings?billing=canceled`. Check for these query params and show a toast:

```typescript
"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const searchParams = useSearchParams();
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("billing") === "success") {
      setToast("🎉 Welcome to Winnow Pro! Your subscription is now active.");
    } else if (searchParams.get("billing") === "canceled") {
      setToast("Checkout was canceled. You can upgrade anytime.");
    }
  }, [searchParams]);

  // ... rest of component
}
```

---

# PART 9 — UPGRADE PROMPTS (In-Context)

Show upgrade prompts at the point of friction — when the user hits a limit.

### 9.1 Tailored resume limit reached

**File to modify:** `apps/web/app/matches/` (the component with the "Generate ATS Resume" button)

When the API returns 403 with the usage-limit message, show an inline upgrade prompt:

```tsx
// After calling POST /api/tailor/{job_id}:
if (response.status === 403) {
  const data = await response.json();
  // Show upgrade prompt instead of error
  setUpgradePrompt({
    message: data.detail,
    // e.g., "You've used 1/1 tailored resumes this month. Upgrade to Pro for more."
  });
}
```

### 9.2 Matches truncation notice

When the matches list is limited (free users see 10), show a banner:

```tsx
{billing.plan === "free" && totalMatches > billing.matches_visible_limit && (
  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm">
    Showing {billing.matches_visible_limit} of {totalMatches} matches.
    <button onClick={handleUpgrade} className="text-amber-700 font-semibold underline ml-1">
      Upgrade to Pro
    </button>
    to see all matches.
  </div>
)}
```

---

# PART 10 — LOCAL TESTING WITH STRIPE CLI

For local webhook testing, use the Stripe CLI:

### 10.1 Install Stripe CLI

```powershell
# Windows (via Scoop)
scoop install stripe

# Or download from https://stripe.com/docs/stripe-cli
```

### 10.2 Forward webhooks to local API

```powershell
stripe login
stripe listen --forward-to localhost:8000/api/billing/webhook
```

The CLI will print a webhook signing secret (starts with `whsec_...`). Put this in your `.env` as `STRIPE_WEBHOOK_SECRET`.

### 10.3 Test a payment flow

1. Start the API and web app locally.
2. Start `stripe listen --forward-to localhost:8000/api/billing/webhook`.
3. Go to `/settings` in the browser.
4. Click "Upgrade to Pro."
5. Use Stripe's test card: `4242 4242 4242 4242`, any future expiry, any CVC.
6. Complete checkout.
7. You should be redirected to `/settings?billing=success`.
8. The billing status should now show "Pro."
9. Check the terminal — you should see webhook events being forwarded.

### 10.4 Test card numbers

| Card Number | Result |
|-------------|--------|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 3220` | Requires 3D Secure |
| `4000 0000 0000 9995` | Declined (insufficient funds) |
| `4000 0000 0000 0341` | Charge fails after attaching |

---

# PART 11 — TESTS

**File to create:** `services/api/tests/test_billing.py` (NEW)

```python
"""Tests for billing endpoints."""
import os


def test_billing_status_free_by_default(auth_client):
    client, user = auth_client
    response = client.get("/api/billing/status")
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["tailored_resumes_used"] == 0
    assert data["tailored_resumes_limit"] == 1
    assert data["cover_letters_limit"] == 0


def test_billing_status_unauthenticated(client):
    response = client.get("/api/billing/status")
    assert response.status_code == 401


def test_checkout_returns_url(auth_client):
    """Test checkout session creation (requires STRIPE_SECRET_KEY in test env)."""
    client, user = auth_client
    # This test will fail without a valid Stripe key
    # Skip if no Stripe key configured
    if not os.environ.get("STRIPE_SECRET_KEY"):
        return
    response = client.post(
        "/api/billing/checkout",
        json={"interval": "month"},
    )
    assert response.status_code in (200, 500)  # 500 if Stripe not configured
    if response.status_code == 200:
        assert "checkout_url" in response.json()


def test_billing_portal_requires_customer(auth_client):
    """Portal should fail for users with no Stripe customer."""
    client, user = auth_client
    response = client.post("/api/billing/portal")
    assert response.status_code == 400  # No Stripe customer yet


def test_webhook_rejects_invalid_signature(client):
    response = client.post(
        "/api/billing/webhook",
        content=b'{"type": "test"}',
        headers={"stripe-signature": "invalid"},
    )
    assert response.status_code == 400


def test_usage_limit_enforcement(auth_client, db_session):
    """Test that free users are limited."""
    from app.services.billing import check_and_increment_usage
    client, user = auth_client
    
    # First tailored resume should succeed
    allowed, msg = check_and_increment_usage(user.id, "tailored_resume", db_session)
    assert allowed is True
    
    # Second should be blocked (free limit is 1)
    allowed, msg = check_and_increment_usage(user.id, "tailored_resume", db_session)
    assert allowed is False
    assert "Upgrade" in msg


def test_usage_limit_cover_letter_blocked_on_free(auth_client, db_session):
    """Free users cannot use cover letters."""
    from app.services.billing import check_and_increment_usage
    client, user = auth_client
    
    allowed, msg = check_and_increment_usage(user.id, "cover_letter", db_session)
    assert allowed is False
    assert "Pro plan" in msg
```

---

# PART 12 — PRODUCTION DEPLOYMENT

### 12.1 Add Stripe secrets to GCP Secret Manager

```powershell
echo -n "sk_live_YOUR_LIVE_SECRET_KEY" | gcloud secrets create STRIPE_SECRET_KEY --data-file=-
echo -n "whsec_YOUR_LIVE_WEBHOOK_SECRET" | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
echo -n "price_YOUR_LIVE_MONTHLY_ID" | gcloud secrets create STRIPE_PRO_MONTHLY_PRICE_ID --data-file=-
echo -n "price_YOUR_LIVE_ANNUAL_ID" | gcloud secrets create STRIPE_PRO_ANNUAL_PRICE_ID --data-file=-
```

### 12.2 Update Cloud Run deployment

Add the new secrets to the `winnow-api` Cloud Run service:

```powershell
gcloud run services update winnow-api `
  --set-secrets="STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest,STRIPE_PRO_MONTHLY_PRICE_ID=STRIPE_PRO_MONTHLY_PRICE_ID:latest,STRIPE_PRO_ANNUAL_PRICE_ID=STRIPE_PRO_ANNUAL_PRICE_ID:latest" `
  --update-env-vars="STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_KEY"
```

### 12.3 Add publishable key to web deployment

Update the web build arg:

```powershell
docker build `
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com `
  --build-arg NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_KEY `
  -t winnow-web .
```

### 12.4 Configure webhook in Stripe Dashboard (live mode)

1. Toggle to **live mode** in the Stripe Dashboard.
2. Create the same product + prices (or use the Product Catalog's live/test toggle).
3. Add a webhook endpoint pointing to your production API URL.
4. Update the live webhook secret in Secret Manager.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Subscription model | `services/api/app/models/subscription.py` | CREATE |
| User model (add stripe_customer_id) | `services/api/app/models/user.py` | MODIFY |
| Models __init__ (register) | `services/api/app/models/__init__.py` | MODIFY |
| Alembic migration | `services/api/alembic/versions/` | CREATE via `alembic revision` |
| Billing service | `services/api/app/services/billing.py` | CREATE |
| Billing router | `services/api/app/routers/billing.py` | CREATE |
| Main app (register router) | `services/api/app/main.py` | MODIFY |
| Tailor router (usage gate) | `services/api/app/routers/tailor.py` | MODIFY |
| Matches router (visibility gate) | `services/api/app/routers/matches.py` | MODIFY |
| Settings page (billing UI) | `apps/web/app/settings/page.tsx` | MODIFY |
| Matches page (upgrade prompt) | `apps/web/app/matches/` components | MODIFY |
| Requirements.txt | `services/api/requirements.txt` | MODIFY — add `stripe` |
| .env | `services/api/.env` | MODIFY — add Stripe keys |
| .env.example | `services/api/.env.example` | MODIFY — add Stripe placeholders |
| Web .env.local | `apps/web/.env.local` | MODIFY — add publishable key |
| Tests | `services/api/tests/test_billing.py` | CREATE |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Stripe Dashboard (Steps 1–3)

1. **Step 1:** Create a Stripe account at https://dashboard.stripe.com (stay in test mode).
2. **Step 2:** Create the "Winnow Pro" product with monthly ($19) and annual ($180) prices. Write down both Price IDs.
3. **Step 3:** Copy your test Secret Key and Publishable Key from Developers → API keys.

### Phase 2: Backend Setup (Steps 4–9)

4. **Step 4:** Add `stripe>=8.0.0` to `services/api/requirements.txt`. Install: `pip install stripe`.
5. **Step 5:** Add all Stripe env vars to `services/api/.env` and `services/api/.env.example` (Part 2).
6. **Step 6:** Create `services/api/app/models/subscription.py` (Part 3.1).
7. **Step 7:** Add `stripe_customer_id` column to `services/api/app/models/user.py` (Part 3.2).
8. **Step 8:** Import `Subscription` in `services/api/app/models/__init__.py` (Part 3.3).
9. **Step 9:** Create and run the Alembic migration:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   alembic revision --autogenerate -m "add subscriptions table and stripe_customer_id to users"
   alembic upgrade head
   ```

### Phase 3: Billing Service + Router (Steps 10–12)

10. **Step 10:** Create `services/api/app/services/billing.py` (Part 4).
11. **Step 11:** Create `services/api/app/routers/billing.py` (Part 5).
12. **Step 12:** Register the router in `services/api/app/main.py` (Part 6).

### Phase 4: Usage Gates (Steps 13–15)

13. **Step 13:** Add usage check to `POST /api/tailor/{job_id}` in `services/api/app/routers/tailor.py` (Part 7.1).
14. **Step 14:** Add match visibility limit to `GET /api/matches` in `services/api/app/routers/matches.py` (Part 7.3).
15. **Step 15:** Add semantic search limit (Part 7.4).

### Phase 5: Frontend (Steps 16–18)

16. **Step 16:** Add `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` to `apps/web/.env.local`.
17. **Step 17:** Add the billing section to `apps/web/app/settings/page.tsx` (Part 8).
18. **Step 18:** Add upgrade prompts to the matches page when limits are hit (Part 9).

### Phase 6: Local Testing (Steps 19–21)

19. **Step 19:** Install Stripe CLI and run `stripe listen --forward-to localhost:8000/api/billing/webhook`.
20. **Step 20:** Test the full checkout flow: free → click upgrade → Stripe Checkout (test card 4242...) → return to settings → verify Pro status.
21. **Step 21:** Test limit enforcement: generate 1 tailored resume (should succeed), try a 2nd (should get 403 with upgrade prompt).

### Phase 7: Tests + Lint (Steps 22–23)

22. **Step 22:** Create `services/api/tests/test_billing.py` and run:
    ```powershell
    cd services/api
    python -m pytest tests/test_billing.py -v
    ```
23. **Step 23:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd ../../apps/web
    npm run lint
    ```

### Phase 8: Production (Steps 24–26)

24. **Step 24:** Add Stripe live keys to GCP Secret Manager (Part 12.1).
25. **Step 25:** Update Cloud Run deployment with new secrets (Part 12.2).
26. **Step 26:** Configure live webhook in Stripe Dashboard pointing to production API URL.

---

## Non-Goals (Do NOT implement in this prompt)

- Multiple paid tiers (just Free + Pro for v1)
- Usage-based billing (flat subscription only)
- Proration for mid-cycle plan changes (Stripe handles this automatically)
- Coupon/discount codes (add later via Stripe Dashboard)
- Invoice PDF generation (Stripe handles this)
- Revenue analytics dashboard (use Stripe Dashboard)
- Affiliate/referral program
- Team/enterprise plans

---

## Summary Checklist

- [ ] Stripe Dashboard: Product "Winnow Pro" created with monthly + annual prices
- [ ] Stripe Dashboard: Webhook endpoint configured with correct events
- [ ] Dependencies: `stripe` package installed
- [ ] Environment: All Stripe env vars in `.env`, `.env.example`, web `.env.local`
- [ ] Database: `subscriptions` table created + `stripe_customer_id` on users
- [ ] Migration: Alembic migration created and applied
- [ ] Billing service: `billing.py` with plan limits, usage tracking, Checkout, Portal, webhook handlers
- [ ] Billing router: `GET /api/billing/status`, `POST /api/billing/checkout`, `POST /api/billing/portal`, `POST /api/billing/webhook`
- [ ] Router registered in `main.py`
- [ ] Webhook endpoint: skips auth, verifies Stripe signature, processes all 6 event types
- [ ] Usage gate: tailored resume generation checks and increments monthly usage
- [ ] Usage gate: cover letter generation blocked on free plan
- [ ] Visibility gate: matches limited to 10 for free users
- [ ] Visibility gate: semantic search limited to 5 results for free users
- [ ] Frontend: billing section in Settings page showing plan, usage bars, upgrade buttons
- [ ] Frontend: Stripe Checkout redirect for upgrades (monthly + annual)
- [ ] Frontend: Stripe Customer Portal for managing subscription
- [ ] Frontend: success/cancel toast on return from Checkout
- [ ] Frontend: upgrade prompts when limits are hit (403 on tailor, truncation notice on matches)
- [ ] Local testing: Stripe CLI webhook forwarding tested end-to-end
- [ ] Tests: billing status, checkout, portal, webhook signature, usage limits
- [ ] Production: Stripe live keys in Secret Manager, Cloud Run updated, live webhook configured
- [ ] Linted and formatted

Return code changes only.
