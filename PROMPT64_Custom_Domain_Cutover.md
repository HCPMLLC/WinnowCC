# PROMPT64_Custom_Domain_Cutover.md

Read CLAUDE.md, ARCHITECTURE.md, PROMPT26_Custom_Domain.md, and tasks/lessons.md (especially lesson #20) before making changes.

## Purpose

Complete the custom domain cutover from Cloud Run default URLs (`*.run.app`) to `winnowcc.ai` (frontend) and `api.winnowcc.ai` (backend). This includes DNS configuration, Cloud Run domain mappings, SSL certificate provisioning, cookie domain scoping, Auth0 updates, Stripe webhook URL updates, Chrome extension URL updates, and verification.

---

## Triggers — When to Use This Prompt

- You are ready to go live on the permanent `winnowcc.ai` domain.
- The app is currently only accessible via ugly Cloud Run URLs like `winnow-web-cdn2d6pc5q-uc.a.run.app`.
- Lesson #20 in `tasks/lessons.md` says: "api.winnowcc.ai was set but no Cloud Run domain mapping or SSL cert existed."

---

## What Already Exists (DO NOT recreate)

Based on thorough codebase review (2026-02-28), these items are ALREADY CONFIGURED and need NO changes:

1. **CORS** (`services/api/app/main.py` lines 150-172): `https://winnowcc.ai` and `https://www.winnowcc.ai` already in `ALLOWED_ORIGINS`. Chrome extension regex pattern included. Dynamic `CORS_ORIGIN` env var supported.

2. **Deploy workflow** (`.github/workflows/deploy.yml`):
   - `FRONTEND_URL=https://winnowcc.ai` set on API (line 59), Worker (line 125), Scheduler (line 168)
   - `AUTH_COOKIE_SECURE=true` set on API
   - Web Docker build uses `NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai` and `NEXT_PUBLIC_APP_URL=https://winnowcc.ai` (lines 198-199)
   - Auth0 domain/client ID fetched from GCP Secret Manager (lines 200-201)
   - Sentry DSN, PostHog key/host passed as build args (lines 202-205)

3. **Web `.env.production`** (`apps/web/.env.production`): Has `NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai` and `NEXT_PUBLIC_APP_URL=https://winnowcc.ai`.

4. **Mobile `eas.json`** (`apps/mobile/eas.json`): Preview and Production profiles set `EXPO_PUBLIC_API_BASE_URL=https://api.winnowcc.ai`.

5. **Chrome extension manifest** (`apps/chrome-extension/manifest.json`): Host permissions include `https://api.winnowcc.ai/*`. Homepage URL is `https://winnowcc.ai`.

6. **Email (Resend)**: Already sends from `hello@winnowcc.ai`. DKIM fixed 2026-02-28. DMARC at `p=none` (planned upgrade to `p=quarantine` late March 2026).

7. **Redirect infrastructure** (`infra/redirect/Dockerfile` and `infra/redirect/nginx.conf`): Exist for winnowcc.io → winnowcc.ai redirect. NOT YET DEPLOYED.

8. **PostHog provider**: Already wired into `apps/web/app/layout.tsx`. Deploy workflow passes key from GitHub secrets. `.env.production` has placeholder `phc_YOUR_API_KEY_HERE`.

9. **Cloud Run URL in CORS**: `https://winnow-web-cdn2d6pc5q-uc.a.run.app` included as fallback (line 157).

---

## What Does NOT Exist Yet (MUST be created)

1. **Google Cloud DNS zones** for `winnowcc.ai` and `winnowcc.io`
2. **DNS records** (A, AAAA, CNAME) pointing domains to Cloud Run services
3. **Cloud Run domain mappings** for `winnowcc.ai`, `www.winnowcc.ai`, `api.winnowcc.ai`
4. **GCP managed SSL certificates** (auto-provision when domain mappings are created)
5. **`COOKIE_DOMAIN` env var support** in `set_auth_cookie()` and `clear_auth_cookie()` in auth.py
6. **Auth0 allowed callback/logout/web origin URLs** for winnowcc.ai
7. **Stripe webhook endpoint URL** updated to api.winnowcc.ai
8. **Chrome extension `popup.js` DEFAULT_API_URL** updated from localhost to production
9. **winnowcc.io redirect service** deployed to Cloud Run (or registrar forwarding configured)
10. **GCP uptime checks** updated from `*.run.app` to custom domain

---

## Domain Architecture

| Domain | Purpose | Maps To |
|--------|---------|---------|
| `winnowcc.ai` | Web app (frontend) | Cloud Run: `winnow-web` |
| `www.winnowcc.ai` | Redirect → `winnowcc.ai` | Cloud Run: `winnow-web` |
| `api.winnowcc.ai` | API server (backend) | Cloud Run: `winnow-api` |
| `winnowcc.io` | Defensive redirect → `winnowcc.ai` | Cloud Run: `winnow-redirect` or registrar forwarding |
| `www.winnowcc.io` | Defensive redirect → `winnowcc.ai` | Cloud Run: `winnow-redirect` or registrar forwarding |

---

## What to Build

7 phases, executed in strict order. Each phase finishes completely before starting the next.

**Estimated total time:** 2-4 hours (most is waiting for DNS and SSL).

---

## BEFORE YOU START — Accounts You Need

Make sure you can log into ALL of these before beginning:

1. **Domain registrar** — wherever you bought `winnowcc.ai` and `winnowcc.io` (Namecheap, Cloudflare, GoDaddy, Porkbun, etc.)
2. **Google Cloud Console** — `https://console.cloud.google.com`
3. **Auth0 Dashboard** — `https://manage.auth0.com`
4. **Stripe Dashboard** — `https://dashboard.stripe.com`
5. **PowerShell terminal** with `gcloud` CLI already set up

---

# PHASE 1 — DNS SETUP

**What this does:** DNS is like a phone book for the internet. Right now, when someone types `winnowcc.ai`, the internet doesn't know where to send them. We set up the phone book entries.

**Time:** 15 min work + 15-60 min waiting for propagation.

### Step 1.1: Create a DNS Zone for winnowcc.ai

Open PowerShell and run:

```powershell
gcloud dns managed-zones create winnowcc-ai `
  --dns-name="winnowcc.ai." `
  --description="Winnow primary domain" `
  --visibility=public
```

If it says "already exists" — that's fine, move on.

### Step 1.2: Create a DNS Zone for winnowcc.io

```powershell
gcloud dns managed-zones create winnowcc-io `
  --dns-name="winnowcc.io." `
  --description="Winnow defensive domain" `
  --visibility=public
```

### Step 1.3: Get the Nameserver Addresses

```powershell
gcloud dns managed-zones describe winnowcc-ai --format="value(nameServers)"
```

This prints something like: `ns-cloud-a1.googledomains.com.,ns-cloud-a2.googledomains.com.,ns-cloud-a3.googledomains.com.,ns-cloud-a4.googledomains.com.`

**Write these down.** You need them in the next step.

Do the same for winnowcc.io:
```powershell
gcloud dns managed-zones describe winnowcc-io --format="value(nameServers)"
```

**Write these down too.**

### Step 1.4: Point Your Domain Registrar to Google's Nameservers

1. Open your domain registrar website in a browser
2. Log in
3. Find `winnowcc.ai` in your domain list and click on it
4. Look for "Nameservers" or "DNS Settings" or "Custom Nameservers"
5. Change the nameservers to the 4 values from Step 1.3:
   - Nameserver 1: `ns-cloud-a1.googledomains.com` (yours may differ)
   - Nameserver 2: `ns-cloud-a2.googledomains.com`
   - Nameserver 3: `ns-cloud-a3.googledomains.com`
   - Nameserver 4: `ns-cloud-a4.googledomains.com`
6. Save
7. Do the same for `winnowcc.io`

### Step 1.5: Wait for Propagation

Wait **15 to 60 minutes**. No way to speed this up.

Check if it's done:
```powershell
nslookup -type=NS winnowcc.ai
```

If you see Google nameservers in the response, propagation is done.

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| "Zone already exists" error | Fine — zone was already created. Move on. |
| Can't find nameserver settings | Search "[registrar name] change nameservers" on Google |
| Not propagating after 60 min | Check you saved changes. Some registrars have a toggle for "Use custom nameservers" — flip it ON. |

### Rollback

Change nameservers back to your registrar's defaults. Everything reverts within an hour.

---

# PHASE 2 — MAP DOMAINS TO CLOUD RUN + SSL

**What this does:** Tell Google Cloud which service handles which domain. Google auto-provisions SSL certificates (the padlock icon).

**Time:** 15 min work + 15-60 min waiting for SSL.

### Step 2.1: Map winnowcc.ai → winnow-web

```powershell
gcloud beta run domain-mappings create `
  --service=winnow-web `
  --domain=winnowcc.ai `
  --region=us-central1
```

This prints DNS records. **Write down the A record IP address and AAAA IPv6 address.**

### Step 2.2: Add DNS Records for winnowcc.ai

Replace `IP_ADDRESS` and `IPV6_ADDRESS` with actual values from Step 2.1:

```powershell
gcloud dns record-sets create winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=A `
  --ttl=300 `
  --rrdatas="IP_ADDRESS"

gcloud dns record-sets create winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=AAAA `
  --ttl=300 `
  --rrdatas="IPV6_ADDRESS"
```

**Don't forget the period (`.`) after `winnowcc.ai.`** — it's required.

### Step 2.3: Map www.winnowcc.ai

```powershell
gcloud dns record-sets create www.winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."

gcloud beta run domain-mappings create `
  --service=winnow-web `
  --domain=www.winnowcc.ai `
  --region=us-central1
```

### Step 2.4: Map api.winnowcc.ai → winnow-api

```powershell
gcloud dns record-sets create api.winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."

gcloud beta run domain-mappings create `
  --service=winnow-api `
  --domain=api.winnowcc.ai `
  --region=us-central1
```

### Step 2.5: Set Up winnowcc.io Redirect

**Option A — Registrar Forwarding (easier):**

If your registrar supports "URL Forwarding" or "Domain Redirect":
1. Log into registrar → find winnowcc.io → "URL Forwarding"
2. Set 301 redirect: `winnowcc.io` → `https://winnowcc.ai`
3. Same for `www.winnowcc.io` → `https://winnowcc.ai`

**Option B — Cloud Run (if registrar doesn't support forwarding):**

Get your GCP Project ID:
```powershell
gcloud config get-value project
```

Replace `YOUR_PROJECT_ID` below:

```powershell
cd C:\Users\ronle\Documents\resumematch\infra\redirect

docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/winnow/redirect:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/winnow/redirect:latest

gcloud run deploy winnow-redirect `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/winnow/redirect:latest `
  --region=us-central1 `
  --platform=managed `
  --allow-unauthenticated `
  --port=8080 `
  --memory=128Mi `
  --cpu=1 `
  --min-instances=0 `
  --max-instances=2

gcloud beta run domain-mappings create `
  --service=winnow-redirect `
  --domain=winnowcc.io `
  --region=us-central1

gcloud beta run domain-mappings create `
  --service=winnow-redirect `
  --domain=www.winnowcc.io `
  --region=us-central1
```

Add DNS records (get IPs from domain mapping output):
```powershell
gcloud dns record-sets create winnowcc.io. `
  --zone=winnowcc-io `
  --type=A `
  --ttl=300 `
  --rrdatas="IP_ADDRESS"

gcloud dns record-sets create winnowcc.io. `
  --zone=winnowcc-io `
  --type=AAAA `
  --ttl=300 `
  --rrdatas="IPV6_ADDRESS"

gcloud dns record-sets create www.winnowcc.io. `
  --zone=winnowcc-io `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."
```

### Step 2.6: Wait for SSL Certificates

```powershell
gcloud beta run domain-mappings describe `
  --domain=winnowcc.ai `
  --region=us-central1

gcloud beta run domain-mappings describe `
  --domain=api.winnowcc.ai `
  --region=us-central1
```

Look for `certificateStatus: ACTIVE`. If it says `PROVISIONING`, wait 15-30 min and check again.

**DO NOT proceed to Phase 3 until ALL certificates show ACTIVE.** Users will see security warnings otherwise.

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| "Record already exists" | Run `gcloud dns record-sets list --zone=winnowcc-ai` to see existing records. Delete wrong ones with `gcloud dns record-sets delete winnowcc.ai. --zone=winnowcc-ai --type=A` |
| SSL stuck on PROVISIONING for 2+ hours | DNS hasn't propagated. Go back and verify Phase 1 Step 1.5. |
| "Domain mapping already exists" | Run `gcloud beta run domain-mappings list --region=us-central1` to see existing mappings. |

### Rollback

```powershell
gcloud beta run domain-mappings delete --domain=winnowcc.ai --region=us-central1
gcloud beta run domain-mappings delete --domain=api.winnowcc.ai --region=us-central1
gcloud beta run domain-mappings delete --domain=www.winnowcc.ai --region=us-central1
```

Old `*.run.app` URLs continue working — they are never removed.

---

# PHASE 3 — CODE CHANGES (3 Files)

**What this does:** Update the auth cookie to work across `winnowcc.ai` and `api.winnowcc.ai`, add the env var to the deploy workflow, and fix the Chrome extension default URL.

**Time:** 20 minutes.

### Step 3.1: Update auth.py — Add COOKIE_DOMAIN Support

**File:** `services/api/app/services/auth.py`

**WHY:** When you log in at `winnowcc.ai`, a cookie is set. But the API is at `api.winnowcc.ai`. By setting the cookie domain to `.winnowcc.ai` (with leading dot), the cookie works for BOTH domains. We also need to update `clear_auth_cookie` so logout properly deletes the domain-scoped cookie.

**Change 1:** After line 25 (`COOKIE_SECURE = ...`), add:
```python
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # e.g., ".winnowcc.ai" in production
```

**Change 2:** Replace the `set_auth_cookie` function (lines 87-97) with:
```python
def set_auth_cookie(response: Response, *, user_id: int, email: str) -> None:
    token = make_token(user_id=user_id, email=email)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax" if COOKIE_DOMAIN else ("none" if COOKIE_SECURE else "lax"),
        secure=COOKIE_SECURE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=60 * 60 * 24 * SESSION_DAYS,
    )
```

Key changes:
- Added `domain=COOKIE_DOMAIN` — cookie now works for all of `*.winnowcc.ai`
- Changed `samesite` logic — with cookie domain (production), use `"lax"` (more secure than `"none"`)

**Change 3:** Replace the `clear_auth_cookie` function (lines 100-101) with:
```python
def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
```

Key change: Added `domain=COOKIE_DOMAIN` so the browser knows which cookie to delete. Without this, logout won't work — the old cookie lingers.

### Step 3.2: Update deploy.yml — Add COOKIE_DOMAIN Env Var

**File:** `.github/workflows/deploy.yml`

**On line 59** (the API `--set-env-vars` line), add `::COOKIE_DOMAIN=.winnowcc.ai` after `AUTH_COOKIE_SECURE=true`:

**Before:**
```
AUTH_COOKIE_SECURE=true::EMBEDDING_PROVIDER=sentence-transformers
```

**After:**
```
AUTH_COOKIE_SECURE=true::COOKIE_DOMAIN=.winnowcc.ai::EMBEDDING_PROVIDER=sentence-transformers
```

**IMPORTANT:** The dot at the beginning of `.winnowcc.ai` is required. Without it, cookies only work for the exact domain, not subdomains.

### Step 3.3: Update Chrome Extension popup.js

**File:** `apps/chrome-extension/popup/popup.js`

**On line 15**, change:
```javascript
const DEFAULT_API_URL = "http://127.0.0.1:8000";
```

To:
```javascript
const DEFAULT_API_URL = "https://api.winnowcc.ai";
```

**Note:** The Auth0 domain and client ID on lines 16-17 are public client-side values (not secrets). They match the Auth0 tenant and are fine to leave as-is.

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| Login works but user gets logged out on navigation | Check `COOKIE_DOMAIN` is `.winnowcc.ai` (with dot) in API env vars. Check browser dev tools — cookie domain should show `.winnowcc.ai` |
| Can't log out | Check `clear_auth_cookie` has `domain=COOKIE_DOMAIN` |
| Old cookies from before | They expire in 7 days. Users can clear cookies manually. |

### Rollback

`git checkout -- services/api/app/services/auth.py .github/workflows/deploy.yml apps/chrome-extension/popup/popup.js`

---

# PHASE 4 — UPDATE AUTH0 (Social Login Settings)

**What this does:** Auth0 handles "Sign in with Google" and "Sign in with GitHub." Auth0 needs to know the app now lives at `winnowcc.ai`. Without this, social login breaks.

**Time:** 10 minutes.

### Step 4.1: Open Auth0 Settings

1. Go to `https://manage.auth0.com`
2. Log in
3. Left sidebar → **Applications** → **Applications**
4. Find your app (client ID: `wr752tl9vqPflOZ2bmmNRKThozGLMovP`)
5. Click to open settings

### Step 4.2: Update Allowed Callback URLs

Find the **Allowed Callback URLs** field. Add these (keep existing ones, separate with commas):

```
https://winnowcc.ai/api/auth/callback, https://www.winnowcc.ai/api/auth/callback
```

**WHY:** The web app constructs the callback as `${window.location.origin}/api/auth/callback` (see `apps/web/app/login/page.tsx`). On the custom domain, that becomes `https://winnowcc.ai/api/auth/callback`.

### Step 4.3: Update Allowed Logout URLs

Find **Allowed Logout URLs**. Add:
```
https://winnowcc.ai, https://www.winnowcc.ai
```

### Step 4.4: Update Allowed Web Origins

Find **Allowed Web Origins**. Add:
```
https://winnowcc.ai, https://www.winnowcc.ai
```

### Step 4.5: Save

Scroll to bottom → click **Save Changes**.

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| "Callback URL mismatch" after clicking Google/GitHub login | Typo in callback URL. Must be exactly `https://winnowcc.ai/api/auth/callback` |
| Forgot to save | Go back and click Save Changes |

### Rollback

No rollback needed — new URLs don't interfere with old ones. Both work simultaneously.

---

# PHASE 5 — UPDATE STRIPE (Payment Webhooks)

**What this does:** Stripe sends payment notifications (subscription created/updated/deleted) to your server. Currently hitting the old `*.run.app` URL — need to update to `api.winnowcc.ai`.

**Time:** 10 minutes.

### Step 5.1: Open Stripe Webhooks

1. Go to `https://dashboard.stripe.com`
2. Log in
3. Left sidebar → **Developers** → **Webhooks**

### Step 5.2: Update Candidate Billing Webhook

1. Find the webhook endpoint with URL `https://winnow-api-cdn2d6pc5q-uc.a.run.app/api/billing/webhook`
2. Click on it → **Update endpoint** (or three-dot menu)
3. Change URL to:
   ```
   https://api.winnowcc.ai/api/billing/webhook
   ```
4. Click **Update endpoint**

### Step 5.3: Update Employer Billing Webhook (If Separate)

If there's a second webhook for `/api/employer/billing/webhook`:
1. Click on it
2. Change URL to: `https://api.winnowcc.ai/api/employer/billing/webhook`
3. Save

### Step 5.4: Test

1. On the webhook page → **Send test webhook**
2. Select `checkout.session.completed`
3. Click Send
4. Should return `200` with a green checkmark

### Step 5.5: Webhook Signing Secret

The signing secret (`STRIPE_WEBHOOK_SECRET`) does NOT change when you edit an existing endpoint. No GCP Secret Manager update needed.

If you accidentally created a new endpoint instead of editing:
```powershell
echo -n "whsec_YOUR_NEW_SECRET" | gcloud secrets versions add stripe-webhook-secret --data-file=-
```

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| Test webhook returns error/timeout | SSL cert not active yet. Open `https://api.winnowcc.ai/health` in browser first. |
| Payments stop working | Check webhook URL for typos. Path must be `/api/billing/webhook` |

### Rollback

Change Stripe webhook URL back to old `*.run.app` URL.

---

# PHASE 6 — DEPLOY CODE CHANGES

**What this does:** Push the 3 code changes from Phase 3. GitHub Actions auto-deploys to Cloud Run.

**Time:** 15 minutes.

### Step 6.1: Verify Changes

```powershell
cd C:\Users\ronle\Documents\resumematch
git diff
```

Should show changes in exactly 3 files:
1. `services/api/app/services/auth.py` — COOKIE_DOMAIN support
2. `.github/workflows/deploy.yml` — COOKIE_DOMAIN env var
3. `apps/chrome-extension/popup/popup.js` — DEFAULT_API_URL

### Step 6.2: Commit and Push

```powershell
cd C:\Users\ronle\Documents\resumematch
git add services/api/app/services/auth.py .github/workflows/deploy.yml apps/chrome-extension/popup/popup.js
git commit -m "feat: add COOKIE_DOMAIN support for custom domain cutover and update Chrome extension API URL"
git push origin main
```

### Step 6.3: Watch Deploy

1. Go to your GitHub repo → Actions tab
2. Watch the "Deploy to GCP" workflow
3. Wait for all 4 jobs to go green: Deploy API, Deploy Worker, Deploy Scheduler, Deploy Web
4. Takes ~5-10 minutes

### Step 6.4: Verify COOKIE_DOMAIN Was Set

```powershell
gcloud run services describe winnow-api --region=us-central1 --format="get(spec.template.spec.containers[0].env)"
```

Look for `COOKIE_DOMAIN=.winnowcc.ai` in the output.

### What Could Go Wrong

| Problem | Fix |
|---------|-----|
| Deploy fails (red X) | Click failed step for error message. Likely syntax error in changed file. |
| COOKIE_DOMAIN missing from env vars | Check deploy.yml — make sure `::COOKIE_DOMAIN=.winnowcc.ai::` separators are correct |

### Rollback

```powershell
git revert HEAD
git push origin main
```

---

# PHASE 7 — VERIFICATION + MONITORING UPDATES

**What this does:** Test everything on the custom domain. Update monitoring tools.

**Time:** 30 minutes.

### Step 7.1: Test Web App

1. Open **incognito/private** browser window (avoids old cookies)
2. Go to `https://winnowcc.ai`
3. **Check:** Landing page loads with padlock icon (SSL) in address bar

### Step 7.2: Test API

1. Go to `https://api.winnowcc.ai/health`
2. **Check:** Shows `{"status":"ok"}`
3. Go to `https://api.winnowcc.ai/ready`
4. **Check:** Returns a response (not an error)

### Step 7.3: Test Email/Password Login

1. Go to `https://winnowcc.ai/login`
2. Log in with existing account
3. **Check:** Dashboard loads
4. Open browser DevTools (F12) → Application tab → Cookies
5. **Check:** `rm_session` cookie has domain `.winnowcc.ai`

### Step 7.4: Test Social Login

1. Log out
2. Go to `https://winnowcc.ai/login`
3. Click "Sign in with Google" (or GitHub)
4. **Check:** Auth0 page appears → sign in → redirected to dashboard (or onboarding)

### Step 7.5: Test Redirects

| Visit this URL | Should redirect to |
|----------------|-------------------|
| `http://winnowcc.ai` | `https://winnowcc.ai` |
| `https://www.winnowcc.ai` | `https://winnowcc.ai` |
| `https://winnowcc.io` | `https://winnowcc.ai` |
| `https://www.winnowcc.io` | `https://winnowcc.ai` |

### Step 7.6: Test Old URLs Still Work

1. Go to `https://winnow-web-cdn2d6pc5q-uc.a.run.app` — should still load
2. Go to `https://winnow-api-cdn2d6pc5q-uc.a.run.app/health` — should still respond

Old URLs work indefinitely as a safety net.

### Step 7.7: Update GCP Uptime Checks

1. Go to `https://console.cloud.google.com/monitoring/uptime`
2. Find API uptime check → Edit → change Host from `winnow-api-cdn2d6pc5q-uc.a.run.app` to `api.winnowcc.ai` → Save
3. Find Web uptime check → Edit → change Host from `winnow-web-cdn2d6pc5q-uc.a.run.app` to `winnowcc.ai` → Save
4. If readiness check exists (`/ready`), update that host too

### Step 7.8: Update Sentry

```powershell
gcloud run services update winnow-api `
  --region=us-central1 `
  --update-env-vars="SENTRY_SERVER_NAME=api.winnowcc.ai"
```

### Step 7.9: Final Checklist

- [ ] `https://winnowcc.ai` loads with SSL padlock
- [ ] `https://api.winnowcc.ai/health` returns `{"status":"ok"}`
- [ ] `https://www.winnowcc.ai` redirects to `https://winnowcc.ai`
- [ ] `https://winnowcc.io` redirects to `https://winnowcc.ai`
- [ ] Email/password login works
- [ ] Social login (Google/GitHub) works
- [ ] `rm_session` cookie has domain `.winnowcc.ai`
- [ ] Logout works (cookie cleared)
- [ ] Stripe test webhook returns 200
- [ ] GCP uptime checks monitor custom domain
- [ ] Resume upload and parsing works
- [ ] Old `*.run.app` URLs still work as fallback
- [ ] Mobile app connects to `https://api.winnowcc.ai` (next EAS build)

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Auth cookie domain | `services/api/app/services/auth.py` | MODIFY — add `COOKIE_DOMAIN` env var, update `set_auth_cookie` and `clear_auth_cookie` |
| Deploy workflow | `.github/workflows/deploy.yml` | MODIFY — add `COOKIE_DOMAIN=.winnowcc.ai` to API env vars |
| Chrome extension default URL | `apps/chrome-extension/popup/popup.js` | MODIFY — change `DEFAULT_API_URL` to `https://api.winnowcc.ai` |
| CORS origins | `services/api/app/main.py` | NO CHANGE — already includes `winnowcc.ai` |
| Web env | `apps/web/.env.production` | NO CHANGE — already has `api.winnowcc.ai` |
| Mobile env | `apps/mobile/eas.json` | NO CHANGE — already has `api.winnowcc.ai` |
| Email | `services/api/app/services/email.py` | NO CHANGE — already uses `hello@winnowcc.ai` |
| Redirect infra | `infra/redirect/` | DEPLOY (files exist, not deployed) |

---

## External Dashboards to Update

| Dashboard | What to Change |
|-----------|---------------|
| Domain registrar | Point nameservers to Google Cloud DNS |
| Google Cloud Console | Create DNS zones, domain mappings |
| Auth0 (`manage.auth0.com`) | Add `winnowcc.ai` callback URLs, logout URLs, web origins |
| Stripe (`dashboard.stripe.com`) | Update webhook endpoint URL to `api.winnowcc.ai` |
| GCP Monitoring | Update uptime check hosts to custom domains |

---

## Things to Do LATER (Not Part of This Cutover)

1. **DMARC upgrade** — Change `_dmarc.winnowcc.ai` from `p=none` to `p=quarantine` around late March 2026 (per MEMORY.md)
2. **PostHog API key** — Add real `POSTHOG_KEY` to GitHub repo Secrets if not already done
3. **Mobile app rebuild** — Next `eas build` will automatically use `api.winnowcc.ai` (already in eas.json)
4. **Bulk upload script** — `scripts/bulk_upload_resumes.py` line 667 defaults to Cloud Run URL. Update if used.
5. **EAS-COMMANDS.md** — Update documentation references from `*.run.app` to `api.winnowcc.ai`
6. **Old Cloud Run URLs** — Keep working indefinitely. No need to disable.

---

## Non-Goals (Do NOT implement in this prompt)

- CDN / Cloud Armor / WAF (future hardening)
- Staging environment (`staging.winnowcc.ai`)
- DNSSEC (optional hardening)
- Multi-region deployment
- Disabling old `*.run.app` URLs

---

## Rollback (If Everything Goes Wrong)

The old `*.run.app` URLs never stop working. To fully revert:

1. **Code:** `git revert HEAD && git push origin main`
2. **Stripe:** Change webhook URL back to old `*.run.app` URL
3. **Auth0:** Old URLs remain alongside new ones — no action needed
4. **Domain mappings:** `gcloud beta run domain-mappings delete --domain=winnowcc.ai --region=us-central1` (repeat for api. and www.)
5. **DNS:** Revert nameservers at your registrar to their original values

Return code changes only.
