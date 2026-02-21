# PROMPT26_Custom_Domain.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPT16 (Test & Deploy) before making changes.

## Purpose

Configure custom domains for the Winnow platform, mapping `WinnowCC.ai` as the primary domain and `WinnowCC.io` as a defensive redirect. This includes DNS configuration, SSL certificate provisioning (via GCP managed certs), updating CORS origins, auth cookie domain, Stripe webhook URLs, mobile app API URL, Sentry environment tags, GCP uptime checks, and adding product analytics (Posthog). After this prompt, users will access the app at `https://winnowcc.ai` and the API at `https://api.winnowcc.ai`.

---

## Triggers — When to Use This Prompt

- You've completed QA (PROMPT25) and are ready to go live on a custom domain.
- You need to move from Cloud Run default URLs (`*.run.app`) to a branded domain.
- You're setting up DNS, SSL, CORS, cookie domain, or analytics for production.

---

## What Already Exists (DO NOT recreate)

1. **Cloud Run services:** `winnow-api`, `winnow-worker`, `winnow-web` deployed (PROMPT16).
2. **CORS:** `services/api/app/main.py` — `ALLOWED_ORIGINS` list with `CORS_ORIGIN` env var support.
3. **Auth cookies:** `services/api/app/services/auth.py` — `set_auth_cookie` with `IS_PRODUCTION`, `Secure`, `SameSite` flags.
4. **Security headers:** `services/api/app/middleware/security_headers.py` — HSTS, X-Frame-Options, etc. (PROMPT21).
5. **Stripe billing:** `services/api/app/routers/billing.py` — webhook endpoint at `POST /api/billing/webhook` (PROMPT20).
6. **Sentry:** API + web + worker with DSNs in Secret Manager (PROMPT22).
7. **GCP monitoring:** Uptime checks on Cloud Run default URLs (PROMPT22).
8. **Mobile app:** `apps/mobile/.env` — `EXPO_PUBLIC_API_BASE_URL` (PROMPT23).
9. **Deploy workflow:** `.github/workflows/deploy.yml` — builds and deploys to Cloud Run on merge to main (PROMPT16).
10. **Next.js config:** `apps/web/next.config.js` — `output: 'standalone'`, security headers.

---

## Domain Architecture

| Subdomain | Purpose | Maps to |
|-----------|---------|---------|
| `winnowcc.ai` | Web app (frontend) | Cloud Run: `winnow-web` |
| `www.winnowcc.ai` | Redirect → `winnowcc.ai` | 301 redirect |
| `api.winnowcc.ai` | API server (backend) | Cloud Run: `winnow-api` |
| `winnowcc.io` | Defensive asset — redirect all | 301 redirect → `winnowcc.ai` |
| `www.winnowcc.io` | Defensive asset — redirect all | 301 redirect → `winnowcc.ai` |

---

## What to Build

This prompt covers 9 domains. Execute in order — each builds on the previous.

---

# PART 1 — REGISTER DOMAINS + DNS SETUP

### 1.1 Register the domains

If not already registered, purchase `winnowcc.ai` and `winnowcc.io` from a domain registrar (Google Domains, Namecheap, Cloudflare Registrar, etc.).

### 1.2 Point nameservers to Google Cloud DNS (recommended)

Using Google Cloud DNS gives you tight integration with Cloud Run domain mapping. If you prefer your registrar's DNS, skip to 1.3.

**In PowerShell (gcloud CLI):**

```powershell
# Create a DNS zone for winnowcc.ai
gcloud dns managed-zones create winnowcc-ai `
  --dns-name="winnowcc.ai." `
  --description="Winnow primary domain" `
  --visibility=public

# Create a DNS zone for winnowcc.io
gcloud dns managed-zones create winnowcc-io `
  --dns-name="winnowcc.io." `
  --description="Winnow defensive domain" `
  --visibility=public

# Get the nameservers for each zone
gcloud dns managed-zones describe winnowcc-ai --format="value(nameServers)"
gcloud dns managed-zones describe winnowcc-io --format="value(nameServers)"
```

Copy the nameservers output (e.g., `ns-cloud-a1.googledomains.com`, ...) and go to your registrar's control panel. Update the nameservers for both domains to the Google Cloud DNS nameservers.

