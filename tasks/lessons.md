# Lessons Learned

## Skill Extraction

### 1. SKILL_DATABASE must only contain actual skills, never qualifiers
- **Pattern**: Words like "certified", "certification", "experienced", "proficient" are adjectives/qualifiers, not skills. They match everywhere and produce false positives.
- **Rule**: Only add concrete, nameable skills to SKILL_DATABASE. Specific cert names (PMP, CISSP) are fine; generic words ("certified") are not.
- **Rule**: When adding to SKILL_DATABASE, ask: "Would a recruiter list this as a standalone skill on a job req?" If no, don't add it.

### 2. Multi-word skills must go in MULTI_WORD_SKILLS, not just SKILL_DATABASE
- **Pattern**: SKILL_DATABASE is matched via single-word tokenization (`re.findall(r'[a-zA-Z0-9+.#]+')`). Multi-word entries like "aws certified" in SKILL_DATABASE can never match — they're dead weight.
- **Rule**: Any skill containing a space MUST be added to the `MULTI_WORD_SKILLS` list to be matched. It can optionally also be in SKILL_DATABASE for normalization lookups, but MULTI_WORD_SKILLS is what triggers the match.

### 3. _extract_all_skills must pull from ALL skill sources in the profile
- **Pattern**: Skills live in multiple places: `profile.skills` (top-level), `experience[].skills_used`, `experience[].technologies_used`, AND `preferences.skill_categories`. If `_extract_all_skills` misses any source, the matching engine won't know the user has those skills, causing false "skill gaps".
- **Rule**: When a new place to store skills is added to the profile schema, `_extract_all_skills()` in `matching.py` MUST be updated to read from it. The skill categories widget (`preferences.skill_categories`) is a primary user-curated skill source.

## Profile Data Persistence

### 4. Dedicated sub-resource endpoints must be protected from main resource overwrites
- **Pattern**: `PUT /api/profile/skill-categories` saves skill categories to `preferences.skill_categories`. But `PUT /api/profile` (main save) sends the full `profile_json` which may not include `skill_categories`, silently overwriting them with null.
- **Rule**: When a sub-resource endpoint writes to a nested field within a parent resource, the parent's PUT endpoint must preserve that field if the incoming payload doesn't include it. Check for this whenever adding a new dedicated save endpoint.

### 5. Auto-save UX for drag-and-drop widgets prevents data loss
- **Pattern**: A manual "Save" button on a drag-and-drop widget creates a disconnected state. Users forget to click it, then save something else and lose their work.
- **Rule**: Drag-and-drop category changes should auto-save on drop. Remove manual save buttons and replace with a subtle "Saving..." indicator.

## Server Management

### 6. Always kill ALL server processes when restarting
- **Pattern**: On Windows, `taskkill` on a uvicorn PID may not kill the child worker process. Multiple stale processes can accumulate on the same port, serving old code even after file changes.
- **Rule**: When restarting the API server, kill ALL python.exe processes (`tasklist | grep python`), not just the PID from `netstat`. Verify port is clear before starting a new instance.

### 7. Full restart checklist — do ALL of these every time
- **Pattern**: Stale `.next` cache, wrong env ports, and zombie processes cause "TypeError: fetch failed" and "Internal Server Error" after restarts.
- **Rule**: When restarting services, always follow this sequence:
  1. Kill ALL python.exe and node.exe processes (`Stop-Process -Name python,node -Force`)
  2. Verify `.env.local` has correct API port (`API_BASE_URL=http://127.0.0.1:8000`, NOT 8001)
  3. Delete `apps/web/.next` directory (stale cache causes ISE even after env fixes)
  4. Start infra: `cd infra && docker compose up -d`
  5. Start API, Worker, Web via `start-dev.ps1` or manually
  6. Verify API responds: `curl http://127.0.0.1:8000/docs`
- **Rule**: The `.env.local` port MUST match the uvicorn port (default 8000). Mismatches cause "fetch failed" on every page.

