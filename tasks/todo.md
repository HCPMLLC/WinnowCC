# PROMPT67 — Advanced Security & IP Protection

## Status: COMPLETE

### Group 1: Rate-limit auth endpoints
- [x] Add `@limiter.limit()` + `request: Request` to signup (5/min), login (10/min), verify-otp (10/min), resend-otp (3/min), forgot-password (5/min), reset-password (5/min)

### Group 2: Critical Fixes B–E
- [x] Delete broken SMS OTP service (`sms_service.py`, `sms_otp.py`, remove from `main.py`)
- [x] Add CSP header to API security middleware (`default-src 'none'; frame-ancestors 'none'`)
- [x] Add CSP + security headers to Next.js frontend (`next.config.js` `headers()`)
- [x] Add server-side min password length (8 chars) in `_validate_password()`
- [x] Add CORS Chrome extension TODO comment for specific extension ID

### Group 3: Session Management — DB + Model
- [x] Migration `a1b2c3d4e5f6` — `user_sessions` table + `last_login_at`, `last_login_ip`, `token_version` on users
- [x] `models/session.py` — `UserSession` model
- [x] `models/user.py` — session + lockout columns added

### Group 4: Session Management — Auth Service
- [x] `make_token()` — now returns `(token, jti)` tuple with `jti` + `ver` claims
- [x] `create_session()` — inserts UserSession row
- [x] `set_auth_cookie()` — accepts `request` + `db_session`, creates DB session, updates last login
- [x] `get_current_user()` — validates session via `_validate_session()` (Redis cache + DB lookup)
- [x] `revoke_session()` / `revoke_all_sessions()` — session revocation
- [x] `clear_auth_cookie()` — revokes session on logout
- [x] Updated all callers: signup, login, verify-otp, reset-password, oauth-callback, logout

### Group 5: Sessions Router + Frontend + Cleanup
- [x] `routers/sessions.py` — GET/DELETE /api/auth/sessions
- [x] Registered in `main.py`
- [x] Scheduled jobs: `scheduled_cleanup_expired_sessions()` (3:30 AM), `scheduled_purge_old_auth_events()` (4:30 AM)
- [x] Registered in `scheduler.py`
- [x] Active Sessions UI in `apps/web/app/settings/page.tsx`

### Group 6: Abuse Detection
- [x] Migration `b2c3d4e5f6a7` — `auth_events` table + lockout columns on users
- [x] `models/auth_event.py` — `AuthEvent` model
- [x] `services/abuse_detection.py` — full service (record, check_locked, check_ip, handle failure/success, unlock, summary)
- [x] Login endpoint: IP block check, account lockout check, failure tracking, success reset
- [x] Signup endpoint: records auth event
- [x] Admin endpoints in `security_check.py`: GET auth-events, GET locked-accounts, POST unlock/{user_id}

### Group 7: IP Protection
- [x] `services/ip_protection.py` — get_client_ip, check_admin_ip (CIDR), check_geo_allowed (ipinfo.io + Redis), check_employer_ip_allowed
- [x] `middleware/geo_block.py` — GeoBlockMiddleware (skips /api/auth/, /health, /ready)
- [x] Registered in `main.py`
- [x] Admin IP check integrated in `require_admin_user()`
- [x] Employer IP allowlist check in `get_employer_profile()`
- [x] Migration `c3d4e5f6a7b8` — `ip_allowlist` JSONB column on `employer_profiles`
- [x] `models/employer.py` — `ip_allowlist` column
- [x] IP Allowlist UI in `apps/web/app/employer/settings/page.tsx` (Pro only)

### Group 8: WAF — Cloud Armor
- [x] `infra/cloud-armor/setup.sh` — OWASP rules, edge rate limiting, backend attachment
- [x] `infra/cloud-armor/alerts.sh` — monitoring alerts for WAF blocks + auth abuse

## Verification
- [x] `ruff check .` — Python lint passes
- [x] `npm run lint` — Frontend lint passes
- [x] All Python files parse without syntax errors
