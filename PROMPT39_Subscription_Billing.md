# PROMPT 39: Subscription & Billing System (Stripe Integration)

## Objective
Implement Stripe-powered subscription billing for employer tiers with webhooks, payment processing, subscription management, and usage-based limits enforcement. Enable employers to upgrade, downgrade, and manage their billing.

---

## Context
After building the two-sided marketplace (PROMPT33-38), employers are limited to free tier functionality. Now we'll add paid subscriptions so employers can upgrade for more features and you can generate revenue.

**Subscription Tiers:**
- **Free**: $0/mo - 1 job, 10 candidate views/month
- **Starter**: $99/mo - 5 jobs, 50 candidate views/month
- **Pro**: $299/mo - Unlimited jobs, 200 candidate views/month
- **Enterprise**: Custom - Unlimited everything

---

## Prerequisites
- ✅ PROMPT36 completed (employer backend working)
- ✅ PROMPT38 completed (employer frontend working)
- ✅ Stripe account created (https://stripe.com)
- ✅ Stripe API keys obtained (test mode)

---

## Setup Steps

### Step 0: Install Dependencies & Get Stripe Keys

**Terminal Commands:**
```bash
# Backend - install Stripe SDK
cd services/api
pip install stripe --break-system-packages

# Frontend - install Stripe libraries
cd ../../web
npm install @stripe/stripe-js @stripe/react-stripe-js
```

**Get Stripe Keys:**
1. Go to https://dashboard.stripe.com
2. Sign up or log in
3. Get your keys from Developers > API Keys
4. Copy "Publishable key" and "Secret key" (test mode)

**Add to `.env` files:**

`services/api/.env`:
```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # We'll get this later
STRIPE_PRICE_STARTER=price_...   # We'll create these
STRIPE_PRICE_PRO=price_...
```

`web/.env.local`:
```bash
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

---

## Implementation Steps

### Step 1: Create Stripe Products & Prices

**Location:** Stripe Dashboard (https://dashboard.stripe.com/products)

**Instructions:**
1. Go to Products > Add Product
2. Create three products:

**Starter Plan:**
- Name: Winnow Starter
- Description: 5 active jobs, 50 candidate views/month
- Pricing: $99/month (recurring)
- Copy the Price ID (starts with `price_...`)

**Pro Plan:**
- Name: Winnow Pro
- Description: Unlimited jobs, 200 candidate views/month
- Pricing: $299/month (recurring)
- Copy the Price ID

**Enterprise Plan:**
- Name: Winnow Enterprise
- Description: Unlimited everything, dedicated support
- Pricing: Custom (we'll handle separately)

**Update `.env`** with the Price IDs:
```bash
STRIPE_PRICE_STARTER=price_1ABC...
STRIPE_PRICE_PRO=price_2DEF...
```

---

### Step 2: Backend - Stripe Service

**Location:** Create `services/api/app/services/stripe_service.py`

**Code:**
```python
import stripe
from datetime import datetime
from typing import Optional
from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

# Price IDs from environment
PRICE_IDS = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "pro": settings.STRIPE_PRICE_PRO,
}


def create_customer(email: str, name: str) -> str:
    """
    Create a Stripe customer.
    
    Args:
        email: Customer email
        name: Customer name (company name)
    
    Returns:
        Stripe customer ID
    """
    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata={"platform": "winnow"}
    )
    return customer.id


def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Create a Stripe Checkout session for subscription.
    
    Args:
        customer_id: Stripe customer ID
        price_id: Stripe price ID (starter or pro)
        success_url: URL to redirect on success
        cancel_url: URL to redirect on cancel
    
    Returns:
        Checkout session URL
    """
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price": price_id,
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"platform": "winnow"}
    )
    return session.url


def create_portal_session(customer_id: str, return_url: str) -> str:
    """
    Create a customer portal session for managing subscription.
    
    Args:
        customer_id: Stripe customer ID
        return_url: URL to return to after managing subscription
    
    Returns:
        Portal session URL
    """
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def get_subscription(subscription_id: str) -> Optional[dict]:
    """
    Get subscription details from Stripe.
    
    Args:
        subscription_id: Stripe subscription ID
    
    Returns:
        Subscription object or None
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_start": datetime.fromtimestamp(subscription.current_period_start),
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end),
            "cancel_at_period_end": subscription.cancel_at_period_end,
        }
    except stripe.error.StripeError:
        return None