**Wait 15–60 minutes** for nameserver propagation before proceeding.

### 1.3 Alternative: Use your registrar's DNS

If you don't want to use Google Cloud DNS, you'll add the DNS records from Steps 2.2–2.5 directly in your registrar's DNS management panel instead of using `gcloud dns` commands. The record types and values are the same.

---

# PART 2 — MAP CUSTOM DOMAINS TO CLOUD RUN

### 2.1 Map `winnowcc.ai` → `winnow-web` (frontend)

```powershell
gcloud beta run domain-mappings create `
  --service=winnow-web `
  --domain=winnowcc.ai `
  --region=us-central1
```

This will output DNS records you need to add. Typically:

| Record Type | Host | Value |
|-------------|------|-------|
| A | `@` | (IP address provided by GCP) |
| AAAA | `@` | (IPv6 address provided by GCP) |

### 2.2 Add the DNS records for `winnowcc.ai`

```powershell
# Get the required records from the domain mapping output, then add them:

# A record (replace IP_ADDRESS with the actual value from Step 2.1)
gcloud dns record-sets create winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=A `
  --ttl=300 `
  --rrdatas="IP_ADDRESS"

# AAAA record (replace IPV6_ADDRESS with the actual value from Step 2.1)
gcloud dns record-sets create winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=AAAA `
  --ttl=300 `
  --rrdatas="IPV6_ADDRESS"
```

### 2.3 Map `www.winnowcc.ai` → redirect to `winnowcc.ai`

```powershell
# CNAME www → the Cloud Run domain
gcloud dns record-sets create www.winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."
```

Then create the www mapping:
```powershell
gcloud beta run domain-mappings create `
  --service=winnow-web `
  --domain=www.winnowcc.ai `
  --region=us-central1
```

### 2.4 Map `api.winnowcc.ai` → `winnow-api` (backend)

```powershell
gcloud beta run domain-mappings create `
  --service=winnow-api `
  --domain=api.winnowcc.ai `
  --region=us-central1
```

Add the DNS records (same pattern as 2.2):

```powershell
# CNAME for api subdomain
gcloud dns record-sets create api.winnowcc.ai. `
  --zone=winnowcc-ai `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."
```

### 2.5 Set up `winnowcc.io` as a redirect

Option A — Use Cloud Run with a simple redirect service (recommended):

**File to create:** `infra/redirect/Dockerfile`

```dockerfile
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
```

**File to create:** `infra/redirect/nginx.conf`

```nginx
server {
    listen 8080;
    server_name winnowcc.io www.winnowcc.io;

    location / {
        return 301 https://winnowcc.ai$request_uri;
    }
}
```

Build and deploy:

```powershell
cd C:\Users\ronle\Documents\resumematch\infra\redirect

# Build the redirect image
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/redirect:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/redirect:latest

# Deploy to Cloud Run
gcloud run deploy winnow-redirect `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/redirect:latest `
  --region=us-central1 `
  --platform=managed `
  --allow-unauthenticated `
  --port=8080 `
  --memory=128Mi `
  --cpu=1 `
  --min-instances=0 `
  --max-instances=2

# Map the .io domains
gcloud beta run domain-mappings create `
  --service=winnow-redirect `
  --domain=winnowcc.io `
  --region=us-central1

gcloud beta run domain-mappings create `
  --service=winnow-redirect `
  --domain=www.winnowcc.io `
  --region=us-central1
```

Add DNS records for `winnowcc.io`:

```powershell
# A record for winnowcc.io root
gcloud dns record-sets create winnowcc.io. `
  --zone=winnowcc-io `
  --type=A `
  --ttl=300 `
  --rrdatas="IP_ADDRESS"

# AAAA record for winnowcc.io root
gcloud dns record-sets create winnowcc.io. `
  --zone=winnowcc-io `
  --type=AAAA `
  --ttl=300 `
  --rrdatas="IPV6_ADDRESS"

# CNAME for www.winnowcc.io
gcloud dns record-sets create www.winnowcc.io. `
  --zone=winnowcc-io `
  --type=CNAME `
  --ttl=300 `
  --rrdatas="ghs.googlehosted.com."
```

