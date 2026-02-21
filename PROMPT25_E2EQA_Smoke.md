# PROMPT25_E2EQA_Smoke.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and all existing PROMPT files before making changes.

## Purpose

Systematically verify every feature built across PROMPTs 1–24 by walking through every user flow end-to-end on both web and mobile, running automated test suites, validating infrastructure health, and fixing any integration bugs found. This is the final quality gate before launch.

**This is NOT a "write new features" prompt.** This is a structured QA pass that:
1. Runs all existing automated tests and fixes failures
2. Walks through every core user flow manually
3. Validates infrastructure (DB, Redis, queues, Cloud Run, Sentry, monitoring)
4. Documents bugs found and fixes them inline
5. Produces a signed-off QA checklist

---

## Triggers — When to Use This Prompt

- All v1 features are implemented and you're preparing for launch.
- You want to verify end-to-end flows after a large merge or refactor.
- You suspect integration bugs between features built in different PROMPTs.
- Pre-deploy smoke testing before pushing to production.

---

## What Already Exists

Every feature referenced below has been implemented. This prompt validates them:

### Backend (services/api/)
- Auth: signup, login, logout, me, Bearer token + cookie (`routers/auth.py`, `services/auth.py`)
- Profile: get, update, completeness, versioning (`routers/profile.py`)
- Resume: upload, parse (async via RQ) (`routers/resume.py`)
- Matches: list, detail, search, status update, refresh (`routers/matches.py`)
- Dashboard: 5 KPI metrics (`routers/dashboard.py`)
- Tailor: generate, status poll, download, detail with change log (`routers/tailor.py`)
- Tracking: application status (saved/applied/interviewing/rejected/offer)
- Billing: Stripe checkout, portal, webhook, usage, status (`routers/billing.py`)
- Sieve: chat, triggers, history, clear (`routers/sieve.py`)
- Data export: ZIP download (`routers/export.py` or equivalent)
- Account deletion: cascade delete
- Admin: observability, queues, trust, security posture
- Health: `/health`, `/ready`

### Frontend (apps/web/)
- Landing/login page, signup, auth guards
- Dashboard with 5 KPI cards + pipeline visualization
- Profile page (view + edit)
- Resume upload page
- Matches list (search, filters, status picker)
- Match detail (scores, reasons, gaps, generate ATS resume, status)
- Tailored resume "What Changed" page
- Settings (billing, data export, account deletion)
- Sieve chatbot widget (LLM-powered + proactive triggers)

### Mobile (apps/mobile/)
- Login/signup screens
- Dashboard tab (metrics, plan badge)
- Matches tab (list, pull-to-refresh)
- Job detail (scores, status picker, generate resume, download/share)
- Profile tab (preferences edit, logout)

### Infrastructure
- Docker Compose: Postgres + Redis
- Cloud Run: winnow-api, winnow-worker, winnow-web
- Cloud SQL, GCS, Secret Manager, Cloud Scheduler
- Sentry (API + web + worker)
- Structured logging, GCP monitoring dashboards + alerts
- GitHub Actions CI/CD

### Test Infrastructure
- `services/api/tests/` — pytest test suite with conftest.py, helpers, per-router test files
- `apps/web/e2e/` — Playwright e2e tests
- `.github/workflows/ci.yml` — CI pipeline

---

## QA Execution Plan

This prompt is organized into 8 phases. Execute them in order.

---

# PHASE 1 — ENVIRONMENT SETUP + INFRASTRUCTURE CHECK

Before testing flows, verify the foundation is healthy.

### Step 1: Start all local services

Open **PowerShell Window #1** — Infrastructure:
```powershell
cd C:\Users\ronle\Documents\resumematch\infra
docker compose up -d
```

Verify containers are running:
```powershell
docker ps
```

You should see `postgres` and `redis` containers running.

### Step 2: Run database migrations

**PowerShell Window #2** — API:
```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Verify: no errors. If there are migration conflicts, resolve them before continuing.

### Step 3: Start the API server

Same window:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Start the worker

**PowerShell Window #3** — Worker:
```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1
python -m rq.cli worker --with-scheduler
```

### Step 5: Start the web app

**PowerShell Window #4** — Web:
```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
npm run dev
```

### Step 6: Verify health endpoints

Open a browser or PowerShell and check:

```powershell
# Basic health (should return status: ok)
curl http://localhost:8000/health

