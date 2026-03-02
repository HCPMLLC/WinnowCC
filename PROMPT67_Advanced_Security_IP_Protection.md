# PROMPT 67: Advanced Security & IP Protection

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 1–66 before making changes.

---

## Purpose

Harden Winnow for production scale with four security capabilities that PROMPT21 explicitly deferred: **session management with token revocation**, **API abuse detection with account lockout**, **WAF via Google Cloud Armor**, and **IP-based access controls**. This prompt also fixes critical gaps discovered during the security audit (unprotected auth endpoints, broken SMS OTP service, missing CSP header).

**Business case:** A hiring platform stores resumes, salary expectations, and PII. A security incident means regulatory exposure (GDPR, CCPA), reputational damage, and loss of trust from all three segments. These features are table-stakes for enterprise employer and recruiter customers who will ask for SOC 2 evidence.

---

## What Already Exists (DO NOT Recreate)

1. **MFA (email + SMS OTP):** `services/api/app/services/auth.py` — 6-digit OTP, HMAC-SHA256, 10-min TTL, 5-attempt lockout per code. Required for employer/recruiter roles.
2. **Rate limiting middleware:** `services/api/app/middleware/rate_limit.py` — slowapi, per-user or per-IP keying. Currently only applied to account export, account delete, and billing checkout.
3. **Security headers:** `services/api/app/middleware/security_headers.py` — X-Frame-Options, HSTS, Referrer-Policy, Permissions-Policy. Missing CSP.
4. **JWT auth:** HS256, 7-day expiry, HttpOnly cookie (`rm_session`) for web, Bearer header for mobile.
5. **Cloud Run deployment:** API (public), Worker (internal), Scheduler (internal), Web (public). VPC connector for DB/Redis. No Cloud Armor.
6. **CORS:** Explicit origin allowlist + Chrome extension regex.

---

## Critical Fixes (Do These First)

Before building new features, fix these audit findings that represent immediate risk.

### Fix A: Rate-limit all auth endpoints

**File to modify:** `services/api/app/routers/auth.py`

Add `@limiter.limit()` decorators:

| Endpoint | Limit | Rationale |
|---|---|---|
| `POST /api/auth/login` | `10/minute` | Brute-force prevention |
| `POST /api/auth/signup` | `5/minute` | Spam account creation |
| `POST /api/auth/verify-otp` | `10/minute` | OTP brute-force (supplements 5-attempt DB counter) |
| `POST /api/auth/resend-otp` | `3/minute` | Prevents SMS/email credit burn |
| `POST /api/auth/forgot-password` | `5/minute` | Email bombing prevention |
| `POST /api/auth/reset-password` | `5/minute` | Token brute-force |

Import and add `request: Request` parameter to each endpoint handler that doesn't already have it.

### Fix B: Remove or secure the standalone SMS OTP service

**File:** `services/api/app/services/sms_service.py` and `services/api/app/routers/sms_otp.py`

