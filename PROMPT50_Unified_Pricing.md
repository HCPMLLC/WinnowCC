# PROMPT 50: Unified Pricing Strategy — Adoption-First (v2.0)

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Objective

Implement the unified three-segment pricing model optimized for maximum adoption and retention. This replaces the candidate-only billing from PROMPT20 and the employer billing from PROMPT39 with a single cohesive system covering candidates, employers, and recruiters.

**Key strategic changes from PROMPT20/PROMPT39:**
- Candidates: Replace `free`/`pro` with `free`/`starter`/`pro` (add $9/mo tier)
- Employers: Replace `free`/$99/$299 with `free`/$49/$149 (lower prices, same schema)
- Recruiters: NEW segment with 14-day trial → `solo`/`team`/`agency` tiers
- Migration toolkit is free forever on all recruiter tiers
- No $1 trial tiers anywhere — free tiers for candidates/employers, 14-day trial for recruiters

---

## Context

Winnow serves three market segments that each need their own billing track:

| Segment | Entry Point | Starter | Pro | Enterprise |
|---------|-------------|---------|-----|------------|
| **Candidates** | Free (no CC) | $9/mo | $19/mo | — |
| **Employers** | Free (no CC) | $49/mo | $149/mo | Custom |
| **Recruiters** | 14-day trial (full access) | $29/mo (Solo) | $69/user/mo (Team) | $99/user/mo (Agency) |

**Annual discounts:** Candidates 27–35%, Employers 32–33%, Recruiters 24–28%.

---

## Prerequisites

- ✅ PROMPT20 completed (candidate billing exists with `free`/`pro`)
- ✅ PROMPT33 completed (employer schema exists with `subscription_tier`)
- ✅ PROMPT39 completed (employer Stripe integration exists)
- ✅ Stripe account in test mode with API keys
- ✅ Stripe CLI installed for local webhook testing

---

## What Already Exists (DO NOT recreate from scratch — MODIFY these)

1. **Candidate billing service:** `services/api/app/services/billing.py` — Has `PLAN_LIMITS` dict with `free`/`pro`, `check_and_increment_usage()`, Stripe checkout/webhook handlers
2. **Candidate subscription model:** `services/api/app/models/subscription.py` — `subscriptions` table with `plan`, `status`, `stripe_customer_id`, usage counters
3. **Employer billing routes:** `services/api/app/routers/billing.py` — Stripe checkout for employers, webhook handler, portal session
4. **Employer Stripe service:** `services/api/app/services/stripe_service.py` — `PRICE_IDS`, checkout/portal/webhook functions
5. **Employer profile model:** `services/api/app/models/employer.py` — `employer_profiles` table with `subscription_tier`, `stripe_customer_id`, `trial_ends_at`
6. **Frontend pricing:** `web/app/pricing/page.tsx` — Candidate pricing page
7. **Frontend employer settings:** `web/app/employer/settings/page.tsx` — Employer billing/upgrade UI
8. **Config:** `services/api/app/core/config.py` — Has `STRIPE_SECRET_KEY`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`

---

# PART 1 — STRIPE DASHBOARD SETUP (Manual, in browser)

These are manual steps performed once in the Stripe Dashboard at https://dashboard.stripe.com. Stay in **test mode**.

### Step 1.1: Delete or Archive Old Products

**Location:** Stripe Dashboard → Products

1. Find the existing "Winnow Pro" product (from PROMPT20) — **Archive it** (don't delete, in case there are test subscriptions)
2. Find the existing "Winnow Starter" and "Winnow Pro" employer products (from PROMPT39) — **Archive them**

### Step 1.2: Create Product — Winnow Candidate

**Location:** Stripe Dashboard → Products → Add Product

1. **Product name:** `Winnow Candidate`
2. **Description:** `AI-powered job search: resume tailoring, match scoring, Sieve concierge`
3. **Add 4 prices:**

| Price Name | Amount | Billing | Lookup Key |
|-----------|--------|---------|------------|
| Candidate Starter Monthly | $9.00 | Monthly, recurring | `candidate_starter_monthly` |
| Candidate Starter Annual | $79.00 | Yearly, recurring | `candidate_starter_annual` |
| Candidate Pro Monthly | $19.00 | Monthly, recurring | `candidate_pro_monthly` |
| Candidate Pro Annual | $149.00 | Yearly, recurring | `candidate_pro_annual` |

4. **Copy all 4 Price IDs** (each starts with `price_...`)

> **IMPORTANT:** To add lookup keys, click "Additional options" when creating each price and enter the lookup key. This lets us reference prices by name instead of hardcoded IDs.

### Step 1.3: Create Product — Winnow Employer

**Location:** Stripe Dashboard → Products → Add Product

1. **Product name:** `Winnow Employer`
2. **Description:** `AI-powered hiring: multi-board distribution, candidate intelligence, analytics`
3. **Add 4 prices:**

| Price Name | Amount | Billing | Lookup Key |
|-----------|--------|---------|------------|
| Employer Starter Monthly | $49.00 | Monthly, recurring | `employer_starter_monthly` |
| Employer Starter Annual | $399.00 | Yearly, recurring | `employer_starter_annual` |
| Employer Pro Monthly | $149.00 | Monthly, recurring | `employer_pro_monthly` |
| Employer Pro Annual | $1,199.00 | Yearly, recurring | `employer_pro_annual` |

4. **Copy all 4 Price IDs**

### Step 1.4: Create Product — Winnow Recruiter

**Location:** Stripe Dashboard → Products → Add Product

1. **Product name:** `Winnow Recruiter`
2. **Description:** `Career intelligence platform: AI briefs, Chrome extension, salary intel, CRM`
3. **Add 6 prices:**

| Price Name | Amount | Billing | Lookup Key |
|-----------|--------|---------|------------|
| Recruiter Solo Monthly | $29.00 | Monthly, recurring | `recruiter_solo_monthly` |
| Recruiter Solo Annual | $249.00 | Yearly, recurring | `recruiter_solo_annual` |
| Recruiter Team Monthly | $69.00 | Monthly, recurring | `recruiter_team_monthly` |
| Recruiter Team Annual | $599.00 | Yearly, recurring | `recruiter_team_annual` |
| Recruiter Agency Monthly | $99.00 | Monthly, recurring | `recruiter_agency_monthly` |
| Recruiter Agency Annual | $899.00 | Yearly, recurring | `recruiter_agency_annual` |

4. **Copy all 6 Price IDs**

> **NOTE on per-seat pricing:** For Team and Agency, the `quantity` in the Stripe subscription represents the number of seats. When creating a checkout session, pass `quantity: numberOfSeats`.

### Step 1.5: Record All Price IDs

After creating all products, you should have **14 Price IDs total**. Write them down — you'll need them in Step 2.1.

---

# PART 2 — ENVIRONMENT VARIABLES

### Step 2.1: Update Backend .env

**Location:** `services/api/.env`

**What to change:** Replace the old `STRIPE_PRICE_STARTER` and `STRIPE_PRICE_PRO` with the new unified set. Add all 14 price IDs:

```bash
# ── Stripe Keys (keep existing) ──
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ── Candidate Prices (NEW — replaces old STRIPE_PRICE_PRO) ──
STRIPE_PRICE_CANDIDATE_STARTER_MO=price_PASTE_HERE
STRIPE_PRICE_CANDIDATE_STARTER_YR=price_PASTE_HERE
STRIPE_PRICE_CANDIDATE_PRO_MO=price_PASTE_HERE
STRIPE_PRICE_CANDIDATE_PRO_YR=price_PASTE_HERE

