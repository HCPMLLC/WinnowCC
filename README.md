# Winnow Monorepo

Package manager: npm (pnpm not available in this environment).

## Local dev (Windows PowerShell)

### 1) Start Postgres + Redis
```
cd infra
docker compose up -d
```

### 2) Run the API
```
cd ..\services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
$env:DB_URL="postgresql://resumematch:resumematch@localhost:5432/resumematch"
$env:REDIS_URL="redis://localhost:6379/0"
$env:ADMIN_TOKEN="dev-admin-token"
$env:AUTH_SECRET="dev-secret-change-me"
$env:AUTH_COOKIE_NAME="rm_session"
$env:AUTH_TOKEN_EXPIRES_DAYS="7"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) Run the web app
```
cd ..\..\apps\web
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
$env:NEXT_PUBLIC_ADMIN_TOKEN="dev-admin-token"
npm run dev
```

Notes:
- Auth uses an HttpOnly cookie named by `AUTH_COOKIE_NAME` (default `rm_session`).
- Keep `AUTH_SECRET` set to a stable value between restarts or existing sessions will be invalidated.
- Matches require job ingestion sources; see `services/api/README.md` for configuration.

## Linting and formatting

### Web
```
cd apps\web
npm run lint
npm run format
```

### API
```
cd services\api
.\.venv\Scripts\Activate.ps1
.\scripts\lint.ps1
.\scripts\format.ps1
```