def cancel_subscription(subscription_id: str, immediate: bool = False) -> bool:
    """
    Cancel a subscription.
    
    Args:
        subscription_id: Stripe subscription ID
        immediate: If True, cancel immediately. If False, cancel at period end.
    
    Returns:
        Success boolean
    """
    try:
        if immediate:
            stripe.Subscription.delete(subscription_id)
        else:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        return True
    except stripe.error.StripeError:
        return False


def construct_webhook_event(payload: bytes, signature: str):
    """
    Construct and verify webhook event from Stripe.
    
    Args:
        payload: Request body bytes
        signature: Stripe signature header
    
    Returns:
        Stripe event object
    
    Raises:
        ValueError: If signature verification fails
    """
    return stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )
```

---

### Step 3: Backend - Config Updates

**Location:** `services/api/app/core/config.py`

**What to add:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Stripe settings
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_STARTER: str
    STRIPE_PRICE_PRO: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

### Step 4: Backend - Billing Routes

**Location:** Create `services/api/app/routers/billing.py`

**Code:**
```python
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_employer_profile
from app.models.employer import EmployerProfile
from app.services import stripe_service
from pydantic import BaseModel

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateCheckoutSessionRequest(BaseModel):
    tier: str  # 'starter' or 'pro'
    

class CheckoutSessionResponse(BaseModel):
    url: str


class PortalSessionResponse(BaseModel):
    url: str


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    employer: EmployerProfile = Depends(get_employer_profile),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe Checkout session to upgrade subscription.
    
    Returns redirect URL to Stripe Checkout.
    """
    if request.tier not in ["starter", "pro"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tier. Must be 'starter' or 'pro'"
        )
    
    # Create Stripe customer if doesn't exist
    if not employer.stripe_customer_id:
        customer_id = stripe_service.create_customer(
            email=employer.user.email,
            name=employer.company_name
        )
        employer.stripe_customer_id = customer_id
        db.commit()
    
    # Get price ID for tier
    price_id = stripe_service.PRICE_IDS[request.tier]
    
    # Create checkout session
    checkout_url = stripe_service.create_checkout_session(
        customer_id=employer.stripe_customer_id,
        price_id=price_id,
        success_url=f"{settings.FRONTEND_URL}/employer/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/employer/settings"
    )
    
    return CheckoutSessionResponse(url=checkout_url)


@router.post("/create-portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    employer: EmployerProfile = Depends(get_employer_profile)
):
    """
    Create a Stripe Customer Portal session.
    
    Allows employer to manage subscription, payment methods, invoices.
    """
    if not employer.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Stripe customer found. Please subscribe first."
        )
    
    portal_url = stripe_service.create_portal_session(
        customer_id=employer.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/employer/settings"
    )
    
    return PortalSessionResponse(url=portal_url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    
    Critical events:
    - checkout.session.completed: Subscription created
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription cancelled
    - invoice.payment_failed: Payment failed
    """
    payload = await request.body()
    
    try:
        event = stripe_service.construct_webhook_event(payload, stripe_signature)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle different event types
    if event.type == "checkout.session.completed":
        session = event.data.object
        
        # Get employer by customer ID
        employer = db.query(EmployerProfile).filter(
            EmployerProfile.stripe_customer_id == session.customer
        ).first()
        
        if employer:
            # Update subscription details
            subscription = session.subscription
            employer.stripe_subscription_id = subscription
            
            # Determine tier from price
            price_id = session.line_items.data[0].price.id
            if price_id == stripe_service.PRICE_IDS["starter"]:
                employer.subscription_tier = "starter"
            elif price_id == stripe_service.PRICE_IDS["pro"]:
                employer.subscription_tier = "pro"
            
            employer.subscription_status = "active"
            db.commit()
    
    elif event.type == "customer.subscription.updated":
        subscription = event.data.object
        
        employer = db.query(EmployerProfile).filter(
            EmployerProfile.stripe_subscription_id == subscription.id
        ).first()
        
        if employer:
            employer.subscription_status = subscription.status
            employer.current_period_start = datetime.fromtimestamp(subscription.current_period_start)
            employer.current_period_end = datetime.fromtimestamp(subscription.current_period_end)
            db.commit()
    
    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        
        employer = db.query(EmployerProfile).filter(
            EmployerProfile.stripe_subscription_id == subscription.id
        ).first()
        
        if employer:
            employer.subscription_tier = "free"
            employer.subscription_status = "cancelled"
            db.commit()
    
    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        subscription_id = invoice.subscription
        
        employer = db.query(EmployerProfile).filter(
            EmployerProfile.stripe_subscription_id == subscription_id
        ).first()
        
        if employer:
            employer.subscription_status = "past_due"
            db.commit()
    
    return {"status": "success"}