# ── Employer Prices (NEW — replaces old STRIPE_PRICE_STARTER/PRO) ──
STRIPE_PRICE_EMPLOYER_STARTER_MO=price_PASTE_HERE
STRIPE_PRICE_EMPLOYER_STARTER_YR=price_PASTE_HERE
STRIPE_PRICE_EMPLOYER_PRO_MO=price_PASTE_HERE
STRIPE_PRICE_EMPLOYER_PRO_YR=price_PASTE_HERE

# ── Recruiter Prices (NEW) ──
STRIPE_PRICE_RECRUITER_SOLO_MO=price_PASTE_HERE
STRIPE_PRICE_RECRUITER_SOLO_YR=price_PASTE_HERE
STRIPE_PRICE_RECRUITER_TEAM_MO=price_PASTE_HERE
STRIPE_PRICE_RECRUITER_TEAM_YR=price_PASTE_HERE
STRIPE_PRICE_RECRUITER_AGENCY_MO=price_PASTE_HERE
STRIPE_PRICE_RECRUITER_AGENCY_YR=price_PASTE_HERE
```

### Step 2.2: Update Backend Config

**Location:** `services/api/app/core/config.py`

**What to change:** Replace the old Stripe price settings with the new unified set:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Stripe (keep existing)
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # Remove these old ones:
    # STRIPE_PRICE_STARTER: str    ← DELETE
    # STRIPE_PRICE_PRO: str        ← DELETE

    # Add these new ones:
    # Candidate prices
    STRIPE_PRICE_CANDIDATE_STARTER_MO: str = ""
    STRIPE_PRICE_CANDIDATE_STARTER_YR: str = ""
    STRIPE_PRICE_CANDIDATE_PRO_MO: str = ""
    STRIPE_PRICE_CANDIDATE_PRO_YR: str = ""

    # Employer prices
    STRIPE_PRICE_EMPLOYER_STARTER_MO: str = ""
    STRIPE_PRICE_EMPLOYER_STARTER_YR: str = ""
    STRIPE_PRICE_EMPLOYER_PRO_MO: str = ""
    STRIPE_PRICE_EMPLOYER_PRO_YR: str = ""

    # Recruiter prices
    STRIPE_PRICE_RECRUITER_SOLO_MO: str = ""
    STRIPE_PRICE_RECRUITER_SOLO_YR: str = ""
    STRIPE_PRICE_RECRUITER_TEAM_MO: str = ""
    STRIPE_PRICE_RECRUITER_TEAM_YR: str = ""
    STRIPE_PRICE_RECRUITER_AGENCY_MO: str = ""
    STRIPE_PRICE_RECRUITER_AGENCY_YR: str = ""
```

### Step 2.3: Update Frontend .env.local

**Location:** `web/.env.local`

**What to change:** No new env vars needed — the frontend only needs `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` which already exists. Price IDs are fetched from the backend, never hardcoded in frontend.

---

# PART 3 — DATABASE MIGRATION

### Step 3.1: Create the Migration

**Location:** Terminal

**Commands:**
```bash
cd services/api
alembic revision -m "unified_pricing_v2"
```

This creates a new file in `services/api/alembic/versions/`. Open it and replace the `upgrade()` and `downgrade()` functions.

### Step 3.2: Implement the Migration

**Location:** `services/api/alembic/versions/XXXX_unified_pricing_v2.py`

**Instructions:** Replace the `upgrade()` and `downgrade()` functions only. Do NOT change `revision`, `down_revision`, or date values.