Option B — If your registrar supports URL forwarding (simpler, no Cloud Run needed):

Go to your registrar's DNS panel for `winnowcc.io` and set up a **301 redirect** from `winnowcc.io` and `www.winnowcc.io` to `https://winnowcc.ai`. Most registrars (Namecheap, Cloudflare, GoDaddy) support this natively.

### 2.6 Verify SSL certificates

GCP automatically provisions managed SSL certificates for domain-mapped Cloud Run services. Check status:

```powershell
gcloud beta run domain-mappings describe `
  --domain=winnowcc.ai `
  --region=us-central1

gcloud beta run domain-mappings describe `
  --domain=api.winnowcc.ai `
  --region=us-central1
```

Look for `certificateStatus: ACTIVE`. This can take **15–60 minutes** after DNS propagation. Until the certificate is active, users will see SSL warnings.

---

# PART 3 — UPDATE CORS ORIGINS

The API must accept requests from the new custom domain.

**File to modify:** `services/api/app/main.py`

Find the `ALLOWED_ORIGINS` list. Update it:

```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",          # Local dev
    "http://127.0.0.1:3000",         # Local dev alt
    "http://localhost:8081",          # Expo dev server
    "http://localhost:19006",         # Expo web
    "https://winnowcc.ai",           # Production — primary
    "https://www.winnowcc.ai",       # Production — www
]

# Also keep the dynamic CORS_ORIGIN env var for flexibility
PROD_WEB_URL = os.environ.get("CORS_ORIGIN")
if PROD_WEB_URL and PROD_WEB_URL not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(PROD_WEB_URL)
```

Update the `CORS_ORIGIN` env var on Cloud Run:

```powershell
gcloud run services update winnow-api `
  --region=us-central1 `
  --update-env-vars="CORS_ORIGIN=https://winnowcc.ai"
```

---

# PART 4 — UPDATE AUTH COOKIE DOMAIN

With a custom domain, the web app (`winnowcc.ai`) and API (`api.winnowcc.ai`) share the same root domain, so cookies can be scoped to `.winnowcc.ai` with `SameSite=Lax` (more secure than `SameSite=None`).

**File to modify:** `services/api/app/services/auth.py`

Find the `set_auth_cookie` function. Update it to accept a configurable domain:

```python
import os

IS_PRODUCTION = os.environ.get("ENV", "dev") != "dev"
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)  # e.g., ".winnowcc.ai"


def set_auth_cookie(response: Response, user_id: int, email: str) -> None:
    """Set the authentication cookie on the response."""
    token = make_token(user_id=user_id, email=email)
    response.set_cookie(
        key=os.environ.get("AUTH_COOKIE_NAME", "rm_session"),
        value=token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax" if COOKIE_DOMAIN else ("none" if IS_PRODUCTION else "lax"),
        domain=COOKIE_DOMAIN,       # ".winnowcc.ai" in production
        path="/",
        max_age=60 * 60 * 24 * int(os.environ.get("AUTH_TOKEN_EXPIRES_DAYS", "7")),
    )
```

Set the env var on Cloud Run:

```powershell
gcloud run services update winnow-api `
  --region=us-central1 `
  --update-env-vars="COOKIE_DOMAIN=.winnowcc.ai"
```

**Why `.winnowcc.ai` (with leading dot)?** This lets the cookie be sent to both `winnowcc.ai` and `api.winnowcc.ai`. Without the domain, the cookie would only be sent to the exact host that set it.

---

# PART 5 — UPDATE STRIPE WEBHOOK URL

Stripe needs to send webhook events to your new domain instead of the Cloud Run default URL.

### 5.1 Update in Stripe Dashboard

1. Go to https://dashboard.stripe.com/webhooks
2. Find your existing webhook endpoint (the old `*.run.app` URL)
3. Click it → **Update endpoint**
4. Change the URL to:
   ```
   https://api.winnowcc.ai/api/billing/webhook
   ```
5. Click **Update endpoint**

### 5.2 Verify the webhook signing secret hasn't changed

