# PROMPT79_Admin_Test_Mode.md

Read CLAUDE.md, AGENTS.md, and the billing service before making changes.

## Purpose

Add an **Admin Test Mode** that allows designated admin email addresses to bypass ALL billing tier checks, daily usage limits, and feature gates across all three segments (candidate, employer, recruiter) — without creating Stripe subscriptions or triggering any charges. This enables the founder to test every top-tier feature in production as if they had the highest plan in each segment.

**Why this matters:** Winnow has 3 segments × 3+ tiers each = dozens of gated features. Testing them in production currently requires either manual database edits or real Stripe subscriptions. This adds a clean, secure, environment-variable-controlled bypass.

---

## Triggers — When to Use This Prompt

- Need to test Pro/Agency-tier features without paying
- Need to bypass daily usage counters during QA
- Need to verify feature gates work correctly by toggling admin mode on/off
- Need a demo mode for investor presentations

---

## What Already Exists (READ FIRST — do NOT recreate)

1. **Billing service:** `services/api/app/services/billing.py`
   - `CANDIDATE_PLAN_LIMITS` dict with tiers: `free`, `starter`, `pro`
   - `EMPLOYER_PLAN_LIMITS` dict with tiers: `free`, `starter`, `pro`, `enterprise`
   - `RECRUITER_PLAN_LIMITS` dict with tiers: `trial`, `solo`, `team`, `agency`, `enterprise`
   - Helper functions: `get_plan_limits()`, `get_user_plan()`, `check_feature_access()`, `check_daily_limit()`, `increment_daily_counter()`
   - Backward-compat alias: `PLAN_LIMITS = CANDIDATE_PLAN_LIMITS`
2. **Auth service:** `services/api/app/services/auth.py` — `get_current_user()` returns user object with `.email`, `.id`, `.role`
3. **Daily usage model:** `services/api/app/models/` — `DailyUsageCounter` tracks per-day limits
4. **Subscription model:** `services/api/app/models/subscription.py` — `Subscription` with `plan`, `status`
5. **Recruiter billing:** `services/api/app/models/recruiter.py` — `RecruiterProfile.subscription_tier`
6. **Employer billing:** Employer profiles have their own `plan_tier` field
7. **Environment variables:** Already loaded via `os.environ.get()` pattern throughout the codebase
8. **Existing ADMIN_TOKEN:** Used for admin API endpoints (different from this feature — do not conflict)

---

## Implementation — 3 Parts

Execute in exact order. Each part builds on the previous one.

---

## PART 1 — Add the Environment Variable

### Step 1.1 — Add to `.env` files

**File to edit:** `services/api/.env`

Open this file in Cursor. Add this line at the bottom, in a new section:

```
# ── Admin Test Mode ────────────────────────────────────────────
# Comma-separated list of email addresses that bypass ALL billing checks.
# These users see top-tier features (Pro/Agency) without Stripe subscriptions.
# Leave empty or remove to disable admin test mode entirely.
ADMIN_TEST_EMAILS=ron@winnowcc.com,hello@winnowcc.com,team@winnowcc.com
```

**File to edit:** `services/api/.env.example`

Open this file in Cursor. Add the same block (but with placeholder values):

```
# ── Admin Test Mode ────────────────────────────────────────────
# Comma-separated emails that bypass billing checks for testing.
ADMIN_TEST_EMAILS=
```

### Step 1.2 — Add to GCP Secret Manager (for production)

This step is done in the GCP Console, not in Cursor. After implementing the code changes below, you will need to:

1. Go to GCP Console → Secret Manager
2. Find the secret that stores your API environment variables
3. Add `ADMIN_TEST_EMAILS=ron@winnowcc.com,hello@winnowcc.com,team@winnowcc.com`
4. Redeploy Cloud Run to pick up the new variable