```python
"""unified_pricing_v2

Revision ID: [GENERATED_ID]
Revises: [PREVIOUS_REVISION]
Create Date: [GENERATED_DATE]
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


# revision identifiers — leave as-is
revision = '[GENERATED_ID]'
down_revision = '[PREVIOUS_REVISION]'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Update candidate subscriptions table ──
    # Add billing_interval column ('monthly' or 'annual')
    op.add_column('subscriptions',
        sa.Column('billing_interval', sa.String(20), server_default='monthly')
    )
    # Add sieve_messages_used counter
    op.add_column('subscriptions',
        sa.Column('sieve_messages_used', sa.Integer(), server_default='0')
    )
    # Add semantic_searches_used counter
    op.add_column('subscriptions',
        sa.Column('semantic_searches_used', sa.Integer(), server_default='0')
    )

    # ── 2. Update employer_profiles for new pricing ──
    # Add billing_interval column
    op.add_column('employer_profiles',
        sa.Column('billing_interval', sa.String(20), server_default='monthly')
    )
    # Add monthly usage counters
    op.add_column('employer_profiles',
        sa.Column('candidate_views_used', sa.Integer(), server_default='0')
    )
    op.add_column('employer_profiles',
        sa.Column('candidate_views_reset_at', sa.DateTime(timezone=True))
    )
    op.add_column('employer_profiles',
        sa.Column('job_parses_used', sa.Integer(), server_default='0')
    )

    # ── 3. Create recruiter_profiles table (NEW) ──
    op.create_table(
        'recruiter_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False, unique=True),

        # Company info
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('company_type', sa.String(50)),
        sa.Column('company_website', sa.String(500)),
        sa.Column('specializations', JSONB),

        # Subscription
        sa.Column('subscription_tier', sa.String(50), nullable=False, server_default='trial'),
        sa.Column('subscription_status', sa.String(50), server_default='trialing'),
        sa.Column('billing_interval', sa.String(20), server_default='monthly'),
        sa.Column('stripe_customer_id', sa.String(255)),
        sa.Column('stripe_subscription_id', sa.String(255)),

        # Trial tracking
        sa.Column('trial_started_at', sa.DateTime(timezone=True)),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True)),

        # Seat management
        sa.Column('seats_purchased', sa.Integer(), server_default='1'),
        sa.Column('seats_used', sa.Integer(), server_default='1'),

        # Usage counters
        sa.Column('candidate_briefs_used', sa.Integer(), server_default='0'),
        sa.Column('salary_lookups_used', sa.Integer(), server_default='0'),
        sa.Column('usage_reset_at', sa.DateTime(timezone=True)),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── 4. Create recruiter_team_members table ──
    op.create_table(
        'recruiter_team_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('recruiter_profile_id', UUID(as_uuid=True),
                  sa.ForeignKey('recruiter_profiles.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('role', sa.String(50), server_default='member'),
        sa.Column('invited_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('accepted_at', sa.DateTime(timezone=True)),
    )

    # ── 5. Indexes ──
    op.create_index('idx_recruiter_profiles_user_id', 'recruiter_profiles', ['user_id'])
    op.create_index('idx_recruiter_profiles_stripe_customer', 'recruiter_profiles', ['stripe_customer_id'])
    op.create_index('idx_recruiter_team_members_profile', 'recruiter_team_members', ['recruiter_profile_id'])
    op.create_index('idx_recruiter_team_members_user', 'recruiter_team_members', ['user_id'])


def downgrade():
    op.drop_index('idx_recruiter_team_members_user')
    op.drop_index('idx_recruiter_team_members_profile')
    op.drop_index('idx_recruiter_profiles_stripe_customer')
    op.drop_index('idx_recruiter_profiles_user_id')

    op.drop_table('recruiter_team_members')
    op.drop_table('recruiter_profiles')

    op.drop_column('employer_profiles', 'job_parses_used')
    op.drop_column('employer_profiles', 'candidate_views_reset_at')
    op.drop_column('employer_profiles', 'candidate_views_used')
    op.drop_column('employer_profiles', 'billing_interval')

    op.drop_column('subscriptions', 'semantic_searches_used')
    op.drop_column('subscriptions', 'sieve_messages_used')
    op.drop_column('subscriptions', 'billing_interval')
```

### Step 3.3: Run the Migration

**Location:** Terminal

```bash
cd services/api
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade xxx -> yyy, unified_pricing_v2
```

**Verify:** Connect to your database and confirm:
- `subscriptions` table has new columns: `billing_interval`, `sieve_messages_used`, `semantic_searches_used`
- `employer_profiles` table has new columns: `billing_interval`, `candidate_views_used`, `candidate_views_reset_at`, `job_parses_used`
- New table `recruiter_profiles` exists with all columns
- New table `recruiter_team_members` exists

---

# PART 4 — BACKEND: UNIFIED PLAN LIMITS

### Step 4.1: Update Candidate PLAN_LIMITS

**Location:** `services/api/app/services/billing.py`

**What to change:** Replace the existing `PLAN_LIMITS` dict with the new three-tier model:

```python
# ── Candidate Plan Limits ──────────────────────────────────────────

CANDIDATE_PLAN_LIMITS = {
    "free": {
        "resume_uploads": 1,
        "resume_parses": 1,
        "matches_visible": 5,
        "tailored_resumes_per_month": 1,    # 1 total (not per month — once used, must upgrade)
        "cover_letters_per_month": 1,        # 1 total
        "semantic_searches_per_day": 3,      # 3 total
        "application_tracking": 5,           # 5 jobs max
        "sieve_messages_per_day": 3,         # 3 total
        "match_explainability": "basic",     # top 3 dimensions
        "ips_breakdown": "score_only",
        "mjass_enabled": False,
        "data_export": False,
    },
    "starter": {
        "resume_uploads": 3,
        "resume_parses": 3,
        "matches_visible": 25,               # per day
        "tailored_resumes_per_month": 5,
        "cover_letters_per_month": 5,
        "semantic_searches_per_day": 10,
        "application_tracking": 50,
        "sieve_messages_per_day": 50,
        "match_explainability": "full",      # top 7 dimensions
        "ips_breakdown": "score_breakdown",
        "mjass_enabled": False,
        "data_export": "csv",
    },
    "pro": {
        "resume_uploads": 999,
        "resume_parses": 999,
        "matches_visible": 999,
        "tailored_resumes_per_month": 30,
        "cover_letters_per_month": 30,
        "semantic_searches_per_day": 999,
        "application_tracking": 999,
        "sieve_messages_per_day": 999,
        "match_explainability": "full_gap",  # full + gap analysis
        "ips_breakdown": "full_5_stage",
        "mjass_enabled": True,
        "data_export": "full",               # JSON + CSV + DOCX
    },
}

# Keep backward compatibility — old code referencing PLAN_LIMITS still works
PLAN_LIMITS = CANDIDATE_PLAN_LIMITS
```

### Step 4.2: Add Employer Plan Limits

**Location:** `services/api/app/services/billing.py` (add below candidate limits)