@router.get("/subscription-details")
async def get_subscription_details(
    employer: EmployerProfile = Depends(get_employer_profile)
):
    """
    Get current subscription details.
    """
    if not employer.stripe_subscription_id:
        return {
            "tier": employer.subscription_tier,
            "status": employer.subscription_status,
            "has_subscription": False
        }
    
    subscription = stripe_service.get_subscription(employer.stripe_subscription_id)
    
    return {
        "tier": employer.subscription_tier,
        "status": employer.subscription_status,
        "has_subscription": True,
        "current_period_start": subscription["current_period_start"],
        "current_period_end": subscription["current_period_end"],
        "cancel_at_period_end": subscription["cancel_at_period_end"]
    }
```

---

### Step 5: Register Billing Router

**Location:** `services/api/app/main.py`

**What to add:**

```python
from app.routers import auth, candidate, employer, billing  # Add billing

app.include_router(auth.router)
app.include_router(candidate.router)
app.include_router(employer.router)
app.include_router(billing.router)  # ADD THIS
```

---

### Step 6: Setup Stripe Webhook

**Location:** Terminal

**Instructions:**

1. **Install Stripe CLI:**
```bash
# macOS
brew install stripe/stripe-cli/stripe

# Windows (download from https://github.com/stripe/stripe-cli/releases)
# Linux
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-local stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list
sudo apt update
sudo apt install stripe
```

2. **Login to Stripe:**
```bash
stripe login
```

3. **Forward webhooks to local server:**
```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
```

This will output a webhook signing secret:
```
> Ready! Your webhook signing secret is whsec_... (^C to quit)
```

4. **Copy the `whsec_...` value** and add to `services/api/.env`:
```bash
STRIPE_WEBHOOK_SECRET=whsec_...
```

5. **Keep this terminal running** during development to receive webhooks.

---

### Step 7: Frontend - Stripe Context

**Location:** Create `web/contexts/StripeContext.tsx`

**Code:**
```typescript
'use client';