The webhook signing secret (`STRIPE_WEBHOOK_SECRET`) stays the same unless you create a brand new endpoint. If you created a new endpoint instead of updating, copy the new signing secret.

Update Secret Manager if the secret changed:

```powershell
echo -n "whsec_YOUR_NEW_SECRET" | gcloud secrets versions add STRIPE_WEBHOOK_SECRET --data-file=-
```

### 5.3 Test the webhook

In your Stripe Dashboard, click **Send test webhook** on the endpoint. Choose `checkout.session.completed` and send. Check your API logs:

```powershell
gcloud logging read "resource.labels.service_name=winnow-api AND textPayload:webhook" `
  --limit=5 --format=json
```

---

# PART 6 — UPDATE NEXT.JS ENVIRONMENT

The web app needs to know the new API URL.

**File to modify:** `apps/web/.env.production` (CREATE if it doesn't exist)

```env
NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai
NEXT_PUBLIC_APP_URL=https://winnowcc.ai
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
```

**File to modify:** `apps/web/.env.local` (local dev — keep as-is)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

Update the Docker build in the deploy workflow:

**File to modify:** `.github/workflows/deploy.yml`

Find the web build step. Update the build arg:

```yaml
- name: Build and push Web image
  run: |
    cd apps/web
    docker build \
      --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai \
      --build-arg NEXT_PUBLIC_APP_URL=https://winnowcc.ai \
      --build-arg NEXT_PUBLIC_SENTRY_DSN=${{ secrets.NEXT_PUBLIC_SENTRY_DSN }} \
      --build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT=production \
      -t ${{ env.WEB_IMAGE }}:${{ github.sha }} \
      -t ${{ env.WEB_IMAGE }}:latest .
    docker push ${{ env.WEB_IMAGE }}:${{ github.sha }}
    docker push ${{ env.WEB_IMAGE }}:latest
```

---

# PART 7 — UPDATE MOBILE APP

The mobile app's production API URL needs to point to the custom domain.

**File to modify:** `apps/mobile/.env`

For **local development**, keep your local IP:
```env
EXPO_PUBLIC_API_BASE_URL=http://10.135.1.69:8000
```

**File to create:** `apps/mobile/.env.production`

```env
EXPO_PUBLIC_API_BASE_URL=https://api.winnowcc.ai
```

When building for production (app store submission), use the production env:

**File to modify:** `apps/mobile/eas.json`

In the `"production"` build profile, add the env:

```json
{
  "build": {
    "production": {
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://api.winnowcc.ai"
      }
    }
  }
}
```

This ensures that `eas build --profile production` bakes in the production API URL.

---

# PART 8 — ADD PRODUCT ANALYTICS (POSTHOG)

Track user behavior to understand feature usage and identify friction points.

### 8.1 Create a Posthog account

1. Go to https://posthog.com — sign up (free tier: 1M events/month)
2. Create a project called "Winnow"
3. Copy your **API Key** (starts with `phc_...`)
4. Note the **API Host** (usually `https://us.i.posthog.com` or `https://eu.i.posthog.com`)

### 8.2 Install Posthog in the web app

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
npm install posthog-js
```

### 8.3 Create the analytics provider

**File to create:** `apps/web/app/providers/PosthogProvider.tsx`

```tsx
'use client';

import posthog from 'posthog-js';
import { PostHogProvider as PHProvider } from 'posthog-js/react';
import { useEffect } from 'react';

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY || '';
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com';

export default function PosthogProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (POSTHOG_KEY) {
      posthog.init(POSTHOG_KEY, {
        api_host: POSTHOG_HOST,
        person_profiles: 'identified_only',
        capture_pageview: true,
        capture_pageleave: true,
        loaded: (posthog) => {
          if (process.env.NODE_ENV === 'development') {
            posthog.debug();
          }
        },
      });
    }
  }, []);

  if (!POSTHOG_KEY) return <>{children}</>;

  return <PHProvider client={posthog}>{children}</PHProvider>;
}
```

### 8.4 Add the provider to the root layout

**File to modify:** `apps/web/app/layout.tsx`

Add the import and wrap your children:

```tsx
import PosthogProvider from './providers/PosthogProvider';