```python
# ── Employer Plan Limits ───────────────────────────────────────────

EMPLOYER_PLAN_LIMITS = {
    "free": {
        "active_jobs": 1,
        "candidate_views_per_month": 5,
        "multi_board_distribution": ["google_jobs"],
        "ai_job_parsing_per_month": 1,       # 1 total
        "cross_board_analytics": False,
        "salary_intelligence": False,
        "time_to_fill_prediction": False,
        "bias_detection": False,
        "support_level": "community",
    },
    "starter": {
        "active_jobs": 5,
        "candidate_views_per_month": 50,
        "multi_board_distribution": ["google_jobs", "indeed", "ziprecruiter"],
        "ai_job_parsing_per_month": 10,
        "cross_board_analytics": "basic",
        "salary_intelligence": False,
        "time_to_fill_prediction": False,
        "bias_detection": "basic",
        "support_level": "email",
    },
    "pro": {
        "active_jobs": 25,
        "candidate_views_per_month": 200,
        "multi_board_distribution": "all",
        "ai_job_parsing_per_month": 999,
        "cross_board_analytics": "full",
        "salary_intelligence": True,
        "time_to_fill_prediction": True,
        "bias_detection": "full",
        "support_level": "email_chat",
    },
    "enterprise": {
        "active_jobs": 999,
        "candidate_views_per_month": 999,
        "multi_board_distribution": "all_custom",
        "ai_job_parsing_per_month": 999,
        "cross_board_analytics": "full_api",
        "salary_intelligence": True,
        "time_to_fill_prediction": True,
        "bias_detection": "full_ofccp",
        "support_level": "dedicated_csm",
    },
}
```

### Step 4.3: Add Recruiter Plan Limits

**Location:** `services/api/app/services/billing.py` (add below employer limits)

```python
# ── Recruiter Plan Limits ──────────────────────────────────────────

RECRUITER_PLAN_LIMITS = {
    "trial": {
        # Full Agency-level access for 14 days
        "seats": 1,
        "candidate_briefs_per_month": 999,
        "chrome_extension": True,
        "salary_lookups_per_month": 999,
        "market_position_scoring": True,
        "career_trajectory_ai": True,
        "time_to_fill_prediction": True,
        "migration_toolkit": "full",
        "client_crm": "full",
        "invoicing": True,
        "trial_duration_days": 14,
    },
    "solo": {
        "seats": 1,
        "candidate_briefs_per_month": 20,
        "chrome_extension": True,
        "salary_lookups_per_month": 5,
        "market_position_scoring": True,
        "career_trajectory_ai": False,
        "time_to_fill_prediction": False,
        "migration_toolkit": "full",         # Free forever on ALL tiers
        "client_crm": "basic",
        "invoicing": False,
    },
    "team": {
        "seats": 10,                          # Max seats for this tier
        "candidate_briefs_per_month": 100,
        "chrome_extension": True,
        "salary_lookups_per_month": 50,
        "market_position_scoring": True,
        "career_trajectory_ai": True,
        "time_to_fill_prediction": True,
        "migration_toolkit": "full",
        "client_crm": "full",
        "invoicing": False,
    },
    "agency": {
        "seats": 999,                         # Unlimited
        "candidate_briefs_per_month": 500,
        "chrome_extension": True,
        "salary_lookups_per_month": 999,
        "market_position_scoring": True,
        "career_trajectory_ai": True,
        "time_to_fill_prediction": True,
        "migration_toolkit": "full",
        "client_crm": "full_pipeline",
        "invoicing": True,
    },
    "enterprise": {
        "seats": 999,
        "candidate_briefs_per_month": 999,
        "chrome_extension": True,
        "salary_lookups_per_month": 999,
        "market_position_scoring": True,
        "career_trajectory_ai": True,
        "time_to_fill_prediction": True,
        "migration_toolkit": "full_api",
        "client_crm": "full_custom",
        "invoicing": True,
    },
}
```

### Step 4.4: Add Unified Price ID Map

**Location:** `services/api/app/services/billing.py` (add below plan limits)

```python
# ── Stripe Price ID Map ────────────────────────────────────────────
# Maps (segment, tier, interval) → Stripe Price ID from env vars

from app.core.config import settings

PRICE_IDS = {
    # Candidates
    ("candidate", "starter", "monthly"): settings.STRIPE_PRICE_CANDIDATE_STARTER_MO,
    ("candidate", "starter", "annual"):  settings.STRIPE_PRICE_CANDIDATE_STARTER_YR,
    ("candidate", "pro", "monthly"):     settings.STRIPE_PRICE_CANDIDATE_PRO_MO,
    ("candidate", "pro", "annual"):      settings.STRIPE_PRICE_CANDIDATE_PRO_YR,

    # Employers
    ("employer", "starter", "monthly"):  settings.STRIPE_PRICE_EMPLOYER_STARTER_MO,
    ("employer", "starter", "annual"):   settings.STRIPE_PRICE_EMPLOYER_STARTER_YR,
    ("employer", "pro", "monthly"):      settings.STRIPE_PRICE_EMPLOYER_PRO_MO,
    ("employer", "pro", "annual"):       settings.STRIPE_PRICE_EMPLOYER_PRO_YR,

    # Recruiters
    ("recruiter", "solo", "monthly"):    settings.STRIPE_PRICE_RECRUITER_SOLO_MO,
    ("recruiter", "solo", "annual"):     settings.STRIPE_PRICE_RECRUITER_SOLO_YR,
    ("recruiter", "team", "monthly"):    settings.STRIPE_PRICE_RECRUITER_TEAM_MO,
    ("recruiter", "team", "annual"):     settings.STRIPE_PRICE_RECRUITER_TEAM_YR,
    ("recruiter", "agency", "monthly"):  settings.STRIPE_PRICE_RECRUITER_AGENCY_MO,
    ("recruiter", "agency", "annual"):   settings.STRIPE_PRICE_RECRUITER_AGENCY_YR,
}


def get_price_id(segment: str, tier: str, interval: str = "monthly") -> str:
    """
    Look up the Stripe Price ID for a given segment/tier/interval.

    Args:
        segment: 'candidate', 'employer', or 'recruiter'
        tier: Plan tier name (e.g., 'starter', 'pro', 'solo', 'team', 'agency')
        interval: 'monthly' or 'annual'

    Returns:
        Stripe price ID string

    Raises:
        ValueError if combination not found
    """
    key = (segment, tier, interval)
    price_id = PRICE_IDS.get(key)
    if not price_id:
        raise ValueError(f"No Stripe price configured for {segment}/{tier}/{interval}")
    return price_id
```