### 8. RQ worker dies on Redis connection timeout — needs auto-restart
- **Pattern**: `SimpleWorker` (used on Windows) exits with `Redis connection timeout, quitting...` after ~40 min idle. When it's down, jobs pile up (34+ observed) and features like resume parsing, email sending, and embedding silently stop working. Users see "Parsing is taking longer than expected" indefinitely.
- **Root cause**: `Redis.from_url()` uses default socket timeout. Long idle periods cause TCP keepalive failure.
- **Rule**: Worker must auto-restart on crash. Wrap `worker.work()` in a retry loop with backoff. Set `socket_keepalive=True` and `socket_timeout` on the Redis connection.
- **Rule**: Always start the RQ worker alongside the API server. Add worker health check to startup scripts.

### 9. Resume parse polling timeout too short for LLM parsing
- **Pattern**: Frontend polls parse status 20x at 1s intervals (20s max). LLM parsing via gpt-4o-mini takes 42-55s. Frontend gives up and shows "Parsing is taking longer than expected" even though the job succeeds.
- **Fix**: Increased to 40 polls at 2s intervals (80s max). Shows elapsed seconds in status message.
- **Rule**: When using LLM-based processing in async jobs, polling windows must be at least 2x the expected LLM response time.

## Data Integrity

### 10. Never merge jobs with different source_job_ids — they are distinct requisitions
- **Pattern**: Ran a dedup script that grouped by title+company and deleted "duplicates". This incorrectly deleted employer-posted jobs that had the same title+company but different `source_job_id` values (e.g., two "Software Developer 2" requisitions for different teams). Lost real job data.
- **Rule**: `source_job_id` is the authoritative unique identifier. Two jobs with different `source_job_id` values are ALWAYS distinct, even if title and company are identical. Any dedup logic must check `source_job_id` first.
- **Rule**: The `(source, source_job_id)` pair must be unique in the DB (enforced via unique constraint). Cross-source fingerprint dedup must skip when `source_job_id` differs.
- **Rule**: Before running any bulk delete/merge operation on production data, always dry-run first and inspect the results. Never auto-delete without verifying the grouping criteria against all use cases (employer vs. board, requisition IDs, etc.).

## Route Registration

### 11. Static sub-routes must be registered BEFORE parameterized routes in FastAPI/Starlette
- **Pattern**: `POST /pipeline/upload-resumes` was registered AFTER `PUT /pipeline/{candidate_id}`. Starlette matches paths in registration order — `{candidate_id}` matched "upload-resumes" as a path parameter, saw wrong method (PUT/DELETE ≠ POST), and returned 405 "Method Not Allowed" before reaching the correct handler.
- **Rule**: In FastAPI routers, always register static sub-paths (`/pipeline/upload-resumes`) BEFORE parameterized paths at the same level (`/pipeline/{candidate_id}`). Starlette resolves the first path match, not the best match.
- **Rule**: When adding a new `/resource/action` endpoint to a router that already has `/resource/{id}`, place it above the `{id}` routes.

## Cookie & Authentication

### 12. `127.0.0.1` and `localhost` are different domains for cookies
- **Pattern**: Frontend at `localhost:3000` and API at `127.0.0.1:8000` are different origins. Cookies set by `127.0.0.1:8000` are NOT sent when the browser navigates to `localhost:3000`. The Next.js middleware forwards browser cookies to the API — but since the `rm_session` cookie belongs to `127.0.0.1`, it's never included in `localhost` requests. Result: middleware auth check always fails → redirect loop to login.
- **Fix**: Changed `NEXT_PUBLIC_API_BASE_URL` from `http://127.0.0.1:8000` to `http://localhost:8000`. Cookies for `localhost` are shared across ports (3000 and 8000).
- **Rule**: Frontend and API must use the SAME hostname (both `localhost` or both `127.0.0.1`). Never mix them. Ports don't matter for cookie scope, but hostnames do.
- **Rule**: Update lesson #7 — `.env.local` should use `http://localhost:8000`, NOT `http://127.0.0.1:8000`.

### 13. Time-critical emails (MFA OTP) must send synchronously, not via RQ
- **Pattern**: MFA OTP email was enqueued to RQ worker, but the worker had a 44-job backlog. OTP codes expire in 10 minutes — by the time the worker processed the job, the code was expired or the user had given up.
- **Fix**: Changed `_generate_and_send_otp()` to call `send_mfa_otp_email()` directly instead of enqueuing.
- **Rule**: Any email with a short expiry (OTP, MFA, time-sensitive notifications) must send synchronously. Only use RQ for non-urgent emails (verification links, marketing, password reset with 30-min expiry).
- **Rule**: Wrap synchronous email sends in try/except so delivery failures don't crash the endpoint.