# Readiness (should return status: ok, checks.database: ok, checks.redis: ok)
curl http://localhost:8000/ready
```

**If `/ready` shows `degraded`:** Check which service (database or redis) is failing and fix it before continuing.

### Step 7: Verify Swagger docs load

Open in browser:
```
http://127.0.0.1:8000/docs
```

Verify: Swagger UI loads with all endpoints listed. Scroll through and confirm you see routes for `/api/auth`, `/api/profile`, `/api/matches`, `/api/tailor`, `/api/sieve`, `/api/billing`, `/api/dashboard`.

---

# PHASE 2 — AUTOMATED TEST SUITES

### Step 8: Run API pytest suite

```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1

# Create test database if it doesn't exist
docker exec -it infra-postgres-1 psql -U resumematch -c "CREATE DATABASE resumematch_test;" 2>$null

$env:TEST_DB_URL="postgresql://resumematch:resumematch@localhost:5432/resumematch_test"
python -m pytest tests/ -v --tb=short
```

**Expected:** All tests pass. If any fail:
1. Read the failure message carefully
2. Determine if it's a real bug or a test environment issue
3. Fix the underlying code (not just the test) if it's a real bug
4. Re-run until all pass

### Step 9: Run pytest with coverage

```powershell
python -m pytest tests/ -v --cov=app --cov-report=term-missing --tb=short
```

**Expected:** Coverage ≥ 50% on critical paths (auth, profile, matches, tailor, billing).

### Step 10: Run API linting

```powershell
cd C:\Users\ronle\Documents\resumematch\services\api
python -m ruff check .
python -m ruff format --check .
```

**Expected:** No errors. If there are lint errors, fix them:
```powershell
python -m ruff check . --fix
python -m ruff format .
```

### Step 11: Run web linting

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
npm run lint
```

**Expected:** No errors or only warnings.

### Step 12: Run Playwright e2e tests

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
npx playwright test
```

**Expected:** All e2e tests pass. If Playwright is not installed yet:
```powershell
npx playwright install
npx playwright test
```

---

# PHASE 3 — WEB APP: CORE USER FLOWS

Open `http://localhost:3000` in your browser. Walk through each flow and check every item.

### Flow A: Auth (PROMPT6 + AUTH PROMPT)

**Step 13: Landing page**
- [ ] Landing page loads with login form
- [ ] Brand colors (hunter green, gold) display correctly
- [ ] No console errors (open DevTools → Console)

**Step 14: Signup**
- [ ] Click "Sign Up" or navigate to signup page
- [ ] Enter a NEW test email (e.g., `qatest@winnow.dev`) and a valid password
- [ ] Click submit → redirects to onboarding or dashboard
- [ ] No error messages

**Step 15: Logout**
- [ ] Click logout (profile menu or settings)
- [ ] Redirected to login page
- [ ] Visiting `/dashboard` redirects back to login (auth guard works)

**Step 16: Login**
- [ ] Enter the test credentials from Step 14
- [ ] Click login → redirects to dashboard
- [ ] Wrong password shows error message (not a crash)
- [ ] Nonexistent email shows same generic error (not "user not found")

### Flow B: Profile + Resume (PROMPT3, 4, 9)