### Step 4.5: Update get_plan_limits Helper

**Location:** `services/api/app/services/billing.py` (replace existing `get_plan_limits`)

```python
def get_plan_limits(plan: str, segment: str = "candidate") -> dict:
    """
    Return the limits for a given plan and segment.

    Args:
        plan: Plan name ('free', 'starter', 'pro', 'trial', 'solo', 'team', 'agency', 'enterprise')
        segment: 'candidate', 'employer', or 'recruiter'

    Returns:
        Dict of feature limits
    """
    if segment == "candidate":
        return CANDIDATE_PLAN_LIMITS.get(plan, CANDIDATE_PLAN_LIMITS["free"])
    elif segment == "employer":
        return EMPLOYER_PLAN_LIMITS.get(plan, EMPLOYER_PLAN_LIMITS["free"])
    elif segment == "recruiter":
        return RECRUITER_PLAN_LIMITS.get(plan, RECRUITER_PLAN_LIMITS["trial"])
    else:
        return CANDIDATE_PLAN_LIMITS["free"]
```

---

# PART 5 — BACKEND: RECRUITER MODEL

### Step 5.1: Create Recruiter Profile Model

**Location:** Create NEW file `services/api/app/models/recruiter.py`

```python
"""Recruiter profile model."""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class RecruiterProfile(Base):
    __tablename__ = "recruiter_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, unique=True)

    # Company info
    company_name = Column(String(255), nullable=False)
    company_type = Column(String(50))
    company_website = Column(String(500))
    specializations = Column(JSONB)

    # Subscription
    subscription_tier = Column(String(50), nullable=False, default="trial")
    subscription_status = Column(String(50), default="trialing")
    billing_interval = Column(String(20), default="monthly")
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))

    # Trial
    trial_started_at = Column(DateTime(timezone=True))
    trial_ends_at = Column(DateTime(timezone=True))

    # Seats
    seats_purchased = Column(Integer, default=1)
    seats_used = Column(Integer, default=1)

    # Usage
    candidate_briefs_used = Column(Integer, default=0)
    salary_lookups_used = Column(Integer, default=0)
    usage_reset_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", backref="recruiter_profile")
    team_members = relationship("RecruiterTeamMember", back_populates="recruiter_profile",
                                cascade="all, delete-orphan")

    @property
    def is_trial_active(self) -> bool:
        """Check if the 14-day trial is still active."""
        if self.subscription_tier != "trial":
            return False
        if not self.trial_ends_at:
            return False
        return datetime.now(timezone.utc) < self.trial_ends_at

    @property
    def trial_days_remaining(self) -> int:
        """Days remaining in trial. Returns 0 if trial expired."""
        if not self.trial_ends_at:
            return 0
        delta = self.trial_ends_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def start_trial(self):
        """Initialize the 14-day trial."""
        now = datetime.now(timezone.utc)
        self.subscription_tier = "trial"
        self.subscription_status = "trialing"
        self.trial_started_at = now
        self.trial_ends_at = now + timedelta(days=14)


class RecruiterTeamMember(Base):
    __tablename__ = "recruiter_team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_profile_id = Column(UUID(as_uuid=True),
                                   ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
                                   nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)
    role = Column(String(50), default="member")
    invited_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted_at = Column(DateTime(timezone=True))

    # Relationships
    recruiter_profile = relationship("RecruiterProfile", back_populates="team_members")
    user = relationship("User")
```

### Step 5.2: Register the Model

**Location:** `services/api/app/models/__init__.py`

**What to add:**
```python
from app.models.recruiter import RecruiterProfile, RecruiterTeamMember
```

---

# PART 6 — BACKEND: UNIFIED BILLING ROUTES

### Step 6.1: Create Unified Checkout Endpoint

**Location:** `services/api/app/routers/billing.py`

**What to change:** Add this new unified endpoint alongside the existing ones. Keep existing endpoints working for backward compatibility until frontend is updated.

```python
from pydantic import BaseModel
from typing import Optional


class UnifiedCheckoutRequest(BaseModel):
    """Request to create a checkout session for any segment."""
    segment: str          # 'candidate', 'employer', 'recruiter'
    tier: str             # 'starter', 'pro', 'solo', 'team', 'agency'
    interval: str = "monthly"  # 'monthly' or 'annual'
    seats: int = 1        # For recruiter team/agency only


class CheckoutResponse(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_unified_checkout(
    request: UnifiedCheckoutRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a Stripe Checkout session for any segment/tier/interval.

    Handles:
    - Candidate: starter or pro (monthly/annual)
    - Employer: starter or pro (monthly/annual)
    - Recruiter: solo, team, or agency (monthly/annual, with seat quantity)
    """
    from app.services.billing import get_price_id

    # Validate segment/tier combination
    valid_combos = {
        "candidate": ["starter", "pro"],
        "employer": ["starter", "pro"],
        "recruiter": ["solo", "team", "agency"],
    }
    if request.segment not in valid_combos:
        raise HTTPException(400, f"Invalid segment: {request.segment}")
    if request.tier not in valid_combos[request.segment]:
        raise HTTPException(400, f"Invalid tier '{request.tier}' for segment '{request.segment}'")

    # Get the Stripe price ID
    try:
        price_id = get_price_id(request.segment, request.tier, request.interval)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Get or create Stripe customer
    stripe_customer_id = _get_or_create_stripe_customer(current_user, request.segment, db)

    # Build checkout session
    line_items = [{
        "price": price_id,
        "quantity": request.seats if request.segment == "recruiter" and request.tier in ("team", "agency") else 1,
    }]

    # Recruiter subscriptions get a 14-day trial
    subscription_data = {}
    if request.segment == "recruiter":
        subscription_data["trial_period_days"] = 14

    import stripe
    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        mode="subscription",
        payment_method_types=["card"],
        line_items=line_items,
        subscription_data=subscription_data if subscription_data else None,
        success_url=f"{settings.FRONTEND_URL}/{request.segment}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/{request.segment}/settings",
        metadata={
            "platform": "winnow",
            "segment": request.segment,
            "tier": request.tier,
            "interval": request.interval,
            "seats": str(request.seats),
        }
    )

    return CheckoutResponse(url=session.url)


def _get_or_create_stripe_customer(user, segment: str, db: Session) -> str:
    """Get existing Stripe customer ID or create a new one."""
    import stripe

    # Check the appropriate profile for existing customer ID
    if segment == "candidate":
        if user.stripe_customer_id:
            return user.stripe_customer_id
    elif segment == "employer":
        employer = user.employer_profile
        if employer and employer.stripe_customer_id:
            return employer.stripe_customer_id
    elif segment == "recruiter":
        recruiter = user.recruiter_profile
        if recruiter and recruiter.stripe_customer_id:
            return recruiter.stripe_customer_id

    # Create new Stripe customer
    customer = stripe.Customer.create(
        email=user.email,
        name=getattr(user, 'full_name', user.email),
        metadata={"platform": "winnow", "segment": segment, "user_id": str(user.id)}
    )

    # Store customer ID in the appropriate place
    if segment == "candidate":
        user.stripe_customer_id = customer.id
    elif segment == "employer" and user.employer_profile:
        user.employer_profile.stripe_customer_id = customer.id
    elif segment == "recruiter" and user.recruiter_profile:
        user.recruiter_profile.stripe_customer_id = customer.id

    db.commit()
    return customer.id
```