### 14. FastAPI `Response` dependency may not carry `Set-Cookie` through middleware stacks
- **Pattern**: `verify-otp` used FastAPI's `response: Response` dependency to set the auth cookie via `set_auth_cookie(response, ...)`. The cookie wasn't appearing in the HTTP response — likely because stacked middleware (slowapi rate limiter, security headers, etc.) interfered with header propagation.
- **Fix**: Changed `verify-otp` to return a `JSONResponse` directly with `resp.set_cookie(...)` set on it. This guarantees the cookie is in the response regardless of middleware.
- **Rule**: For endpoints that MUST set cookies (login, OTP verification), return a `JSONResponse` with cookies set directly on it rather than using the `Response` dependency. This is more reliable through middleware stacks.

### 15. Dev mode: show OTP codes on screen when email delivery is unreliable
- **Pattern**: In local dev, Resend sandbox sender (`onboarding@resend.dev`) may fail to deliver emails. MFA becomes unusable because the user can't get the code.
- **Fix**: Added `dev_otp` field to `MfaRequiredResponse` (only populated when `FRONTEND_URL` contains `localhost`). Frontend shows it in a yellow dev box.
- **Rule**: For any auth flow that depends on external delivery (email, SMS), add a dev-mode bypass that shows the code on screen. Gate it behind a clear dev-mode check.

## Page Architecture

### 16. NEVER overwrite files without backing up uncommitted work first
- **Pattern**: User had an uncommitted marketing landing page at `apps/web/app/page.tsx` built in a prior Claude Code session. Writing a new version destroyed it. `git checkout HEAD` restored the committed version (a login form), not the user's work. Recovery required searching through Claude session transcript JSONL files.
- **Rule**: Before overwriting ANY file, always run `git diff -- <file>` to check for uncommitted changes. If there are uncommitted changes, back up the file first (e.g., `cp file file.bak`) and inform the user.
- **Rule**: Never assume `git checkout HEAD` will restore what the user had — it only restores the last committed version, not uncommitted work.

### 17. Landing page (/) and login page (/login) are SEPARATE pages with distinct purposes
- **Pattern**: `/` is the full-width marketing landing page with video hero, audience toggle (seekers/employers/recruiters), features, pricing, and competitive comparison. `/login` is the two-panel auth page. These must never be conflated.
- **Rule**: `/login/page.tsx` must NEVER redirect to `/`. It is a real page with its own layout.
- **Architecture**:
  - `apps/web/app/page.tsx` — Marketing landing page. Full-width video hero (`Winnow Vid AI Gend.mp4`), audience toggle, features, how it works, comparison, pricing. CTAs link to `/login?mode=signup`.
  - `apps/web/app/login/page.tsx` — Two-panel auth page. Left: login/signup form (social + email/password) with white-to-transparent gradient over video. Right: Winnow logo (`Winnow CC Masthead TBGC.png`), marketing copy, IPS feature highlight over shared video background. Full-width `Winnow Vid AI Gend.mp4` behind both panels.
  - `apps/web/app/signup/page.tsx` — Redirect-only, sends to `/login?mode=signup`.
- **Key details**:
  - Login page video spans full width behind both panels (not confined to right panel)
  - Left panel has gradient: solid white at bottom (email form), fading to transparent above (auth0 cards see through to video)
  - Right panel text block max-width: 550px
  - Winnow logo lives in right panel, `h-[120px]`
  - "Welcome back" and subtitle are white text
  - Video overlay is `bg-slate-900/45`

### 18. The navbar logo on the landing page uses `Winnow CC Masthead TBGC.png` at `h-12`
- **Pattern**: The landing page navbar logo was changed from `Winnow Masthead Gold Shadow.png` (h-8) to `Winnow CC Masthead TBGC.png` (h-12) for better legibility.
- **Rule**: When referencing the Winnow logo, use `Winnow CC Masthead TBGC.png` unless the user specifies otherwise. Available logos in `apps/web/public/`: `Winnow CC Masthead TBGC.png`, `Winnow Masthead Gold Shadow.png`, `Winnow Masthead Wheat Shadow.png`.

