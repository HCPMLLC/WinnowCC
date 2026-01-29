# PROMPT_AUTH_ONBOARDING_IMPLEMENT_V1.md

Implement Auth + Onboarding v1 end-to-end.

Repo structure:
- API: services/api (FastAPI, SQLAlchemy 2.0, Alembic)
- Web: apps/web (Next.js App Router)

### API (services/api)
1) Add dependencies to services/api/requirements.txt:
- passlib[bcrypt]
- python-jose[cryptography]

2) Add env vars to services/api/.env.example:
AUTH_SECRET=dev-secret-change-me
AUTH_COOKIE_NAME=rm_session
AUTH_TOKEN_EXPIRES_DAYS=7

3) Ensure dotenv loads at API startup (single place):
- Update services/api/app/main.py to call load_dotenv(dotenv_path=Path(".../services/api/.env")) early.
- Remove per-request dotenv loads and any debug prints.

4) Create models + migration:
- users table: id, email unique, password_hash, onboarding_completed_at, is_admin, created_at, updated_at
- candidate table: id, user_id unique FK users.id, first_name,last_name,phone,location_city,state,country,work_authorization,
  years_experience, desired_job_types JSON, desired_locations JSON, desired_salary_min/max, remote_preference, created_at, updated_at

Alembic: create new revision to create these tables.

5) Auth utilities:
- services/api/app/services/auth.py:
  - hash_password / verify_password
  - create_jwt / decode_jwt
  - set_auth_cookie(response) / clear_auth_cookie(response)
  - get_current_user dependency (reads cookie, validates JWT, loads user from DB)

Cookie should be HttpOnly, SameSite=Lax, Path=/.
In dev, Secure=False.

6) Routers:
- services/api/app/routers/auth.py
  POST /api/auth/signup {email,password}
  POST /api/auth/login {email,password}
  POST /api/auth/logout
  GET /api/auth/me -> {user_id,email,onboarding_complete}

- services/api/app/routers/onboarding.py
  GET /api/onboarding/me -> candidate record for current user
  POST /api/onboarding/complete -> upsert candidate + set onboarding_completed_at

7) Gate + scope:
- Require auth on existing endpoints:
  - /api/resume/upload (set resume_documents.user_id)
  - /api/profile/* (read/write by user_id)
  - /api/trust/me (return trust for current user)
  - /api/match/run (require onboarding_complete and trust_gate allowed)
If existing tables don’t yet have user_id, add minimal migrations to add user_id columns and index them.
If that’s too big right now: implement “scope by latest resume_document belonging to current user” and add user_id only to resume_documents + candidate_profiles + job_runs first.

8) CORS:
Allow web origin http://localhost:3000 and allow credentials.
Add CORSMiddleware with allow_credentials=True.

### Web (apps/web)
1) Ensure all fetch calls to API use:
- base URL = NEXT_PUBLIC_API_BASE_URL (default http://127.0.0.1:8000)
- credentials: "include"

2) Add /onboarding page implementation (simple form):
fields: first_name,last_name,phone,location_city,state,country,work_authorization, desired_job_types (comma), desired_locations (comma), desired_salary_min, desired_salary_max, remote_preference
POST to /api/onboarding/complete then redirect /upload.

3) Add route guard helper in apps/web/app/lib/auth.ts:
- fetch /api/auth/me with credentials include
- return onboarding_complete and user_id
Use it in /upload, /profile, /dashboard via client-side redirect.

4) Update /upload and /profile pages to check auth/me and redirect to /login or /onboarding if needed.

Deliverables:
- Migrations
- New API routes
- Web onboarding form + guard
- README updates: how to run locally with env vars and cookies