### Step 6.2: Update Webhook Handler for All Segments

**Location:** `services/api/app/routers/billing.py`

**What to change:** Update the existing webhook handler to read the `segment` from checkout metadata and update the correct profile. Replace the existing `stripe_webhook` function:

```python
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events for all segments."""
    import stripe as stripe_lib

    payload = await request.body()
    try:
        event = stripe_lib.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid signature")

    if event.type == "checkout.session.completed":
        session = event.data.object
        metadata = session.get("metadata", {})
        segment = metadata.get("segment", "candidate")
        tier = metadata.get("tier", "starter")
        interval = metadata.get("interval", "monthly")
        seats = int(metadata.get("seats", "1"))

        if segment == "candidate":
            from app.models.subscription import Subscription
            sub = db.query(Subscription).join(User).filter(
                User.stripe_customer_id == session.customer
            ).first()
            if sub:
                sub.plan = tier
                sub.status = "active"
                sub.billing_interval = interval
                sub.stripe_subscription_id = session.subscription
                db.commit()

        elif segment == "employer":
            from app.models.employer import EmployerProfile
            employer = db.query(EmployerProfile).filter(
                EmployerProfile.stripe_customer_id == session.customer
            ).first()
            if employer:
                employer.subscription_tier = tier
                employer.subscription_status = "active"
                employer.billing_interval = interval
                employer.stripe_subscription_id = session.subscription
                db.commit()

        elif segment == "recruiter":
            from app.models.recruiter import RecruiterProfile
            recruiter = db.query(RecruiterProfile).filter(
                RecruiterProfile.stripe_customer_id == session.customer
            ).first()
            if recruiter:
                recruiter.subscription_tier = tier
                recruiter.subscription_status = "active"
                recruiter.billing_interval = interval
                recruiter.stripe_subscription_id = session.subscription
                recruiter.seats_purchased = seats
                db.commit()

    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object
        _handle_subscription_cancelled(subscription.id, db)

    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        _handle_payment_failed(invoice.subscription, db)

    return {"status": "success"}


def _handle_subscription_cancelled(subscription_id: str, db: Session):
    """Downgrade the user whose subscription was cancelled."""
    from app.models.subscription import Subscription
    from app.models.employer import EmployerProfile
    from app.models.recruiter import RecruiterProfile

    # Check candidates
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == subscription_id
    ).first()
    if sub:
        sub.plan = "free"
        sub.status = "cancelled"
        db.commit()
        return

    # Check employers
    employer = db.query(EmployerProfile).filter(
        EmployerProfile.stripe_subscription_id == subscription_id
    ).first()
    if employer:
        employer.subscription_tier = "free"
        employer.subscription_status = "cancelled"
        db.commit()
        return

    # Check recruiters
    recruiter = db.query(RecruiterProfile).filter(
        RecruiterProfile.stripe_subscription_id == subscription_id
    ).first()
    if recruiter:
        recruiter.subscription_tier = "trial"
        recruiter.subscription_status = "expired"
        db.commit()


def _handle_payment_failed(subscription_id: str, db: Session):
    """Mark the subscription as past_due across all segments."""
    from app.models.subscription import Subscription
    from app.models.employer import EmployerProfile
    from app.models.recruiter import RecruiterProfile

    for Model, field in [
        (Subscription, "status"),
        (EmployerProfile, "subscription_status"),
        (RecruiterProfile, "subscription_status"),
    ]:
        obj = db.query(Model).filter(
            getattr(Model, "stripe_subscription_id") == subscription_id
        ).first()
        if obj:
            setattr(obj, field, "past_due")
            db.commit()
            return
```

### Step 6.3: Add Public Plans Info Endpoint

**Location:** `services/api/app/routers/billing.py` (add this new endpoint)