// Inside the RootLayout component, wrap children:
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PosthogProvider>
          {/* ... existing providers and content ... */}
          {children}
        </PosthogProvider>
      </body>
    </html>
  );
}
```

### 8.5 Add environment variables

**File to modify:** `apps/web/.env.production`

Add:
```env
NEXT_PUBLIC_POSTHOG_KEY=phc_YOUR_API_KEY_HERE
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```

**File to modify:** `apps/web/.env.local` (optional — leave empty to disable in dev)

```env
NEXT_PUBLIC_POSTHOG_KEY=
NEXT_PUBLIC_POSTHOG_HOST=
```

### 8.6 Identify users after login

**File to modify:** `apps/web/app/dashboard/page.tsx` (or wherever auth state is first available)

After a successful login/auth check, identify the user:

```tsx
import posthog from 'posthog-js';

// Inside your dashboard component, after auth is confirmed:
useEffect(() => {
  if (user?.email) {
    posthog.identify(String(user.user_id), {
      email: user.email,
      plan: user.plan || 'free',
    });
  }
}, [user]);
```

### 8.7 Track key events (optional but recommended)

Add custom event tracking at key moments. Add these calls in the relevant components:

```tsx
// When a user uploads a resume
posthog.capture('resume_uploaded', { file_type: 'pdf' });

// When a user generates a tailored resume
posthog.capture('tailored_resume_generated', { job_id: jobId, match_score: matchScore });

// When a user changes application status
posthog.capture('application_status_changed', { new_status: status });

// When a user upgrades to Pro
posthog.capture('subscription_upgraded', { plan: 'pro' });

// When Sieve is opened
posthog.capture('sieve_opened');
```

### 8.8 Update deploy workflow

**File to modify:** `.github/workflows/deploy.yml`

Add the Posthog build arg to the web build step:

```yaml
--build-arg NEXT_PUBLIC_POSTHOG_KEY=${{ secrets.POSTHOG_KEY }} \
--build-arg NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com \
```

Add to GitHub Secrets:

| Secret Name | Value |
|-------------|-------|
| `POSTHOG_KEY` | Your Posthog API key (`phc_...`) |

---

# PART 9 — UPDATE MONITORING + UPTIME CHECKS

### 9.1 Update GCP uptime checks

Go to **GCP Console** → **Monitoring** → **Uptime checks**. Update the existing checks:

**Check 1 — API Health**
- Change host from `winnow-api-xxxxx-uc.a.run.app` to `api.winnowcc.ai`
- Path: `/health`
- Everything else stays the same

**Check 2 — API Readiness**
- Change host to `api.winnowcc.ai`
- Path: `/ready`

**Check 3 — Web App**
- Change host from `winnow-web-xxxxx-uc.a.run.app` to `winnowcc.ai`
- Path: `/`

### 9.2 Update Sentry environment

Update the Sentry environment tag to include the domain:

```powershell
gcloud run services update winnow-api `
  --region=us-central1 `
  --update-env-vars="SENTRY_ENVIRONMENT=production,SENTRY_SERVER_NAME=api.winnowcc.ai"

gcloud run services update winnow-worker `
  --region=us-central1 `
  --update-env-vars="SENTRY_ENVIRONMENT=production"
```

### 9.3 Update Cloud Scheduler

If the Cloud Scheduler job uses the old Cloud Run URL, update it:

```powershell
gcloud scheduler jobs update http winnow-ingest-jobs `
  --location=us-central1 `
  --uri="https://api.winnowcc.ai/api/admin/ingest?admin_token=YOUR_PRODUCTION_ADMIN_TOKEN"
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Redirect Dockerfile | `infra/redirect/Dockerfile` | CREATE |
| Redirect nginx config | `infra/redirect/nginx.conf` | CREATE |
| CORS origins | `services/api/app/main.py` | MODIFY — add `winnowcc.ai` origins |
| Auth cookie domain | `services/api/app/services/auth.py` | MODIFY — add `COOKIE_DOMAIN` env var |
| Web production env | `apps/web/.env.production` | CREATE |
| Mobile production env | `apps/mobile/.env.production` | CREATE |
| Mobile EAS config | `apps/mobile/eas.json` | MODIFY — add production env |
| Posthog provider | `apps/web/app/providers/PosthogProvider.tsx` | CREATE |
| Root layout | `apps/web/app/layout.tsx` | MODIFY — add PosthogProvider |
| Deploy workflow | `.github/workflows/deploy.yml` | MODIFY — update build args |
| Dashboard (Posthog identify) | `apps/web/app/dashboard/page.tsx` | MODIFY — add user identify |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Domain Registration + DNS (Steps 1–5)