This service is broken (in-memory store doesn't work across Cloud Run instances) and dangerous (no auth, no rate limit, uses non-cryptographic random). Two options:

- **Option A (recommended):** Delete both files and remove the router from `main.py`. All MFA OTP functionality already lives in `auth.py` with proper HMAC hashing and DB storage.
- **Option B:** If the standalone SMS endpoint is needed for phone verification, rewrite it to use the DB (like auth OTP does), add auth requirement, add rate limiting (`3/minute`), and use `secrets.randbelow()`.

### Fix C: Add Content-Security-Policy header

**File to modify:** `services/api/app/middleware/security_headers.py`

Add to the response headers:

```python
"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://api.stripe.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
```

Note: This header is primarily relevant for the frontend. Since the API returns JSON (not HTML), a restrictive default is fine. The frontend (`apps/web`) should set its own CSP via `next.config.js` `headers()` — add that too.

### Fix D: Enforce minimum password length server-side

**File to modify:** `services/api/app/routers/auth.py` (or `services/auth.py` — wherever `_validate_password` lives)

Add to password validation:
```python
if len(password) < 8:
    raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
```

### Fix E: Restrict CORS Chrome extension regex

**File to modify:** `services/api/app/main.py`

Replace the broad `r"^chrome-extension://.*"` with the specific extension ID once published:
```python
allow_origin_regex=r"^chrome-extension://YOUR_EXTENSION_ID_HERE$"
```

Until published, keep the broad regex but add a `# TODO` comment.

---

## Implementation Sequence

Build these features **in this exact order** — each builds on the previous:

| Phase | Feature | Depends On | Estimated Effort |
|---|---|---|---|
| 0 | Critical Fixes A–E | Nothing | Small |
| 1 | Session Management & Token Revocation | Fix A (rate limits) | Medium |
| 2 | API Abuse Detection & Account Lockout | Phase 1 (session table) | Medium |
| 3 | IP Protection & Access Controls | Phase 2 (abuse tracking) | Medium |
| 4 | WAF via Google Cloud Armor | Nothing (infra-only) | Medium |

---

## Phase 1: Session Management & Token Revocation

### What It Does

Replaces stateless JWT-only auth with **tracked sessions** that can be individually revoked. Users can see active sessions and log out specific devices. Logout actually invalidates the token server-side.

### Database Migration

**File to create:** `services/api/alembic/versions/xxxx_add_sessions_table.py`

```sql
CREATE TABLE user_sessions (
    id VARCHAR(64) PRIMARY KEY,              -- Unique session/token ID (jti claim)
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL,        -- SHA-256 of the JWT (for lookup without storing raw token)
    device_info VARCHAR(500),                -- User-Agent string (truncated)
    ip_address VARCHAR(45),                  -- IPv4 or IPv6
    ip_country VARCHAR(2),                   -- ISO country code (from GeoIP lookup, nullable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,                  -- NULL = active, set = revoked
    revoke_reason VARCHAR(50)                -- 'user_logout', 'admin_revoke', 'password_change', 'suspicious'
);

CREATE INDEX idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at) WHERE revoked_at IS NULL;

-- Add audit fields to users table
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45);
ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
```

### Backend Changes

**File to modify:** `services/api/app/services/auth.py`

1. **Token creation** — Add `jti` (JWT ID) claim to every token. After signing, insert a row into `user_sessions` with the jti, token hash, device info (from User-Agent), and IP.

2. **Token validation** — In `get_current_user()`, after decoding the JWT, look up the session by `jti`. Reject if:
   - Session row doesn't exist
   - `revoked_at` is set
   - `token_version` on the user doesn't match (global invalidation)

   Update `last_active_at` on the session row (throttle to once per 5 minutes to avoid DB write on every request — use Redis or an in-memory timestamp).

3. **Logout** — Set `revoked_at = now()` and `revoke_reason = 'user_logout'` on the session row. Clear the cookie.

4. **Password change** — Increment `token_version` on the user (invalidates ALL sessions). Set `revoke_reason = 'password_change'` on all active sessions.

5. **Session cleanup** — Background job (daily) deletes expired sessions older than 30 days.

**Performance note:** The session lookup on every request adds one DB query. Cache active session IDs in Redis with a 5-minute TTL to minimize DB hits:
```
Key: session:{jti}  Value: "active" or "revoked"  TTL: 300s
```
On cache miss, fall through to DB. On revocation, delete the Redis key immediately.

### Backend Router

**File to create:** `services/api/app/routers/sessions.py`

```
GET  /api/auth/sessions              — List active sessions for current user
DELETE /api/auth/sessions/{id}       — Revoke a specific session
DELETE /api/auth/sessions            — Revoke all sessions except current ("log out everywhere")
```

Register in `main.py`.

### Frontend

**File to modify:** `apps/web/app/settings/page.tsx` (or create `apps/web/app/settings/security/page.tsx`)

Add a "Active Sessions" section:
- Table showing: Device/browser, IP address, last active, created date
- "Revoke" button per session (except current session, which shows "Current")
- "Log Out All Other Devices" button
- Current session highlighted in green

---

## Phase 2: API Abuse Detection & Account Lockout

### What It Does

Detects and responds to suspicious authentication patterns: repeated failed logins, credential stuffing, impossible travel, and off-hours access from new locations. Locks accounts after threshold breaches and alerts admins.

### Database Migration

**File to create:** `services/api/alembic/versions/xxxx_add_abuse_detection.py`

```sql
-- Track every auth attempt (success or failure)
CREATE TABLE auth_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- NULL if unknown user
    email VARCHAR(255),                       -- Always stored (even if user not found)
    event_type VARCHAR(30) NOT NULL,          -- 'login_success', 'login_failed', 'otp_failed', 'otp_success', 'signup', 'password_reset'
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(500),
    country_code VARCHAR(2),                  -- GeoIP
    failure_reason VARCHAR(100),              -- 'bad_password', 'bad_otp', 'account_locked', 'user_not_found'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_auth_events_email ON auth_events(email, created_at DESC);
CREATE INDEX idx_auth_events_ip ON auth_events(ip_address, created_at DESC);
CREATE INDEX idx_auth_events_user ON auth_events(user_id, created_at DESC);
CREATE INDEX idx_auth_events_created ON auth_events(created_at);

-- Add lockout fields to users table
ALTER TABLE users ADD COLUMN account_locked_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN account_lock_reason VARCHAR(100);
ALTER TABLE users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN failed_login_window_start TIMESTAMPTZ;
```

### Backend Service

**File to create:** `services/api/app/services/abuse_detection.py`

```python
"""
API abuse detection service.
Monitors auth events and enforces account lockout policies.
"""

# --- Configuration ---
LOCKOUT_THRESHOLD = 10          # Failed logins before lockout
LOCKOUT_WINDOW_MINUTES = 30     # Rolling window for counting failures
LOCKOUT_DURATION_MINUTES = 30   # How long the lockout lasts
IP_BLOCK_THRESHOLD = 50         # Failed attempts from one IP in window → temp IP block
IMPOSSIBLE_TRAVEL_KPH = 1000    # Flag if two logins from locations >1000km apart within 1 hour

# --- Core Functions ---

def record_auth_event(
    session, email, event_type, ip_address, user_agent,
    user_id=None, failure_reason=None
):
    """
    Log every auth attempt. Called from login, OTP verify, signup, password reset.
    After recording, check thresholds and lock if needed.
    """

def check_account_locked(session, user) -> tuple[bool, str | None]:
    """
    Returns (is_locked, reason). Check:
    1. Is account_locked_at set and still within lockout duration?
    2. Auto-unlock if lockout has expired.
    """

def check_ip_blocked(session, ip_address) -> bool:
    """
    Count failed auth_events from this IP in the last LOCKOUT_WINDOW_MINUTES.
    Return True if above IP_BLOCK_THRESHOLD.
    """

def detect_impossible_travel(session, user_id, current_ip) -> bool:
    """
    Compare current login IP's geolocation with the last successful login.
    Flag if distance / time_delta implies speed > IMPOSSIBLE_TRAVEL_KPH.
    Uses a simple GeoIP city-level lookup (MaxMind GeoLite2 or ipinfo.io free tier).
    Does NOT block — just flags for logging and optional notification.
    """

def get_abuse_summary(session, user_id=None, ip=None, hours=24) -> dict:
    """
    Admin endpoint helper. Returns event counts grouped by type for a user or IP.
    """

def unlock_account(session, user_id, admin_user_id=None):
    """
    Clear lockout. Log the unlock event. Called by admin or auto-expiry.
    """
```

### Integration with Auth Router

**File to modify:** `services/api/app/routers/auth.py`

In the login handler, **before** checking the password:
1. Call `check_account_locked()` — if locked, return 423 with lockout message and remaining minutes
2. Call `check_ip_blocked()` — if blocked, return 429 with generic message (don't reveal that it's an IP block)

After password check:
3. Call `record_auth_event()` with success or failure
4. On failure, check if `failed_login_count` has crossed `LOCKOUT_THRESHOLD` → lock account

Same pattern for `verify-otp` endpoint.

### Admin Endpoints

**File to create or modify:** `services/api/app/routers/admin_security.py`

```
GET  /api/admin/security/auth-events?email=&ip=&hours=24  — Query auth event log
GET  /api/admin/security/locked-accounts                  — List currently locked accounts
POST /api/admin/security/unlock/{user_id}                 — Manually unlock an account
GET  /api/admin/security/ip-report/{ip}                   — Abuse summary for an IP
```

All gated by `ADMIN_TOKEN` header (not query param — fix the existing admin endpoints that use query params).

### Background Job

**Add to:** `services/api/app/worker.py` or scheduler

```python
# Daily cleanup: delete auth_events older than 90 days
# Weekly: generate abuse summary report (top offending IPs, locked accounts)
```

---

## Phase 3: IP Protection & Access Controls

### What It Does

Three capabilities: (1) admin endpoint IP allowlisting, (2) per-user IP allowlisting for enterprise employers, (3) country-level geo-blocking for compliance.

### Configuration

**Environment variables:**

```bash
# Admin IP allowlist — comma-separated CIDRs. Empty = no restriction.
ADMIN_IP_ALLOWLIST=203.0.113.0/24,198.51.100.42/32

# Geo-block — comma-separated ISO country codes to BLOCK. Empty = allow all.
GEO_BLOCK_COUNTRIES=

# GeoIP provider
GEOIP_PROVIDER=ipinfo          # "ipinfo" (free tier, 50k/mo) or "maxmind" (GeoLite2 DB file)
IPINFO_TOKEN=                  # Only needed for ipinfo provider
MAXMIND_DB_PATH=               # Only needed for maxmind provider
```

### Backend Service

**File to create:** `services/api/app/services/ip_protection.py`

```python
"""
IP-based access controls: allowlisting, geo-blocking, GeoIP resolution.
"""

# --- GeoIP Resolution ---

def get_ip_info(ip_address: str) -> dict:
    """
    Returns {country: "US", city: "Austin", region: "TX", lat: ..., lon: ...}
    Caches results in Redis (TTL 24h) to minimize external API calls.
    Supports ipinfo.io free tier or MaxMind GeoLite2 local DB.
    """

# --- Admin IP Allowlist ---

def check_admin_ip(ip_address: str) -> bool:
    """
    If ADMIN_IP_ALLOWLIST is set, return True only if IP is in an allowed CIDR.
    If ADMIN_IP_ALLOWLIST is empty, return True (no restriction).
    Uses Python's ipaddress module for CIDR matching.
    """

# --- Geo-blocking ---

def check_geo_allowed(ip_address: str) -> bool:
    """
    If GEO_BLOCK_COUNTRIES is set, resolve IP country and block if it matches.
    Returns True if allowed, False if blocked.
    """

# --- Enterprise Employer IP Allowlist ---

def check_employer_ip_allowed(employer_id: int, ip_address: str, session) -> bool:
    """
    If the employer has configured an IP allowlist (stored on employer_profiles),
    only allow API calls from those CIDRs. Used for enterprise SSO setups.
    Returns True if no allowlist configured (default open).
    """
```

### Database Changes

**Add to employer_profiles table:**

```sql
ALTER TABLE employer_profiles ADD COLUMN ip_allowlist TEXT[];  -- Array of CIDR strings, NULL = no restriction
```

### Integration

**Admin endpoints:** Add `check_admin_ip()` as a dependency for all `/api/admin/*` routes. Return 403 if IP not in allowlist.

**Geo-blocking:** Add as middleware in `main.py` — check on every request. Return 403 with message "Service not available in your region." Log blocked attempts.

**Employer IP allowlist:** Add as an optional check in `get_employer_profile()` dependency. If the employer has an allowlist configured, verify the request IP.

### Frontend

**File to modify:** `apps/web/app/employer/settings/page.tsx`

Add an "IP Allowlist" section (Pro plan only):
- Text area for entering CIDR ranges (one per line)
- Validation that entries are valid CIDR notation
- Current IP shown: "Your current IP: x.x.x.x"
- Warning: "Enabling this will restrict API access to these IP ranges only"

---

## Phase 4: WAF via Google Cloud Armor

### What It Does

Adds a Google Cloud Armor security policy in front of the API and Web Cloud Run services. Provides DDoS protection, OWASP Top 10 rule sets, rate limiting at the edge, and geographic controls at the infrastructure level.

### Why Cloud Armor (Not Cloudflare)

Winnow is already on GCP (Cloud Run, Cloud SQL, GCS). Cloud Armor integrates natively with Cloud Run via a Global External Application Load Balancer. No DNS change or proxy hop needed. The free tier covers basic rules; managed WAF rules are ~$5/rule/month.

### Prerequisites

Cloud Armor requires a **Global External Application Load Balancer** (GXLB) in front of Cloud Run. Currently, Cloud Run services are accessed directly via their `.run.app` URLs. This phase adds the load balancer.

### Infrastructure Changes

**File to create:** `infra/cloud-armor/setup.sh`

This is a reference script (not automated CI) documenting the GCP commands:

```bash
#!/usr/bin/env bash
# Cloud Armor WAF setup for Winnow
# Run these commands once in GCP Console or via gcloud CLI.
# Prerequisites: gcloud CLI authenticated, project set.

PROJECT_ID="winnow-prod"
REGION="us-central1"

# 1. Create a Serverless Network Endpoint Group (NEG) for the API
gcloud compute network-endpoint-groups create winnow-api-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=winnow-api

# 2. Create a Serverless NEG for the Web frontend
gcloud compute network-endpoint-groups create winnow-web-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=winnow-web

# 3. Create backend services
gcloud compute backend-services create winnow-api-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend winnow-api-backend \
  --global \
  --network-endpoint-group=winnow-api-neg \
  --network-endpoint-group-region=$REGION

gcloud compute backend-services create winnow-web-backend \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED
gcloud compute backend-services add-backend winnow-web-backend \
  --global \
  --network-endpoint-group=winnow-web-neg \
  --network-endpoint-group-region=$REGION

# 4. Create URL map (route /api/* to API, everything else to Web)
gcloud compute url-maps create winnow-lb \
  --default-service=winnow-web-backend
gcloud compute url-maps add-path-matcher winnow-lb \
  --path-matcher-name=api-matcher \
  --default-service=winnow-web-backend \
  --path-rules="/api/*=winnow-api-backend,/ws/*=winnow-api-backend"

# 5. Create SSL certificate (managed by Google)
gcloud compute ssl-certificates create winnow-cert \
  --domains=winnowcc.ai,www.winnowcc.ai

# 6. Create HTTPS proxy and forwarding rule
gcloud compute target-https-proxies create winnow-https-proxy \
  --url-map=winnow-lb \
  --ssl-certificates=winnow-cert
gcloud compute forwarding-rules create winnow-https-rule \
  --global \
  --target-https-proxy=winnow-https-proxy \
  --ports=443

# 7. Create Cloud Armor security policy
gcloud compute security-policies create winnow-waf \
  --description="Winnow WAF policy"

# 8. Add OWASP ModSecurity Core Rule Set (preconfigured managed rules)
gcloud compute security-policies rules create 1000 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('sqli-v33-stable')" \
  --action=deny-403 \
  --description="Block SQL injection"

gcloud compute security-policies rules create 1001 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('xss-v33-stable')" \
  --action=deny-403 \
  --description="Block XSS"

gcloud compute security-policies rules create 1002 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('lfi-v33-stable')" \
  --action=deny-403 \
  --description="Block local file inclusion"

gcloud compute security-policies rules create 1003 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('rfi-v33-stable')" \
  --action=deny-403 \
  --description="Block remote file inclusion"

gcloud compute security-policies rules create 1004 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('rce-v33-stable')" \
  --action=deny-403 \
  --description="Block remote code execution"

gcloud compute security-policies rules create 1005 \
  --security-policy=winnow-waf \
  --expression="evaluatePreconfiguredWaf('scanner-detection-v33-stable')" \
  --action=deny-403 \
  --description="Block scanner/bot probing"

# 9. Rate limiting at edge (complements app-level slowapi)
gcloud compute security-policies rules create 2000 \
  --security-policy=winnow-waf \
  --expression="true" \
  --action=rate-based-ban \
  --rate-limit-threshold-count=300 \
  --rate-limit-threshold-interval-sec=60 \
  --ban-duration-sec=600 \
  --conform-action=allow \
  --exceed-action=deny-429 \
  --enforce-on-key=IP \
  --description="Ban IPs exceeding 300 req/min for 10 minutes"

# 10. Geo-blocking rule (optional — uncomment and set countries)
# gcloud compute security-policies rules create 3000 \
#   --security-policy=winnow-waf \
#   --expression="origin.region_code == 'CN' || origin.region_code == 'RU'" \
#   --action=deny-403 \
#   --description="Block traffic from specific countries"

# 11. Attach policy to backend services
gcloud compute backend-services update winnow-api-backend \
  --global \
  --security-policy=winnow-waf
gcloud compute backend-services update winnow-web-backend \
  --global \
  --security-policy=winnow-waf

# 12. Update DNS: point winnowcc.ai A record to the load balancer IP
echo "Get the LB IP with: gcloud compute forwarding-rules describe winnow-https-rule --global --format='get(IPAddress)'"
echo "Update winnowcc.ai DNS A record to this IP."
```

### DNS Change

After the load balancer is created, update `winnowcc.ai` DNS:
- Change the A record from the Cloud Run direct mapping to the load balancer's static IP
- The `www` CNAME can stay pointing to the apex

### Monitoring

**File to create:** `infra/cloud-armor/alerts.sh`

```bash
# Create alert policy for WAF blocks (fires if >100 blocks in 5 minutes)
gcloud alpha monitoring policies create \
  --display-name="WAF High Block Rate" \
  --condition-display-name="Cloud Armor blocks > 100/5min" \
  --condition-filter='resource.type="https_lb_rule" AND metric.type="loadbalancing.googleapis.com/https/request_count" AND metric.labels.response_code="403"' \
  --condition-threshold-value=100 \
  --condition-threshold-duration=300s \
  --notification-channels=YOUR_CHANNEL_ID
```

### Cost Estimate

| Component | Monthly Cost |
|---|---|
| Global External LB | ~$18 (forwarding rule) |
| Cloud Armor policy | Free (up to 5 rules) |
| Managed WAF rules | ~$5/rule/month beyond free tier |
| SSL certificate | Free (Google-managed) |
| **Total** | **~$48/month** |

---

## Testing Checklist

### Critical Fixes
- [ ] Login endpoint returns 429 after 10 attempts in 1 minute
- [ ] Signup endpoint returns 429 after 5 attempts in 1 minute
- [ ] Resend-OTP endpoint returns 429 after 3 attempts in 1 minute
- [ ] Forgot-password endpoint returns 429 after 5 attempts in 1 minute
- [ ] CSP header present on API responses
- [ ] Password shorter than 8 chars rejected by API (not just frontend)
- [ ] Standalone SMS OTP service removed or secured

### Phase 1: Session Management
- [ ] Login creates a session row in `user_sessions`
- [ ] JWT contains `jti` claim matching the session ID
- [ ] `GET /api/auth/sessions` returns list of active sessions with device info
- [ ] `DELETE /api/auth/sessions/{id}` revokes a session
- [ ] Revoked session's JWT is rejected on next API call
- [ ] `DELETE /api/auth/sessions` revokes all except current
- [ ] Password change invalidates all sessions (token_version increment)
- [ ] Logout sets `revoked_at` on the session row
- [ ] Expired sessions cleaned up by daily background job
- [ ] Redis cache prevents DB hit on every request
- [ ] `last_login_at` and `last_login_ip` updated on the User row

### Phase 2: Abuse Detection
- [ ] Failed logins recorded in `auth_events` table
- [ ] Successful logins recorded in `auth_events` table
- [ ] Account locks after 10 failed attempts in 30 minutes
- [ ] Locked account returns 423 with remaining lockout time
- [ ] Account auto-unlocks after 30 minutes
- [ ] IP blocked after 50 failed attempts from same IP in 30 minutes
- [ ] Blocked IP gets 429 (not 423 — don't reveal it's an IP block)
- [ ] Impossible travel detected and logged (does not block, only flags)
- [ ] Admin can view auth events by email, IP, or user
- [ ] Admin can manually unlock an account
- [ ] Old auth events purged after 90 days

### Phase 3: IP Protection
- [ ] Admin endpoints blocked when request IP not in `ADMIN_IP_ALLOWLIST`
- [ ] Admin endpoints accessible when allowlist is empty (default open)
- [ ] GeoIP resolution works and caches in Redis
- [ ] Geo-blocked country returns 403
- [ ] Employer can configure IP allowlist in settings (Pro only)
- [ ] Employer IP allowlist enforced on employer API calls
- [ ] Empty employer allowlist means no restriction (default open)

### Phase 4: WAF
- [ ] Load balancer routes `/api/*` to API service, all else to Web
- [ ] SSL terminates at the LB with valid cert for winnowcc.ai
- [ ] SQL injection payload blocked with 403
- [ ] XSS payload blocked with 403
- [ ] Rate limiting at edge bans IPs exceeding 300 req/min
- [ ] Cloud Armor logs visible in GCP Console
- [ ] Alert fires when block rate exceeds threshold

---

## Files Summary

### New Files to Create

| # | File Path | Purpose |
|---|---|---|
| 1 | `services/api/alembic/versions/xxxx_add_sessions_table.py` | Sessions table + user audit fields migration |
| 2 | `services/api/alembic/versions/xxxx_add_abuse_detection.py` | Auth events table + user lockout fields migration |
| 3 | `services/api/app/models/session.py` | SQLAlchemy model for `user_sessions` |
| 4 | `services/api/app/models/auth_event.py` | SQLAlchemy model for `auth_events` |
| 5 | `services/api/app/services/abuse_detection.py` | Abuse detection, lockout, impossible travel |
| 6 | `services/api/app/services/ip_protection.py` | GeoIP, admin allowlist, geo-blocking, employer allowlist |
| 7 | `services/api/app/routers/sessions.py` | Active sessions list, revoke endpoints |
| 8 | `infra/cloud-armor/setup.sh` | Cloud Armor WAF setup reference script |
| 9 | `infra/cloud-armor/alerts.sh` | Monitoring alert setup reference script |

### Existing Files to Modify

| # | File Path | What to Change |
|---|---|---|
| 1 | `services/api/app/routers/auth.py` | Add rate limits, abuse detection integration, session creation |
| 2 | `services/api/app/services/auth.py` | Add jti to JWT, session create/validate/revoke, token_version check |
| 3 | `services/api/app/middleware/security_headers.py` | Add Content-Security-Policy header |
| 4 | `services/api/app/main.py` | Register sessions router, add geo-blocking middleware, fix CORS regex |
| 5 | `services/api/app/models/user.py` | Add last_login_at, last_login_ip, token_version, lockout fields |
| 6 | `services/api/app/models/employer.py` | Add ip_allowlist field |
| 7 | `apps/web/app/employer/settings/page.tsx` | Add IP allowlist config section |
| 8 | `.github/workflows/deploy.yml` | Update if LB replaces direct Cloud Run URL |

### Files to Delete (Fix B)

| # | File Path | Reason |
|---|---|---|
| 1 | `services/api/app/services/sms_service.py` | Broken in-memory OTP store, insecure random, no auth |
| 2 | `services/api/app/routers/sms_otp.py` | Router for the broken service above |

---

## Non-Goals (Do NOT Implement in This Prompt)

- TOTP / authenticator app support (Google Authenticator, Authy) — future MFA enhancement
- WebAuthn / passkeys — future passwordless auth
- MFA backup codes — future MFA recovery
- SIEM integration (Datadog, Splunk) — future observability
- Bot detection / CAPTCHA — future anti-automation
- DDoS simulation / load testing — separate effort
- SOC 2 compliance documentation — business process, not code
- VPN detection / residential proxy blocking — over-engineering for current scale
- mTLS between services — Cloud Run VPC connector already provides internal network isolation