```python
@router.get("/plans/{segment}")
async def get_plans(segment: str):
    """
    Return available plans and pricing for a segment.
    This is a public endpoint — no auth required.
    Used by the pricing pages to display plan features and prices.
    """
    from app.services.billing import (
        CANDIDATE_PLAN_LIMITS, EMPLOYER_PLAN_LIMITS, RECRUITER_PLAN_LIMITS
    )

    prices = {
        "candidate": {
            "free": {"monthly": 0, "annual": 0},
            "starter": {"monthly": 9, "annual": 79},
            "pro": {"monthly": 19, "annual": 149},
        },
        "employer": {
            "free": {"monthly": 0, "annual": 0},
            "starter": {"monthly": 49, "annual": 399},
            "pro": {"monthly": 149, "annual": 1199},
            "enterprise": {"monthly": "custom", "annual": "custom"},
        },
        "recruiter": {
            "trial": {"monthly": 0, "annual": 0, "duration_days": 14},
            "solo": {"monthly": 29, "annual": 249},
            "team": {"monthly": 69, "annual": 599, "per_seat": True},
            "agency": {"monthly": 99, "annual": 899, "per_seat": True},
            "enterprise": {"monthly": "custom", "annual": "custom"},
        },
    }

    limits_map = {
        "candidate": CANDIDATE_PLAN_LIMITS,
        "employer": EMPLOYER_PLAN_LIMITS,
        "recruiter": RECRUITER_PLAN_LIMITS,
    }

    if segment not in prices:
        raise HTTPException(400, f"Invalid segment: {segment}")

    return {
        "segment": segment,
        "plans": {
            tier: {
                "prices": prices[segment][tier],
                "limits": limits_map[segment].get(tier, {}),
            }
            for tier in prices[segment]
        }
    }
```

---

# PART 7 — FRONTEND: PRICING PAGES

### Step 7.1: Create Shared Pricing Component

**Location:** Create NEW file `web/components/PricingCard.tsx`