1. **Step 1:** Purchase `winnowcc.ai` and `winnowcc.io` from your registrar if not already owned.
2. **Step 2:** Create Google Cloud DNS zones and get nameservers (Part 1.2). Update registrar nameservers. **Wait 15–60 minutes.**
3. **Step 3:** Map `winnowcc.ai` and `www.winnowcc.ai` to `winnow-web` (Part 2.1–2.3).
4. **Step 4:** Map `api.winnowcc.ai` to `winnow-api` (Part 2.4).
5. **Step 5:** Set up `winnowcc.io` redirect — either via Cloud Run nginx container (Part 2.5 Option A) or registrar URL forwarding (Part 2.5 Option B).

### Phase 2: SSL Verification (Step 6)

6. **Step 6:** Wait for SSL certificates to become `ACTIVE` (Part 2.6). Check status with `gcloud beta run domain-mappings describe`. This can take up to 60 minutes. Do not proceed until SSL is active.

### Phase 3: Backend Configuration (Steps 7–9)

7. **Step 7:** Open `C:\Users\ronle\Documents\resumematch\services\api\app\main.py` in Cursor. Update `ALLOWED_ORIGINS` to include `winnowcc.ai` domains (Part 3).
8. **Step 8:** Open `C:\Users\ronle\Documents\resumematch\services\api\app\services\auth.py` in Cursor. Add `COOKIE_DOMAIN` support to `set_auth_cookie` (Part 4).
9. **Step 9:** Deploy updated API to Cloud Run with new env vars:
   ```powershell
   # Build and push
   cd C:\Users\ronle\Documents\resumematch\services\api
   docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest .
   docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest

   # Deploy with updated env vars
   gcloud run deploy winnow-api `
     --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest `
     --region=us-central1 `
     --update-env-vars="CORS_ORIGIN=https://winnowcc.ai,COOKIE_DOMAIN=.winnowcc.ai,ENV=production"
   ```

### Phase 4: Stripe Webhook (Step 10)

10. **Step 10:** Update Stripe webhook URL to `https://api.winnowcc.ai/api/billing/webhook` (Part 5.1). Send a test webhook (Part 5.3).

### Phase 5: Frontend Configuration (Steps 11–12)

11. **Step 11:** Create `C:\Users\ronle\Documents\resumematch\apps\web\.env.production` with production API URL and Posthog key (Part 6).
12. **Step 12:** Rebuild and deploy the web app:
    ```powershell
    cd C:\Users\ronle\Documents\resumematch\apps\web
    docker build `
      --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai `
      --build-arg NEXT_PUBLIC_APP_URL=https://winnowcc.ai `
      -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest .
    docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest

    gcloud run deploy winnow-web `
      --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest `
      --region=us-central1
    ```

### Phase 6: Mobile Configuration (Step 13)

13. **Step 13:** Create `C:\Users\ronle\Documents\resumematch\apps\mobile\.env.production` and update `eas.json` (Part 7).

### Phase 7: Product Analytics (Steps 14–17)

14. **Step 14:** Create a Posthog account and project (Part 8.1).
15. **Step 15:** Install posthog-js:
    ```powershell
    cd C:\Users\ronle\Documents\resumematch\apps\web
    npm install posthog-js
    ```
16. **Step 16:** Create `C:\Users\ronle\Documents\resumematch\apps\web\app\providers\PosthogProvider.tsx` (Part 8.3).
17. **Step 17:** Modify `C:\Users\ronle\Documents\resumematch\apps\web\app\layout.tsx` — add PosthogProvider wrapper (Part 8.4). Add `posthog.identify()` to dashboard page (Part 8.6).

### Phase 8: Update Monitoring (Steps 18–20)

18. **Step 18:** Update GCP uptime checks to use custom domains (Part 9.1).
19. **Step 19:** Update Sentry env vars on Cloud Run (Part 9.2).
20. **Step 20:** Update Cloud Scheduler URI to use custom domain (Part 9.3).

### Phase 9: Deploy + Verify (Steps 21–25)

21. **Step 21:** Update `.github/workflows/deploy.yml` with new build args and secrets (Part 6 + 8.8).
22. **Step 22:** Commit all changes, push to `main`, let CI/CD deploy.
23. **Step 23:** Verify web: Open `https://winnowcc.ai` in your browser — landing page loads with SSL.
24. **Step 24:** Verify API: Open `https://api.winnowcc.ai/health` — returns `{"status": "ok"}`.
25. **Step 25:** Verify redirects:
    - `http://winnowcc.ai` → redirects to `https://winnowcc.ai` (HSTS)
    - `https://www.winnowcc.ai` → redirects to `https://winnowcc.ai`
    - `https://winnowcc.io` → redirects to `https://winnowcc.ai`