## Mobile App Deployment (2026-02-22)

### 19. bcrypt 4.1+ breaks passlib — pin bcrypt<4.1
- **Problem**: `passlib` uses `bcrypt.__about__.__version__` for backend detection. `bcrypt>=4.1` removed that attribute, causing `AttributeError` on every `hash_password()` / `verify_password()` call — 500 on both login and signup in production.
- **Fix**: Pin `bcrypt>=4.0,<4.1` in `requirements.txt`.
- **Rule**: When using `passlib[bcrypt]`, always pin `bcrypt<4.1`. Check Cloud Run logs (`gcloud logging read`) for production errors — don't assume the API works just because `/health` returns 200.

### 20. Verify custom domain mapping before using it in builds
- **Problem**: `api.winnowcc.ai` was set as `EXPO_PUBLIC_API_BASE_URL` in EAS builds, but no Cloud Run domain mapping or SSL cert existed. Mobile app couldn't reach the API.
- **Fix**: Point directly at the Cloud Run URL (`winnow-api-cdn2d6pc5q-uc.a.run.app`) in `eas.json`, `.env.production`, and the deploy workflow's `NEXT_PUBLIC_API_BASE_URL` build arg.
- **Rule**: Always verify the API URL is reachable (`curl -s <url>/health`) before building a mobile release. Don't assume custom domains are configured.

### 21. Production database is empty — dev seed accounts don't exist
- **Problem**: Tried logging in with dev seed accounts (`akshitha@test.com`, etc.) on production. They don't exist.
- **Rule**: After deploying to a fresh production database, accounts must be created via signup. Dev seed data doesn't carry over. Consider adding an admin seed script.

### 22. Pushing to main triggers deploy which can reset the database
- **Problem**: Every push to `main` triggers the deploy workflow which re-runs migrations. User accounts created between deploys can be lost.
- **Rule**: Be aware that pushing to `main` triggers a full redeploy. Manually created accounts may need to be recreated. The `promote-admin` Cloud Run job pattern (SQL via env var) is useful for post-deploy setup.

### 23. FlatList causes native crashes on iOS production builds in Expo
- **Problem**: Sieve chat screen used two `FlatList` components (messages + horizontal suggested actions). This caused a native crash on iOS production builds. Expo's error boundary showed "Winnow Career Concierge Crashed" with no useful JS error. React error boundaries could NOT catch it — it was a native-level crash.
- **Fix**: Replace `FlatList` with `ScrollView` + `.map()` for both messages and suggestions.
- **Rule**: In Expo production iOS builds, prefer `ScrollView` over `FlatList` for chat-style UIs with <50 items. `FlatList` virtualization can cause native crashes invisible to JS error boundaries. Only use `FlatList` for genuinely large datasets (hundreds+ items).
- **Debugging approach**: When a crash bypasses React error boundaries, strip the screen to a bare minimum, confirm it works, then add features back incrementally. This is faster than guessing.

### 24. Cloud Run job args: use env vars, not inline scripts
- **Problem**: Multi-line Python scripts via `--args` silently fail — newlines get stripped, `exec()` with escaped newlines produces `SyntaxError`. Jobs exit(0) without actually running the script.
- **Fix**: Use single-line Python with semicolons. Pass dynamic values via `--set-env-vars` instead of embedding in the script. Always check logs to verify execution.
- **Rule**: For Cloud Run jobs: (1) single-line Python with semicolons, (2) variable data in env vars, (3) verify with `gcloud logging read` that the script printed expected output.

### 25. EAS preview profile needs interactive Apple auth; use production for CI
- **Problem**: `eas build --profile preview --non-interactive` failed because iOS internal distribution (ad-hoc) requires Apple credentials not cached on the EAS server.
- **Fix**: Use `--profile production` for non-interactive/CI builds — App Store distribution creds were already configured.
- **Rule**: For automated builds, use the `production` profile. The `preview` profile (internal distribution) needs interactive Apple login.