Build a reusable pricing card component that:
- Shows plan name, price (monthly/annual toggle), and feature list
- Highlights the recommended plan with a Gold (#E8C84A) border
- Shows "Current Plan" badge if the user is on that plan
- Has a CTA button: "Get Started" for free, "Upgrade" for paid tiers
- Annual pricing shows monthly equivalent and savings percentage
- Uses Winnow brand palette: Hunter Green (#1B3025), Gold (#E8C84A), Sage Mist (#CEE3D8)

### Step 7.2: Create Candidate Pricing Page

**Location:** `web/app/pricing/page.tsx` (replace existing)

Build a pricing page that:
- Fetches plans from `GET /api/billing/plans/candidate`
- Shows 3 columns: Free / Starter ($9/mo) / Pro ($19/mo)
- Has monthly/annual toggle. Annual shows: Starter $79/yr (save 27%), Pro $149/yr (save 35%)
- Free column: "Get Started Free" button → links to `/register`
- Starter/Pro: "Upgrade to Starter/Pro" button → calls `POST /api/billing/checkout` with `segment: "candidate"`
- Below the cards, show competitor comparison:
  - "Everything Jobscan does for $50/mo + everything Teal does for $29/mo + AI concierge. All for $9/mo."
- If user is logged in and already on a plan, show "Current Plan" badge on their tier
- Page title: "Simple, transparent pricing"
- Subtitle: "Experience the AI magic for free. Upgrade when you're ready."

### Step 7.3: Create Employer Pricing Page

**Location:** Create NEW file `web/app/employer/pricing/page.tsx`

Build a pricing page that:
- Fetches plans from `GET /api/billing/plans/employer`
- Shows 4 columns: Free / Starter ($49/mo) / Pro ($149/mo) / Enterprise (Contact Sales)
- Monthly/annual toggle. Annual shows: Starter $399/yr (save 32%), Pro $1,199/yr (save 33%)
- Free: "Post Your First Job Free" → links to `/employer/register`
- Starter/Pro: upgrade buttons → `POST /api/billing/checkout` with `segment: "employer"`
- Enterprise: "Contact Sales" button → opens mailto or contact form
- Competitor comparison: "83% cheaper than ZipRecruiter. Smarter than Indeed."

### Step 7.4: Create Recruiter Pricing Page

**Location:** Create NEW file `web/app/recruiter/pricing/page.tsx`

Build a pricing page that:
- Fetches plans from `GET /api/billing/plans/recruiter`
- Shows 4 columns: Solo ($29/mo) / Team ($69/user/mo) / Agency ($99/user/mo) / Enterprise
- All tiers show "14-day free trial" badge at top
- Monthly/annual toggle
- Team and Agency show seat selector (dropdown: 2–10 for Team, 2–50 for Agency)
- Price updates dynamically: e.g., "Team: $69/user × 5 seats = $345/mo"
- Migration toolkit called out as "Free forever on all plans" with highlight
- Solo: "Start 14-Day Free Trial" → calls checkout with trial_period_days
- Competitor comparison: "50–70% less than Bullhorn. Zero implementation fees."

### Step 7.5: Add Upgrade Prompts at Limit Boundaries

**Location:** Update these existing pages to show contextual upgrade prompts:

1. **Candidate match list** (`web/app/matches/page.tsx`):
   - When free user sees 5th match: "You've seen all 5 free matches. Upgrade to Starter for 25/day → $9/mo"

2. **Candidate tailoring** (the page/component that shows after generating a tailored resume):
   - When free user uses their 1 tailored resume: "Your free tailored resume is ready! Want 5 more this month? Starter is $9/mo."

3. **Employer job creation** (`web/app/employer/jobs/new/page.tsx` or similar):
   - When free employer tries to create 2nd job: "Free plan allows 1 active job. Upgrade to Starter ($49/mo) for 5 jobs."

4. **Employer candidate search** (`web/app/employer/candidates/page.tsx` or similar):
   - When free employer hits 5 views: "You've used 5/5 free candidate views this month. Upgrade for more."

---

# PART 8 — RECRUITER ONBOARDING FLOW

### Step 8.1: Create Recruiter Registration Page

**Location:** Create NEW file `web/app/recruiter/register/page.tsx`

Build a registration page that:
1. Collects: email, password, company name, company type (dropdown: Independent / Boutique Agency / Staffing Agency / Enterprise), specializations (multi-select checkboxes: Technology, Healthcare, Finance, Legal, etc.)
2. On submit: calls a backend endpoint that creates user with `role: "recruiter"`, creates `recruiter_profile` with `trial` status, calls `start_trial()`
3. Redirects to `/recruiter/dashboard` with welcome banner: "Your 14-day trial has started! You have full access to all Agency-level features."
4. Shows trial countdown in the header/sidebar: "Trial: 12 days remaining"

### Step 8.2: Create Recruiter Registration Backend Endpoint

**Location:** Add to `services/api/app/routers/auth.py` (or create `services/api/app/routers/recruiter.py`)

```python
@router.post("/register/recruiter")
async def register_recruiter(
    request: RecruiterRegistrationRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new recruiter and start their 14-day trial.
    """
    # 1. Create user with role='recruiter'
    user = User(email=request.email, role="recruiter")
    user.set_password(request.password)
    db.add(user)
    db.flush()

    # 2. Create recruiter profile and start trial
    from app.models.recruiter import RecruiterProfile
    profile = RecruiterProfile(
        user_id=user.id,
        company_name=request.company_name,
        company_type=request.company_type,
        specializations=request.specializations,
    )
    profile.start_trial()  # Sets trial_started_at and trial_ends_at
    db.add(profile)
    db.commit()

    # 3. Return auth token
    token = create_access_token(user.id)
    return {"token": token, "trial_ends_at": str(profile.trial_ends_at)}
```

### Step 8.3: Create Recruiter Dashboard with Trial Banner

**Location:** Create NEW file `web/app/recruiter/dashboard/page.tsx`

Build a dashboard that:
- Shows trial status banner at top (if on trial): days remaining, upgrade CTA
- At day 7: yellow banner "7 days left in your trial. Choose a plan to keep your data."
- At day 2: red banner "Your trial expires in 2 days. Upgrade now to avoid losing access."
- After trial expires: Full-page overlay: "Your trial has ended. Choose a plan to continue. Your data is safe — upgrade to access it."
- Shows usage stats: briefs generated, candidates sourced, data imported

---

# PART 9 — TESTING & VERIFICATION

### Step 9.1: Verify Stripe Webhook Forwarding

**Location:** Terminal (keep running during testing)

```bash
stripe listen --forward-to localhost:8000/api/billing/webhook
```

### Step 9.2: Test Each Segment Flow

**Test Candidate Flow:**
1. Register a new candidate account → verify starts on `free` tier
2. Use 1 tailored resume → verify count incremented and limit shown
3. Try 2nd tailored resume → verify blocked with upgrade prompt
4. Click "Upgrade to Starter" → verify Stripe Checkout opens at $9/mo
5. Complete with test card `4242 4242 4242 4242` → verify tier updates to `starter`
6. Verify 5 tailored resumes/month now available

**Test Employer Flow:**
1. Register a new employer account → verify starts on `free` tier
2. Create 1 job → verify succeeds
3. Try creating 2nd job → verify blocked with upgrade prompt
4. Click "Upgrade to Starter" → verify Stripe Checkout at $49/mo
5. Complete payment → verify tier updates, 5 jobs now allowed

**Test Recruiter Flow:**
1. Register a new recruiter account → verify starts on `trial` with 14-day countdown
2. Verify full Agency-level access during trial (unlimited briefs, salary lookups, etc.)
3. Wait for trial to expire (or manually set `trial_ends_at` to past date in DB)
4. Verify access blocked with "Choose a plan" overlay
5. Click "Choose Solo" → verify Stripe Checkout at $29/mo with trial_period_days: 14
6. Complete payment → verify tier updates to `solo`

**Test Annual Pricing:**
1. On any pricing page, toggle to "Annual"
2. Click upgrade → verify Stripe Checkout shows annual price
3. Complete payment → verify `billing_interval` stored as `annual`

**Test Webhook Events:**
1. In Stripe Dashboard (test mode), manually cancel a subscription
2. Verify the webhook fires and the user is downgraded to `free`/`expired`
3. Trigger a failed payment → verify `past_due` status is set

### Step 9.3: Stripe Test Card Numbers

- **Succeeds:** `4242 4242 4242 4242`
- **Requires auth:** `4000 0025 0000 3155`
- **Declined:** `4000 0000 0000 0002`

Use any future expiry date, any 3-digit CVC, and any billing ZIP.

---

# SUMMARY — Files Modified/Created

**Modified files:**

| # | File | What Changed |
|---|------|-------------|
| 1 | `services/api/.env` | Added 14 new Stripe price IDs, removed 2 old ones |
| 2 | `services/api/app/core/config.py` | Added 14 price settings, removed 2 old ones |
| 3 | `services/api/app/services/billing.py` | New 3-tier candidate limits, employer limits, recruiter limits, PRICE_IDS map, unified helpers |
| 4 | `services/api/app/routers/billing.py` | Unified checkout endpoint, updated webhook for all segments, plans info endpoint |
| 5 | `services/api/app/models/__init__.py` | Added RecruiterProfile, RecruiterTeamMember imports |
| 6 | `web/app/pricing/page.tsx` | Rebuilt with Free/Starter/Pro columns |
| 7 | `web/app/employer/settings/page.tsx` | Updated for new $49/$149 pricing |

**New files:**

| # | File | Purpose |
|---|------|---------|
| 1 | `services/api/alembic/versions/XXXX_unified_pricing_v2.py` | Migration: recruiter tables, new columns |
| 2 | `services/api/app/models/recruiter.py` | RecruiterProfile + RecruiterTeamMember models |
| 3 | `web/components/PricingCard.tsx` | Shared pricing card component |
| 4 | `web/app/employer/pricing/page.tsx` | Employer pricing page |
| 5 | `web/app/recruiter/pricing/page.tsx` | Recruiter pricing page with seat selector |
| 6 | `web/app/recruiter/register/page.tsx` | Recruiter registration + trial start |
| 7 | `web/app/recruiter/dashboard/page.tsx` | Recruiter dashboard with trial banner |

**Database changes:**

| Table | Change |
|-------|--------|
| `subscriptions` | +3 columns: `billing_interval`, `sieve_messages_used`, `semantic_searches_used` |
| `employer_profiles` | +4 columns: `billing_interval`, `candidate_views_used`, `candidate_views_reset_at`, `job_parses_used` |
| `recruiter_profiles` | NEW table: subscription, trial, seats, usage tracking |
| `recruiter_team_members` | NEW table: team seat management |