### Phase 10: Lint (Step 26)

26. **Step 26:** Lint everything:
    ```powershell
    cd C:\Users\ronle\Documents\resumematch\services\api
    python -m ruff check .
    python -m ruff format .

    cd C:\Users\ronle\Documents\resumematch\apps\web
    npm run lint
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- CDN / Cloud Armor / WAF (future — not needed for soft launch)
- Staging environment on a separate subdomain (future — `staging.winnowcc.ai`)
- Email sending from `@winnowcc.ai` (requires MX records + email provider setup)
- SEO optimization, sitemap, robots.txt (separate task)
- DNSSEC (optional hardening — can be added later)
- Multi-region deployment (single region is fine for launch)
- Privacy policy page content (legal task — the page itself can be a placeholder)

---

## Summary Checklist

### DNS + SSL
- [ ] `winnowcc.ai` DNS zone created with A/AAAA records
- [ ] `api.winnowcc.ai` CNAME record created
- [ ] `www.winnowcc.ai` CNAME record created
- [ ] `winnowcc.io` DNS zone created with redirect
- [ ] SSL certificates `ACTIVE` for all domain mappings

### Cloud Run Mappings
- [ ] `winnowcc.ai` → `winnow-web`
- [ ] `www.winnowcc.ai` → `winnow-web`
- [ ] `api.winnowcc.ai` → `winnow-api`
- [ ] `winnowcc.io` → `winnow-redirect` (or registrar redirect)

### Backend
- [ ] CORS includes `https://winnowcc.ai` and `https://www.winnowcc.ai`
- [ ] `CORS_ORIGIN` env var set to `https://winnowcc.ai`
- [ ] `COOKIE_DOMAIN` env var set to `.winnowcc.ai`
- [ ] `set_auth_cookie` uses domain parameter
- [ ] Cookie `SameSite=Lax` with domain scoping

### Stripe
- [ ] Webhook endpoint updated to `https://api.winnowcc.ai/api/billing/webhook`
- [ ] Test webhook sent and received successfully

### Frontend
- [ ] `.env.production` created with production API URL
- [ ] Docker build uses `NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai`
- [ ] Posthog installed and provider added to layout
- [ ] User identification on login

### Mobile
- [ ] `.env.production` created with `https://api.winnowcc.ai`
- [ ] `eas.json` production profile includes production API URL

### Monitoring
- [ ] Uptime checks updated to custom domains
- [ ] Sentry environment tags updated
- [ ] Cloud Scheduler URI updated

### Verification
- [ ] `https://winnowcc.ai` loads (SSL, no warnings)
- [ ] `https://api.winnowcc.ai/health` returns ok
- [ ] `https://www.winnowcc.ai` redirects to `https://winnowcc.ai`
- [ ] `https://winnowcc.io` redirects to `https://winnowcc.ai`
- [ ] Login works on custom domain
- [ ] Cookie set with domain `.winnowcc.ai`
- [ ] Stripe webhook received on new URL
- [ ] Posthog events appearing in dashboard
- [ ] Linted and formatted

Return code changes only.