import { loadStripe, Stripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import { ReactNode } from 'react';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

export function StripeProvider({ children }: { children: ReactNode }) {
  return <Elements stripe={stripePromise}>{children}</Elements>;
}
```

---

### Step 8: Frontend - Billing Page

**Location:** Create `web/app/employer/settings/page.tsx`

**Code:**
```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface SubscriptionDetails {
  tier: string;
  status: string;
  has_subscription: boolean;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
}

export default function SettingsPage() {
  const router = useRouter();
  const [subscription, setSubscription] = useState<SubscriptionDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpgrading, setIsUpgrading] = useState(false);

  useEffect(() => {
    fetchSubscription();
  }, []);

  async function fetchSubscription() {
    try {
      const token = localStorage.getItem('accessToken');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/billing/subscription-details`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (res.ok) {
        const data = await res.json();
        setSubscription(data);
      }
    } catch (error) {
      console.error('Failed to fetch subscription:', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleUpgrade(tier: 'starter' | 'pro') {
    setIsUpgrading(true);

    try {
      const token = localStorage.getItem('accessToken');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/billing/create-checkout-session`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ tier }),
        }
      );

      if (res.ok) {
        const data = await res.json();
        // Redirect to Stripe Checkout
        window.location.href = data.url;
      }
    } catch (error) {
      console.error('Failed to create checkout session:', error);
      setIsUpgrading(false);
    }
  }

  async function handleManageSubscription() {
    try {
      const token = localStorage.getItem('accessToken');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/billing/create-portal-session`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (res.ok) {
        const data = await res.json();
        // Redirect to Stripe Customer Portal
        window.location.href = data.url;
      }
    } catch (error) {
      console.error('Failed to open customer portal:', error);
    }
  }

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Subscription & Billing</h1>

      {/* Current Plan */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Current Plan</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-2xl font-bold capitalize">{subscription?.tier} Plan</p>
            <p className="text-gray-600 text-sm">
              Status: <span className="capitalize">{subscription?.status}</span>
            </p>
            {subscription?.current_period_end && (
              <p className="text-gray-600 text-sm">
                {subscription.cancel_at_period_end ? 'Cancels' : 'Renews'} on{' '}
                {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
          </div>

          {subscription?.has_subscription && (
            <button
              onClick={handleManageSubscription}
              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Manage Subscription
            </button>
          )}
        </div>
      </div>

      {/* Pricing Plans */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Free Tier */}
        <PricingCard
          name="Free"
          price="$0"
          period="forever"
          features={[
            '1 active job posting',
            '10 candidate views/month',
            'Basic analytics',
            'Email support',
          ]}
          current={subscription?.tier === 'free'}
          disabled={true}
          onSelect={() => {}}
        />

        {/* Starter Tier */}
        <PricingCard
          name="Starter"
          price="$99"
          period="per month"
          features={[
            '5 active job postings',
            '50 candidate views/month',
            'Advanced analytics',
            'Priority email support',
          ]}
          current={subscription?.tier === 'starter'}
          disabled={isUpgrading || subscription?.tier === 'starter'}
          onSelect={() => handleUpgrade('starter')}
          buttonText={
            subscription?.tier === 'starter'
              ? 'Current Plan'
              : subscription?.tier === 'pro'
              ? 'Downgrade'
              : 'Upgrade'
          }
        />

        {/* Pro Tier */}
        <PricingCard
          name="Pro"
          price="$299"
          period="per month"
          features={[
            'Unlimited job postings',
            '200 candidate views/month',
            'Full analytics suite',
            'Priority support',
            'ATS integration',
          ]}
          current={subscription?.tier === 'pro'}
          disabled={isUpgrading || subscription?.tier === 'pro'}
          onSelect={() => handleUpgrade('pro')}
          buttonText={subscription?.tier === 'pro' ? 'Current Plan' : 'Upgrade'}
          recommended={true}
        />
      </div>

      {/* Enterprise */}
      <div className="mt-8 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg shadow p-8 text-white text-center">
        <h3 className="text-2xl font-bold mb-2">Enterprise</h3>
        <p className="mb-4">Unlimited everything, dedicated support, custom integrations</p>
        <a
          href="mailto:sales@winnow.com"
          className="inline-block bg-white text-blue-600 px-6 py-2 rounded-md font-medium hover:bg-gray-100"
        >
          Contact Sales
        </a>
      </div>
    </div>
  );
}

function PricingCard({
  name,
  price,
  period,
  features,
  current,
  disabled,
  onSelect,
  buttonText = 'Select Plan',
  recommended = false,
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  current: boolean;
  disabled: boolean;
  onSelect: () => void;
  buttonText?: string;
  recommended?: boolean;
}) {
  return (
    <div
      className={`bg-white rounded-lg shadow p-6 ${
        recommended ? 'ring-2 ring-blue-600' : ''
      }`}
    >
      {recommended && (
        <span className="bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">
          RECOMMENDED
        </span>
      )}

      <h3 className="text-xl font-bold mt-4">{name}</h3>
      <div className="mt-4 mb-6">
        <span className="text-4xl font-bold">{price}</span>
        <span className="text-gray-600 text-sm ml-2">{period}</span>
      </div>

      <ul className="space-y-3 mb-6">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span className="text-green-600">✓</span>
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onSelect}
        disabled={disabled}
        className={`w-full py-2 px-4 rounded-md font-medium ${
          current
            ? 'bg-gray-100 text-gray-600 cursor-default'
            : disabled
            ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        {buttonText}
      </button>
    </div>
  );
}
```

---

### Step 9: Success Page

**Location:** Create `web/app/employer/billing/success/page.tsx`

**Code:**
```typescript
'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';

export default function BillingSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    // Optionally verify the session with backend
    // For now, just redirect after 5 seconds
    const timer = setTimeout(() => {
      router.push('/employer/dashboard');
    }, 5000);

    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div className="max-w-2xl mx-auto text-center py-12">
      <div className="bg-white rounded-lg shadow p-12">
        <div className="text-6xl mb-4">🎉</div>
        <h1 className="text-3xl font-bold mb-4">Subscription Activated!</h1>
        <p className="text-gray-600 mb-8">
          Your subscription has been successfully activated. You now have access to all premium features.
        </p>

        <div className="space-y-4">
          <Link
            href="/employer/dashboard"
            className="block bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 font-medium"
          >
            Go to Dashboard
          </Link>
          <Link
            href="/employer/settings"
            className="block text-blue-600 hover:text-blue-700"
          >
            Manage Subscription
          </Link>
        </div>
      </div>
    </div>
  );
}
```

---

## Testing the Billing Flow

### Test Case 1: Upgrade to Starter
1. Login as employer (free tier)
2. Go to `/employer/settings`
3. Click "Upgrade" on Starter plan
4. Should redirect to Stripe Checkout
5. Use test card: `4242 4242 4242 4242`
6. Complete checkout
7. Should redirect to success page
8. Verify tier updated in dashboard

### Test Case 2: Stripe Webhooks
1. Complete a subscription
2. Check webhook terminal output
3. Should see `checkout.session.completed` event
4. Verify employer tier updated in database

### Test Case 3: Customer Portal
1. Have an active subscription
2. Go to `/employer/settings`
3. Click "Manage Subscription"
4. Should redirect to Stripe portal
5. Can update payment method, view invoices, cancel subscription

### Test Case 4: Subscription Cancellation
1. In Customer Portal, cancel subscription
2. Webhook should fire `customer.subscription.deleted`
3. Tier should revert to 'free'
4. Status should be 'cancelled'

---

## Stripe Test Cards

Use these in **test mode** only:

- **Success**: `4242 4242 4242 4242`
- **Declined**: `4000 0000 0000 0002`
- **Requires Auth**: `4000 0025 0000 3155`
- **Insufficient Funds**: `4000 0000 0000 9995`

Any future expiry date, any CVC.

---

## Production Deployment

### Webhook Setup for Production

1. **Go to Stripe Dashboard > Developers > Webhooks**
2. Click "Add endpoint"
3. Endpoint URL: `https://yourdomain.com/api/billing/webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Copy the signing secret
6. Add to production environment variables