(We'll remind you at the end of this prompt.)

---

## PART 2 — Add Admin Check to Billing Service

This is the core change. You will add ONE helper function and modify FOUR existing functions.

### Step 2.1 — Add the `is_admin_tester()` helper

**File to edit:** `services/api/app/services/billing.py`

Open `billing.py` in Cursor. Find the imports section at the top of the file. Add this import if not already present:

```python
import os
```

Now find the section where `CANDIDATE_PLAN_LIMITS` is defined (it should be near the top, after imports). **Immediately ABOVE** the `CANDIDATE_PLAN_LIMITS` dict, add this new function:

```python
# ── Admin Test Mode ────────────────────────────────────────────

def is_admin_tester(user_email: str) -> bool:
    """
    Check if a user email is in the admin test list.
    Admin testers bypass ALL billing tier checks and daily limits.
    Controlled by the ADMIN_TEST_EMAILS environment variable.
    Returns False if the env var is empty or not set.
    """
    admin_emails_raw = os.environ.get("ADMIN_TEST_EMAILS", "")
    if not admin_emails_raw.strip():
        return False
    admin_emails = [e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()]
    return user_email.lower() in admin_emails


def get_admin_max_tier(segment: str) -> str:
    """
    Return the highest tier name for a given segment.
    Used to give admin testers full access to all features.
    """
    tier_map = {
        "candidate": "pro",
        "employer": "pro",       # or "enterprise" if you want enterprise-level
        "recruiter": "agency",   # or "enterprise" if you want enterprise-level
    }
    return tier_map.get(segment, "pro")
```

### Step 2.2 — Modify `get_user_plan()` to return top tier for admins

**File to edit:** `services/api/app/services/billing.py` (same file, keep it open)

Find the existing `get_user_plan()` function. It currently looks something like this:

```python
def get_user_plan(user_id: int, db: Session) -> str:
    """Return the user's current plan name ('free' or 'pro')."""
    sub = get_or_create_subscription(user_id, db)
    if sub.plan == "pro" and sub.status in ("active", "trialing"):
        return "pro"
    return "free"
```

**Replace the entire function** with this version. The ONLY change is adding the admin check at the very top, before any database lookups:

```python
def get_user_plan(user_id: int, db: Session, segment: str = "candidate", user_email: str = None) -> str:
    """
    Return the user's current plan name.
    Admin testers always get the highest tier for their segment.
    
    Args:
        user_id: The user's database ID
        db: Database session
        segment: 'candidate', 'employer', or 'recruiter'
        user_email: Optional — if provided, checked against admin list.
                    If not provided, looked up from DB.
    """
    # ── Admin bypass ──
    if user_email is None:
        # Look up email from the users table
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user_email = user.email
    
    if user_email and is_admin_tester(user_email):
        return get_admin_max_tier(segment)
    
    # ── Normal billing logic (existing code below — do not change) ──
    sub = get_or_create_subscription(user_id, db)
    if sub.plan == "pro" and sub.status in ("active", "trialing"):
        return "pro"
    return "free"
```

**IMPORTANT:** The existing logic after the admin check must remain exactly as it is now in your codebase. The snippet above shows the original two-tier version. Your actual code may have more tiers (starter, pro, etc.) — keep all of that. Only add the admin bypass block at the top.

### Step 2.3 — Modify `check_feature_access()` to skip for admins

Find the `check_feature_access()` function in the same file. Add the admin bypass as the **very first check** inside the function, before any other logic:

```python
def check_feature_access(user, feature: str, db: Session = None, **kwargs):
    """Check if a user's plan allows access to a feature."""
    
    # ── Admin bypass — skip ALL feature gates ──
    user_email = getattr(user, 'email', None)
    if user_email and is_admin_tester(user_email):
        return True
    
    # ── Existing logic below (do NOT change anything below this line) ──
    # ... rest of existing function stays exactly the same ...
```

**Note:** Your actual function signature may differ slightly (it might accept `request`, `segment`, etc.). Keep the existing signature. Just add the 3-line admin check at the very top of the function body.

### Step 2.4 — Modify `check_daily_limit()` to skip for admins

Find the `check_daily_limit()` function. Same pattern — add admin bypass at the top:

```python
def check_daily_limit(user_id: int, feature: str, limit: int, db: Session, user_email: str = None):
    """Check if user has exceeded daily limit for a feature."""
    
    # ── Admin bypass — skip ALL daily limits ──
    if user_email and is_admin_tester(user_email):
        return True, "Admin test mode — no limits"
    
    # If email not passed, look it up
    if user_email is None:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if user and is_admin_tester(user.email):
            return True, "Admin test mode — no limits"
    
    # ── Existing logic below (do NOT change anything below this line) ──
    # ... rest of existing function stays exactly the same ...
```

**Note:** The return format `(True, "message")` matches the existing pattern where this function returns a tuple of `(allowed: bool, message: str)`. If your version returns differently (e.g., raises an HTTPException), adapt the admin bypass to match. The key point: admin testers should always pass through.

### Step 2.5 — Modify `increment_daily_counter()` to skip for admins

Find the `increment_daily_counter()` function. Add admin bypass so counters don't increment for admin testers (keeps the database clean):

```python
def increment_daily_counter(user_id: int, feature: str, db: Session, user_email: str = None):
    """Increment the daily usage counter for a feature."""
    
    # ── Admin bypass — don't increment counters ──
    if user_email and is_admin_tester(user_email):
        return  # Skip — admin testers don't consume quota
    
    if user_email is None:
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if user and is_admin_tester(user.email):
            return  # Skip
    
    # ── Existing logic below (do NOT change anything below this line) ──
    # ... rest of existing function stays exactly the same ...
```

---

## PART 3 — Pass Email to Billing Checks in Routers

The billing helper functions now accept `user_email` as an optional parameter. For the admin bypass to work efficiently (without extra DB lookups), pass the email from the router where `current_user` is already available.

### Step 3.1 — Update router calls (pattern to follow)

You do NOT need to change every router right now. The admin bypass will still work without this step because the functions fall back to looking up the email from the database. However, for efficiency, you can update the most commonly used routers.

**Pattern:** Wherever you see this in a router:

```python
# OLD — works but does an extra DB lookup for admin check
plan = get_user_plan(current_user.id, db)
```

Change it to:

```python
# NEW — passes email directly, avoids extra DB lookup
plan = get_user_plan(current_user.id, db, segment="candidate", user_email=current_user.email)
```

And wherever you see:

```python
# OLD
allowed, msg = check_daily_limit(current_user.id, "sieve_messages", daily_limit, db)
```

Change it to:

```python
# NEW
allowed, msg = check_daily_limit(current_user.id, "sieve_messages", daily_limit, db, user_email=current_user.email)
```

**Priority routers to update** (these are the ones you'll test most):

| Router file | Path | What it gates |
|---|---|---|
| `services/api/app/routers/matches.py` | GET /api/matches | `matches_visible` limit |
| `services/api/app/routers/tailor.py` | POST /api/tailor/{job_id} | `tailored_resumes_per_month` |
| `services/api/app/routers/sieve.py` | POST /api/sieve/chat | `sieve_messages_per_day` |
| `services/api/app/routers/candidate_insights.py` | GET /api/insights/* | Pro-only career intelligence |
| `services/api/app/routers/billing.py` | GET /api/billing/status | Plan display |
| `services/api/app/routers/employer.py` | Various | Employer feature gates |
| `services/api/app/routers/recruiter.py` | Various | Recruiter feature gates |
| `services/api/app/routers/interview_coaching.py` | POST/GET coaching | `interview_coaching_per_day` |

**You can update these incrementally.** The fallback DB lookup means the bypass works everywhere immediately — the router updates just make it faster.

---

## Verification Checklist

After implementing all three parts, verify the following:

### Local Testing

1. **Set the env var locally:**
   - Open `services/api/.env`
   - Confirm `ADMIN_TEST_EMAILS=ron@winnowcc.com,hello@winnowcc.com,team@winnowcc.com` is present
   - Restart the API server (`uvicorn app.main:app --reload`)

2. **Test candidate Pro features with a free account:**
   - Log in as a candidate with email `ron@winnowcc.com` who is on the `free` tier
   - Try to access career intelligence (Pro only) → Should work
   - Try to generate a tailored resume → Should work (no limit)
   - Try semantic search → Should work (no daily cap)
   - Try Sieve chat → Should work (no message limit)

3. **Test employer Pro features:**
   - Log in as an employer with admin email
   - All employer features should be accessible regardless of plan

4. **Test recruiter Agency features:**
   - Log in as a recruiter with admin email
   - Agency-level features (invoicing, full pipeline, career trajectory AI) should be accessible

5. **Test that non-admin users are still gated:**
   - Log in with a non-admin email on the free tier
   - Verify that feature gates still block access as expected
   - This confirms the bypass only applies to admin emails

6. **Test disabling admin mode:**
   - Set `ADMIN_TEST_EMAILS=` (empty) in `.env`
   - Restart the API
   - Verify that the previously-admin email is now blocked by tier gates again

### Production Deployment

After local verification passes:

1. Go to **GCP Console → Secret Manager**
2. Find the secret used by your Cloud Run API service
3. Create a new version that includes: `ADMIN_TEST_EMAILS=ron@winnowcc.com,hello@winnowcc.com,team@winnowcc.com`
4. Go to **Cloud Run → winnow-api service → Edit & Deploy New Revision**
5. Verify the secret is mapped to the container
6. Deploy the new revision
7. Test on `https://winnowcc.ai` with your admin accounts

---

## Security Notes

- The admin email list is controlled **only** by server-side environment variables — it cannot be set or modified by API requests, frontend code, or user input.
- Admin bypass is invisible to the frontend — the API simply returns data as if the user has a top-tier plan.
- No Stripe subscriptions are created, no webhooks are triggered, no charges occur.
- To revoke admin test access, simply remove the email from `ADMIN_TEST_EMAILS` and restart/redeploy.
- The `ADMIN_TEST_EMAILS` variable is separate from `ADMIN_TOKEN` (used for admin API endpoints). They serve different purposes and don't conflict.

---

## Post-Implementation: Update CLAUDE.md and AGENTS.md

After successful Cursor implementation, add this note to the **Current State** section of your project memory:

> **Admin Test Mode (PROMPT79):** `ADMIN_TEST_EMAILS` env var in billing.py enables designated emails to bypass all tier checks, daily limits, and feature gates across all segments. No Stripe interaction. Controlled server-side only.
