# API

## Run locally (Windows PowerShell)
```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DB_URL="postgresql+psycopg://user:pass@localhost:5432/resumematch"
$env:AUTH_SECRET="dev-secret-change-me"
$env:AUTH_COOKIE_NAME="rm_session"
$env:AUTH_TOKEN_EXPIRES_DAYS="7"
uvicorn app.main:app --reload
```

## Alembic migrations (local)
```powershell
cd services\api
$env:DB_URL="postgresql+psycopg://user:pass@localhost:5432/resumematch"
alembic revision --autogenerate -m "init"
alembic upgrade head
```

Auth notes:
- Cookies are HttpOnly and SameSite=Lax.
- Use a stable `AUTH_SECRET` locally so sessions persist across restarts.

## Job ingestion (v1)
Configured sources (set via `JOB_SOURCES`):
- remotive (public API)
- themuse (public API)
- greenhouse (public boards; requires `GREENHOUSE_COMPANIES` list)
- lever (public boards; requires `LEVER_COMPANIES` list)
- remoteok (public API)
- arbeitnow (public API)
- adzuna (API key required)
- jooble (API key required)
- usajobs (API key + email required)
- ziprecruiter (API key required)
- builtin (API key required; placeholder)
- manual (JSON list via `MANUAL_JOBS_PATH`)

Notes:
- LinkedIn/Google Jobs are not integrated (no scraping).
- For company career pages, use `MANUAL_JOBS_PATH` to seed postings or add
  public Greenhouse/Lever company slugs.