---

## Troubleshooting

### "No such customer" error
**Cause:** Stripe customer ID not created  
**Solution:** Check that customer is created in checkout flow

### Webhook not receiving events
**Cause:** Stripe CLI not running or wrong endpoint  
**Solution:** Keep `stripe listen` running during dev

### "Invalid signature" on webhook
**Cause:** Wrong webhook secret  
**Solution:** Copy exact secret from `stripe listen` output

### Payment succeeds but tier doesn't update
**Cause:** Webhook handler not processing event  
**Solution:** Check webhook logs, verify employer lookup logic

### Customer portal not opening
**Cause:** No subscription or wrong customer ID  
**Solution:** Verify subscription exists and customer ID is correct

---

## Next Steps

After completing this prompt:

1. **PROMPT40:** Mobile App (Expo/React Native)
2. **PROMPT41:** Production Deployment (Cloud infrastructure)
3. **PROMPT42:** Advanced Matching Algorithm

---

## Success Criteria

✅ Stripe SDK installed (backend & frontend)  
✅ Products and prices created in Stripe  
✅ Billing routes implemented  
✅ Webhook handler working  
✅ Settings page shows pricing plans  
✅ Can upgrade to Starter/Pro  
✅ Checkout flow redirects to Stripe  
✅ Success page appears after payment  
✅ Subscription tier updates in database  
✅ Customer portal accessible  
✅ Can cancel subscription  
✅ Webhooks update subscription status  

---

**Status:** Ready for implementation  
**Estimated Time:** 3-4 hours  
**Dependencies:** PROMPT36, 38 (employer backend & frontend)  
**Next Prompt:** PROMPT40_Mobile_App.md