**Step 17: Resume upload**
- [ ] Navigate to Upload page
- [ ] Upload a PDF or DOCX resume
- [ ] Upload progress/status shown (processing indicator)
- [ ] After parsing completes, profile page populates with extracted data
- [ ] Check the worker terminal (Window #3) — you should see the parse job running

**Step 18: Profile review**
- [ ] Navigate to Profile page
- [ ] Name, title, skills, experience, education visible
- [ ] Profile completeness score displayed
- [ ] Deficiencies/recommendations shown if profile is incomplete

**Step 19: Profile edit**
- [ ] Edit a field (e.g., add a skill, change a preference)
- [ ] Save → confirmation shown
- [ ] Refresh page → changes persisted
- [ ] Profile version incremented (check API: `GET /api/profile` returns updated `version`)

### Flow C: Matching (PROMPT5, 7, 15)

**Step 20: Matches list**
- [ ] Navigate to Matches page
- [ ] Job match cards displayed with: title, company, location, match score, interview readiness
- [ ] Each card shows matched skills (green) and missing skills (amber)
- [ ] Matches sorted by score (highest first)
- [ ] If no matches: empty state with CTA to upload resume

**Step 21: Search**
- [ ] Type in the search bar (e.g., "python backend developer")
- [ ] Results update (semantic search)
- [ ] Clear search → full list returns

**Step 22: Match detail**
- [ ] Click a match card
- [ ] Job detail page shows: title, company, location, salary range, description
- [ ] Match score and interview readiness displayed prominently
- [ ] Reasons section: matched skills with evidence
- [ ] Gaps section: missing skills with recommendations
- [ ] Application status picker visible (saved/applied/interviewing/rejected/offer)

**Step 23: Status update**
- [ ] Change application status on a match (e.g., "saved" → "applied")
- [ ] Status saved (refresh page — it persists)
- [ ] Dashboard metrics update to reflect the change

### Flow D: Tailored Resume Generation (PROMPT12)

**Step 24: Generate tailored resume**
- [ ] On a match detail page, click "Generate ATS Resume"
- [ ] Loading/progress indicator shown
- [ ] Check worker terminal — tailoring job runs
- [ ] On completion: "What Changed" page or download link appears

**Step 25: Download + review**
- [ ] Download the DOCX file
- [ ] Open in Word — verify it's properly formatted (single column, standard headings, no tables)
- [ ] Verify NO hallucinated employers, titles, dates, or credentials
- [ ] Change log is accessible (shows what was modified and why)
- [ ] Keyword alignment summary visible

**Step 26: Cover letter**
- [ ] If cover letter was generated, download and verify
- [ ] Grounded in the user's actual experience
- [ ] No fabricated claims

### Flow E: Dashboard Metrics (PROMPT8)

**Step 27: Dashboard**
- [ ] Navigate to Dashboard
- [ ] 5 KPI metric cards visible:
  - Profile Completeness (percentage)
  - Qualified Jobs (count)
  - Applications Submitted (count)
  - Interviews Requested (count)
  - Offers Received (count)
- [ ] Clicking "Profile Completeness" navigates to `/profile`
- [ ] Clicking "Qualified Jobs" navigates to `/matches`
- [ ] Pipeline/funnel visualization displayed below cards
- [ ] Metrics reflect actual data (match the counts from Matches page)

### Flow F: Sieve Chatbot (PROMPT18, 24)

**Step 28: Open Sieve**
- [ ] Sieve FAB (gold circle) visible in bottom-right corner
- [ ] Click FAB → chat panel opens with brand styling
- [ ] Greeting message displayed
- [ ] Proactive trigger(s) shown (e.g., "Your profile is X% complete...")

**Step 29: Chat interaction**
- [ ] Type a message (e.g., "What are my top matches?")
- [ ] Typing indicator shown
- [ ] Response is contextual (references your actual data, not generic)
- [ ] Quick-reply suggestion buttons appear below response
- [ ] Tap a suggestion → prefills or sends

**Step 30: Trigger actions**
- [ ] If a trigger has an action button (e.g., "Complete Profile"), tap it
- [ ] Verify it navigates to the correct page
- [ ] Dismiss a trigger → it disappears
- [ ] Close and reopen Sieve → conversation history persisted

### Flow G: Billing + Subscription (PROMPT20)

**Step 31: Billing page**
- [ ] Navigate to Settings or Billing page
- [ ] Current plan displayed (Free or Pro)
- [ ] Usage shown (tailored resumes used / limit)
- [ ] "Upgrade" button visible if on free plan

**Step 32: Stripe checkout** (use Stripe test mode)
- [ ] Click upgrade → redirects to Stripe Checkout
- [ ] Use test card: `4242 4242 4242 4242`, any future expiry, any CVC
- [ ] After payment → redirected back to app
- [ ] Plan shows "Pro"
- [ ] Usage limits updated

**Step 33: Stripe portal**
- [ ] Click "Manage Subscription" → Stripe Customer Portal opens
- [ ] Can view invoices, update payment method, cancel
- [ ] After returning to app, status reflects any changes

### Flow H: Data Export + Account Deletion (PROMPT19)

**Step 34: Data export**
- [ ] Navigate to Settings → Data Export
- [ ] Click "Export My Data"
- [ ] ZIP file downloads
- [ ] Unzip and verify contents: profile JSON, resume files, matches, tailored resumes

**Step 35: Account deletion** (use a throwaway test account!)
- [ ] Navigate to Settings → Delete Account
- [ ] Confirmation prompt appears (not instant delete)
- [ ] Confirm → account deleted
- [ ] Redirected to login page
- [ ] Logging in with deleted credentials fails
- [ ] Check DB: all user data cascade-deleted (profiles, matches, tailored resumes, sieve conversations)

---

# PHASE 4 — MOBILE APP FLOWS

Start the mobile dev server if not already running:
```powershell
cd C:\Users\ronle\Documents\resumematch\apps\mobile
npx expo start --offline
```

Scan QR code with your phone (Expo Go app).

### Step 36: Mobile login
- [ ] Login screen displays with brand styling (hunter green + gold)
- [ ] Enter valid credentials → navigates to dashboard tab
- [ ] Wrong password → error message (not crash)

### Step 37: Mobile dashboard
- [ ] Dashboard tab shows metric cards
- [ ] Plan badge visible (Free/Pro)
- [ ] "View Matches" button works

### Step 38: Mobile matches
- [ ] Matches tab shows list of match cards
- [ ] Pull down to refresh → list reloads
- [ ] Each card shows: title, company, score badge, top skills
- [ ] Tap a card → navigates to job detail

### Step 39: Mobile job detail
- [ ] Match score and interview readiness displayed
- [ ] Reasons (matched skills) and gaps (missing skills) shown
- [ ] Application status picker works (change and save)
- [ ] "Generate ATS Resume" button → loading → completion
- [ ] Download/Share button → native share sheet opens

### Step 40: Mobile profile
- [ ] Profile tab shows editable preferences
- [ ] Edit a preference (e.g., remote preference) → Save → persists
- [ ] "Log Out" button → returns to login screen
- [ ] Reopen app → still logged in (token persisted)

---

# PHASE 5 — API ENDPOINT VALIDATION

Use Swagger UI at `http://127.0.0.1:8000/docs` or PowerShell curl commands to verify endpoints that aren't easily tested via UI.

### Step 41: Auth endpoints
```powershell
# Signup (should return user_id, email, token)
curl -X POST http://localhost:8000/api/auth/signup -H "Content-Type: application/json" -d '{\"email\":\"apitest@winnow.dev\",\"password\":\"TestPass123!\"}'

# Login (should return user_id, email, token, onboarding_complete)
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{\"email\":\"apitest@winnow.dev\",\"password\":\"TestPass123!\"}'

# Me (use the token from login)
curl http://localhost:8000/api/auth/me -H "Authorization: Bearer YOUR_TOKEN"
```
- [ ] Signup returns 200 with user_id, email, token
- [ ] Login returns 200 with token
- [ ] Me returns 200 with user info when token is valid
- [ ] Me returns 401 when token is missing or invalid

### Step 42: Admin/observability endpoints
```powershell
# System health
curl "http://localhost:8000/api/admin/observability/health?admin_token=dev-admin-token"

# Queue stats
curl "http://localhost:8000/api/admin/observability/queues?admin_token=dev-admin-token"

# Security posture
curl "http://localhost:8000/api/admin/security-posture?admin_token=dev-admin-token"
```
- [ ] Observability health returns API + DB + Redis status
- [ ] Queue stats returns pending/started/failed counts per queue
- [ ] Security posture returns enabled security features

### Step 43: Sieve endpoints
```powershell
# Chat (use a valid Bearer token)
curl -X POST http://localhost:8000/api/sieve/chat -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_TOKEN" -d '{\"message\":\"What are my top matches?\",\"conversation_history\":[]}'

# Triggers
curl -X POST http://localhost:8000/api/sieve/triggers -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_TOKEN" -d '{\"dismissed_ids\":[]}'

# History
curl http://localhost:8000/api/sieve/history -H "Authorization: Bearer YOUR_TOKEN"
```
- [ ] Chat returns a contextual response with suggestions
- [ ] Triggers returns a list of applicable triggers
- [ ] History returns saved conversation messages

### Step 44: Billing endpoints
```powershell
# Billing status
curl http://localhost:8000/api/billing/status -H "Authorization: Bearer YOUR_TOKEN"
```
- [ ] Returns plan, usage counts, and limits

---

# PHASE 6 — SECURITY VALIDATION (PROMPT21)

### Step 45: Rate limiting
- [ ] Hit `/api/auth/login` 11+ times in 1 minute with wrong credentials → returns 429 "Too Many Requests"
- [ ] Hit `/api/sieve/chat` 31+ times in 1 minute → returns 429

### Step 46: Security headers
Open DevTools (F12) → Network tab → click any response → check headers:
- [ ] `X-Content-Type-Options: nosniff` present
- [ ] `X-Frame-Options: DENY` present
- [ ] `Strict-Transport-Security` present (in production)
- [ ] `X-XSS-Protection: 1; mode=block` present

### Step 47: Input validation
- [ ] Try uploading a `.exe` file as a resume → rejected
- [ ] Try a login with SQL injection (`' OR 1=1--`) → rejected (not a server error)
- [ ] Try XSS in profile fields (`<script>alert('xss')</script>`) → sanitized, not executed

### Step 48: Auth hardening
- [ ] Accessing any `/api/` endpoint without auth → 401
- [ ] Using an expired/invalid token → 401
- [ ] Admin endpoints without `admin_token` → 401 or 403

---

# PHASE 7 — WORKER + QUEUE VALIDATION

### Step 49: Worker processing
- [ ] Upload a new resume → check worker terminal → parse job appears and completes
- [ ] Trigger a tailored resume → check worker terminal → tailor job runs
- [ ] Check admin queue endpoint → no stuck failed jobs

### Step 50: Failed job handling
```powershell
# Check for failed jobs
curl "http://localhost:8000/api/admin/observability/queues?admin_token=dev-admin-token"
```
- [ ] Failed count is 0 (or known/expected failures)
- [ ] If failed jobs exist, check details:
```powershell
curl "http://localhost:8000/api/admin/observability/queues/parse/failed?admin_token=dev-admin-token"
```
- [ ] Review error messages and fix root causes

---

# PHASE 8 — BUG FIX + SIGN-OFF

### Step 51: Fix any bugs found

For each bug found during Phases 2–7:
1. Document the bug (what flow, what happened, what was expected)
2. Identify the root cause file
3. Fix the code
4. Re-test that specific flow
5. Re-run the automated test suite to ensure no regressions

### Step 52: Re-run all automated tests

```powershell
# API tests
cd C:\Users\ronle\Documents\resumematch\services\api
.\.venv\Scripts\Activate.ps1
$env:TEST_DB_URL="postgresql://resumematch:resumematch@localhost:5432/resumematch_test"
python -m pytest tests/ -v --tb=short

# Lint
python -m ruff check .
python -m ruff format --check .

# Web lint
cd C:\Users\ronle\Documents\resumematch\apps\web
npm run lint

# E2E
npx playwright test
```

**All must pass before sign-off.**

### Step 53: Final sign-off checklist

Print or copy this checklist. Every item must be checked:

```
═══════════════════════════════════════════════════
  WINNOW v1 QA SIGN-OFF — Date: ___________
═══════════════════════════════════════════════════

INFRASTRUCTURE
  [ ] Docker Compose: Postgres + Redis running
  [ ] Migrations: alembic upgrade head — no errors
  [ ] Health: /health returns ok
  [ ] Ready: /ready returns ok (DB + Redis)
  [ ] Swagger: /docs loads with all endpoints
  [ ] Worker: RQ worker running and processing jobs

AUTOMATED TESTS
  [ ] pytest: all tests pass
  [ ] Coverage: ≥ 50% on critical paths
  [ ] Ruff: no lint errors
  [ ] Web lint: no errors
  [ ] Playwright e2e: all tests pass

WEB — AUTH
  [ ] Landing page loads
  [ ] Signup works
  [ ] Login works
  [ ] Logout works
  [ ] Auth guards redirect unauthenticated users
  [ ] Invalid credentials show error message

WEB — PROFILE + RESUME
  [ ] Resume upload works (PDF and DOCX)
  [ ] Parsing completes (worker processes job)
  [ ] Profile populates with extracted data
  [ ] Profile edit + save persists changes
  [ ] Profile completeness score accurate

WEB — MATCHING
  [ ] Matches list displays with scores
  [ ] Search bar returns results
  [ ] Match detail shows reasons + gaps
  [ ] Application status change persists
  [ ] Dashboard metrics update after status change

WEB — TAILORED RESUME
  [ ] Generate ATS Resume triggers worker job
  [ ] DOCX downloads successfully
  [ ] Content is grounded (no hallucinations)
  [ ] Change log accessible and accurate
  [ ] Cover letter generated (if applicable)

WEB — DASHBOARD
  [ ] 5 KPI cards display correct data
  [ ] Pipeline visualization renders
  [ ] Cards link to correct pages

WEB — SIEVE
  [ ] Widget opens with brand styling
  [ ] Proactive triggers display
  [ ] Chat returns contextual LLM responses
  [ ] Quick-reply suggestions work
  [ ] Conversation history persists
  [ ] Trigger dismiss works

WEB — BILLING
  [ ] Current plan displayed
  [ ] Stripe Checkout works (test mode)
  [ ] Plan updates after payment
  [ ] Stripe Customer Portal accessible

WEB — DATA EXPORT + DELETION
  [ ] ZIP export downloads with correct contents
  [ ] Account deletion cascades all data

MOBILE
  [ ] Login works
  [ ] Dashboard tab shows metrics
  [ ] Matches tab shows list with pull-to-refresh
  [ ] Job detail shows scores + reasons + gaps
  [ ] Status picker works
  [ ] Generate + download tailored resume works
  [ ] Profile edit + save works
  [ ] Logout + re-login works (token persisted)

API DIRECT
  [ ] Auth endpoints (signup/login/me) return correct responses
  [ ] Admin observability endpoints work
  [ ] Sieve chat/triggers/history endpoints work
  [ ] Billing status endpoint works

SECURITY
  [ ] Rate limiting enforced (429 on excess)
  [ ] Security headers present
  [ ] File upload validation rejects bad types
  [ ] SQL injection blocked
  [ ] XSS sanitized
  [ ] Auth required on all protected endpoints

WORKER
  [ ] Parse jobs complete successfully
  [ ] Tailor jobs complete successfully
  [ ] No stuck failed jobs in queues

SIGN-OFF
  Tester: ___________________
  Date:   ___________________
  Status: [ ] PASS  [ ] FAIL — bugs remaining: ____
═══════════════════════════════════════════════════
```

---

## Non-Goals (Do NOT implement in this prompt)

- Writing new features or adding functionality
- Performance testing or load testing
- Production deployment steps (that's Post-Launch Step 2+)
- Mobile app store submission
- Custom domain or DNS configuration
- Adding new tests for edge cases not covered by existing suite
- UI/UX redesign or visual polish

---

## Summary

This prompt walks through **53 verification steps** across **8 phases**:

| Phase | Steps | What |
|-------|-------|------|
| 1 — Environment Setup | 1–7 | Start services, verify health, check Swagger |
| 2 — Automated Tests | 8–12 | pytest, coverage, lint (API + web), Playwright e2e |
| 3 — Web App Flows | 13–35 | Auth, profile, resume, matching, tailor, dashboard, Sieve, billing, export, deletion |
| 4 — Mobile App Flows | 36–40 | Login, dashboard, matches, job detail, profile |
| 5 — API Validation | 41–44 | Direct endpoint testing via curl/Swagger |
| 6 — Security | 45–48 | Rate limiting, headers, input validation, auth hardening |
| 7 — Worker + Queues | 49–50 | Job processing, failed job review |
| 8 — Bug Fix + Sign-off | 51–53 | Fix bugs, re-test, final checklist |

Return code changes only (for bug fixes found during QA).
