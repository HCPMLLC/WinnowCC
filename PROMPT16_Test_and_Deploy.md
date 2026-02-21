# PROMPT16_Test_and_Deploy.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and AGENTS.md before making changes.

## Purpose

Set up a production-grade testing suite and CI/CD pipeline, then deploy Winnow to Google Cloud Platform. This is the final step before launch — it takes the application from "works on my machine" to "runs reliably in the cloud with automated quality gates."

**Two halves, one prompt:**
- **Half A — Testing & CI:** Write pytest tests for critical API endpoints, add Playwright e2e tests for the web app, configure GitHub Actions to run tests + lint on every push/PR.
- **Half B — GCP Deployment:** Dockerize the API and worker, provision Cloud SQL + GCS + Redis, deploy to Cloud Run, wire secrets via Secret Manager, and schedule job ingestion via Cloud Scheduler.

---

## Triggers — When to Use This Prompt

- Setting up automated tests for the first time.
- Configuring GitHub Actions CI/CD pipeline.
- Deploying to GCP (Cloud Run, Cloud SQL, GCS).
- Adding Dockerfiles for API and worker.
- Setting up staging and production environments.

---

## What Already Exists (DO NOT recreate)

1. **Test infrastructure:** `services/api/tests/` directory exists. `services/api/scripts/test.ps1` runs pytest. `requirements-dev.txt` includes `pytest`.
2. **Lint scripts:** `services/api/scripts/lint.ps1` (ruff), `apps/web/package.json` has `lint` (next lint) and `format` (prettier).
3. **Health endpoints:** `GET /health` (no DB dependency) and `GET /ready` (checks DB) already implemented.
4. **Playwright:** Listed as a dev dependency in `apps/web/package.json` but not configured yet.
5. **Docker Compose:** `infra/docker-compose.yml` runs Postgres 16 + Redis 7 for local dev.
6. **.gitignore:** Already excludes `.env`, `node_modules`, `.venv`, `__pycache__`, `.next`.
7. **Auth:** HttpOnly cookie (`rm_session`) with JWT via `services/api/app/services/auth.py`.
8. **Queue/Worker:** RQ-based background jobs via `services/api/app/services/queue.py` and `services/api/app/worker.py`.

---

# HALF A — TESTING & CI

## A1: API Unit & Integration Tests (pytest)

**Directory:** `services/api/tests/`

Write tests for the critical API endpoints. Each test file tests one router. Use pytest fixtures for DB session, test client, and authenticated user.

### A1.1 Test fixtures — conftest.py

**File to create or update:** `services/api/tests/conftest.py`

```python
"""
Shared test fixtures for the Winnow API test suite.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test environment BEFORE importing app
os.environ["AUTH_SECRET"] = "test-secret-key"
os.environ["AUTH_COOKIE_NAME"] = "rm_session"
os.environ["ADMIN_TOKEN"] = "test-admin-token"

# Test database URL — use the same local Postgres but a test database
# Option A: Use the same DB (simpler for dev)
# Option B: Use a separate test DB (safer)
TEST_DB_URL = os.environ.get(
    "TEST_DB_URL",
    "postgresql://resumematch:resumematch@localhost:5432/resumematch_test"
)
os.environ["DB_URL"] = TEST_DB_URL

from app.main import app
from app.db.session import Base, get_db
from app.services.auth import create_jwt, hash_password


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine."""
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh DB session for each test, rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client with overridden DB dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user and return (user, jwt_token)."""
    from app.models.user import User
    user = User(
        email="test@winnow.dev",
        password_hash=hash_password("TestPass123!"),
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_jwt(user.id)
    return user, token


@pytest.fixture
def auth_client(client, test_user):
    """Test client with auth cookie set."""
    user, token = test_user
    client.cookies.set("rm_session", token)
    return client, user


@pytest.fixture
def admin_client(client, db_session):
    """Test client with admin user auth cookie."""
    from app.models.user import User
    admin = User(
        email="admin@winnow.dev",
        password_hash=hash_password("AdminPass123!"),
        is_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = create_jwt(admin.id)
    client.cookies.set("rm_session", token)
    return client, admin
```

### A1.2 Health & auth tests

**File to create:** `services/api/tests/test_health.py`

```python
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ready_checks_db(client):
    response = client.get("/ready")
    assert response.status_code == 200
    # Should be "ok" or "degraded"
    assert response.json()["status"] in ("ok", "degraded")
```

**File to create:** `services/api/tests/test_auth.py`

```python
def test_signup_creates_user(client):
    response = client.post("/api/auth/signup", json={
        "email": "newuser@winnow.dev",
        "password": "SecurePass123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@winnow.dev"
    # Check auth cookie was set
    assert "rm_session" in response.cookies

def test_signup_duplicate_email_fails(client):
    client.post("/api/auth/signup", json={"email": "dup@winnow.dev", "password": "Pass123!"})
    response = client.post("/api/auth/signup", json={"email": "dup@winnow.dev", "password": "Pass456!"})
    assert response.status_code in (400, 409)

def test_login_valid_credentials(client):
    client.post("/api/auth/signup", json={"email": "login@winnow.dev", "password": "Pass123!"})
    response = client.post("/api/auth/login", json={"email": "login@winnow.dev", "password": "Pass123!"})
    assert response.status_code == 200
    assert "rm_session" in response.cookies

def test_login_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "wrong@winnow.dev", "password": "Pass123!"})
    response = client.post("/api/auth/login", json={"email": "wrong@winnow.dev", "password": "WrongPass!"})
    assert response.status_code == 401

def test_me_returns_user_info(auth_client):
    client, user = auth_client
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == user.email

def test_me_unauthenticated_fails(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_logout_clears_cookie(auth_client):
    client, _ = auth_client
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
```

### A1.3 Profile tests

**File to create:** `services/api/tests/test_profile.py`

```python
def test_get_profile_empty(auth_client):
    client, user = auth_client
    response = client.get("/api/profile")
    assert response.status_code in (200, 404)

def test_update_profile(auth_client):
    client, user = auth_client
    # First create a profile by parsing a resume or via direct PUT
    response = client.put("/api/profile", json={
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "preferences": {
            "target_titles": ["Backend Developer"],
            "remote_ok": True,
            "salary_min": 100000,
            "salary_max": 150000
        }
    })
    assert response.status_code == 200

def test_profile_completeness(auth_client):
    client, user = auth_client
    response = client.get("/api/profile/completeness")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data or "completeness_score" in data
```

### A1.4 Matches tests

**File to create:** `services/api/tests/test_matches.py`

```python
def test_get_matches_empty(auth_client):
    client, user = auth_client
    response = client.get("/api/matches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_matches_unauthenticated(client):
    response = client.get("/api/matches")
    assert response.status_code == 401

def test_patch_match_status(auth_client, db_session):
    client, user = auth_client
    # Create a job and match in the test DB first
    # Then test status update
    # This test may need setup helpers — see conftest.py
    pass  # Implement after creating test data helpers

def test_patch_match_referred(auth_client, db_session):
    client, user = auth_client
    # Create a match, then toggle referral
    pass  # Implement after creating test data helpers
```

### A1.5 Dashboard metrics tests

**File to create:** `services/api/tests/test_dashboard.py`

```python
def test_dashboard_metrics_authenticated(auth_client):
    client, user = auth_client
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "profile_completeness_score" in data
    assert "qualified_jobs_count" in data

def test_dashboard_metrics_unauthenticated(client):
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 401
```

### A1.6 Admin endpoint tests

**File to create:** `services/api/tests/test_admin.py`

```python
def test_admin_ingest_requires_token(client):
    response = client.post("/api/admin/ingest")
    assert response.status_code in (401, 403, 422)

def test_admin_ingest_with_valid_token(admin_client):
    client, admin = admin_client
    response = client.post("/api/admin/ingest", params={"admin_token": "test-admin-token"})
    # Should accept the request (may queue background job)
    assert response.status_code in (200, 202)
```

### A1.7 Test data helpers

**File to create:** `services/api/tests/helpers.py`

```python
"""Helper functions to create test data."""
from datetime import datetime, timedelta

def create_test_job(db_session, **overrides):
    """Create a job record for testing."""
    from app.models.job import Job
    defaults = {
        "source": "test",
        "source_job_id": f"test-{datetime.utcnow().timestamp()}",
        "url": "https://example.com/job/1",
        "title": "Senior Python Developer",
        "company": "Test Corp",
        "description": "Build awesome things with Python and FastAPI.",
        "requirements": "5+ years Python, FastAPI, PostgreSQL",
        "location": "Remote",
        "remote_ok": True,
        "posted_at": datetime.utcnow() - timedelta(days=3),
    }
    defaults.update(overrides)
    job = Job(**defaults)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job

def create_test_match(db_session, user_id, job_id, **overrides):
    """Create a match record for testing."""
    from app.models.match import Match
    defaults = {
        "user_id": user_id,
        "job_id": job_id,
        "match_score": 75,
        "interview_readiness_score": 68,
        "offer_probability": 45,
        "reasons": {"matched_skills": ["Python", "FastAPI"]},
    }
    defaults.update(overrides)
    match = Match(**defaults)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    return match

def create_test_profile(db_session, user_id, **overrides):
    """Create a candidate profile for testing."""
    from app.models.candidate_profile import CandidateProfile
    defaults = {
        "user_id": user_id,
        "version": 1,
        "profile_json": {
            "basics": {"name": "Test User", "email": "test@winnow.dev"},
            "experience": [],
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferences": {"target_titles": ["Backend Developer"], "remote_ok": True},
        },
    }
    defaults.update(overrides)
    profile = CandidateProfile(**defaults)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile
```

### A1.8 Create the test database

Before running tests, you need a test database. Add this one-time setup:

```powershell
# In PowerShell, connect to local Postgres and create test DB:
docker exec -it infra-postgres-1 psql -U resumematch -c "CREATE DATABASE resumematch_test;"
```

Or add it to `infra/docker-compose.yml` as an initialization script.

### A1.9 Running tests locally

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1

# Ensure test DB exists
# Set TEST_DB_URL if different from default
$env:TEST_DB_URL="postgresql://resumematch:resumematch@localhost:5432/resumematch_test"

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

Add `pytest-cov` to `requirements-dev.txt`:
```
pytest-cov>=4.1.0
```

---

## A2: Playwright E2E Tests (Web)

**Directory to create:** `apps/web/e2e/`

### A2.1 Configure Playwright

```powershell
cd apps/web
npx playwright install
```

**File to create:** `apps/web/playwright.config.ts`

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'html',
  
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],

  // Start the Next.js dev server before tests
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 30000,
  },
});
```

### A2.2 E2E test files

**File to create:** `apps/web/e2e/landing.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test('landing page loads', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Winnow/i);
});

test('landing page has login link', async ({ page }) => {
  await page.goto('/');
  const loginLink = page.getByRole('link', { name: /log\s*in|sign\s*in/i });
  await expect(loginLink).toBeVisible();
});
```

**File to create:** `apps/web/e2e/auth.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test('signup flow works', async ({ page }) => {
  await page.goto('/login');
  // Fill signup form
  await page.getByLabel(/email/i).fill('e2e-test@winnow.dev');
  await page.getByLabel(/password/i).fill('E2eTestPass123!');
  // Click signup button
  await page.getByRole('button', { name: /sign\s*up|create\s*account/i }).click();
  // Should redirect to dashboard or onboarding
  await expect(page).toHaveURL(/dashboard|onboarding/);
});

test('login with invalid credentials shows error', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill('nonexistent@winnow.dev');
  await page.getByLabel(/password/i).fill('WrongPass!');
  await page.getByRole('button', { name: /log\s*in|sign\s*in/i }).click();
  // Should show error message
  await expect(page.getByText(/invalid|incorrect|failed/i)).toBeVisible();
});
```

**File to create:** `apps/web/e2e/dashboard.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test('dashboard requires authentication', async ({ page }) => {
  await page.goto('/dashboard');
  // Should redirect to login
  await expect(page).toHaveURL(/login/);
});
```

### A2.3 Add Playwright scripts to package.json

**File to modify:** `apps/web/package.json`

Add to `"scripts"`:
```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

### A2.4 Running e2e tests locally

```powershell
# Ensure API + web are running (use start-dev.ps1 or manual startup)
cd apps/web
npx playwright test
```

---

## A3: GitHub Actions CI Pipeline

**File to create:** `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "20"

jobs:
  # ─── API: Lint + Test ───────────────────────────
  api-lint:
    name: API Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          cd services/api
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Ruff check
        run: |
          cd services/api
          python -m ruff check .
      - name: Ruff format check
        run: |
          cd services/api
          python -m ruff format --check .

  api-test:
    name: API Tests
    runs-on: ubuntu-latest
    needs: api-lint
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: resumematch
          POSTGRES_PASSWORD: resumematch
          POSTGRES_DB: resumematch_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DB_URL: postgresql://resumematch:resumematch@localhost:5432/resumematch_test
      TEST_DB_URL: postgresql://resumematch:resumematch@localhost:5432/resumematch_test
      REDIS_URL: redis://localhost:6379/0
      AUTH_SECRET: ci-test-secret
      AUTH_COOKIE_NAME: rm_session
      ADMIN_TOKEN: ci-admin-token
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          cd services/api
          pip install -r requirements.txt -r requirements-dev.txt
      - name: Run Alembic migrations
        run: |
          cd services/api
          alembic upgrade head
      - name: Run tests with coverage
        run: |
          cd services/api
          python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=50
      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: api-coverage
          path: services/api/htmlcov/

  # ─── Web: Lint + Build ─────────────────────────
  web-lint:
    name: Web Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Install dependencies
        run: |
          cd apps/web
          npm ci
      - name: Next.js lint
        run: |
          cd apps/web
          npm run lint

  web-build:
    name: Web Build
    runs-on: ubuntu-latest
    needs: web-lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Install dependencies
        run: |
          cd apps/web
          npm ci
      - name: Build Next.js
        env:
          NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
        run: |
          cd apps/web
          npm run build

  # ─── E2E Tests (on main only) ──────────────────
  e2e-test:
    name: E2E Tests
    runs-on: ubuntu-latest
    needs: [api-test, web-build]
    if: github.ref == 'refs/heads/main'
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: resumematch
          POSTGRES_PASSWORD: resumematch
          POSTGRES_DB: resumematch_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    env:
      DB_URL: postgresql://resumematch:resumematch@localhost:5432/resumematch_test
      REDIS_URL: redis://localhost:6379/0
      AUTH_SECRET: ci-test-secret
      AUTH_COOKIE_NAME: rm_session
      ADMIN_TOKEN: ci-admin-token
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
      - name: Install API dependencies
        run: |
          cd services/api
          pip install -r requirements.txt
      - name: Run migrations
        run: |
          cd services/api
          alembic upgrade head
      - name: Start API
        run: |
          cd services/api
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      - name: Install web dependencies
        run: |
          cd apps/web
          npm ci
      - name: Install Playwright browsers
        run: |
          cd apps/web
          npx playwright install --with-deps chromium
      - name: Build and start web
        run: |
          cd apps/web
          npm run build
          npm start &
          sleep 5
      - name: Run Playwright tests
        run: |
          cd apps/web
          PLAYWRIGHT_BASE_URL=http://localhost:3000 npx playwright test
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: apps/web/playwright-report/
```

---

# HALF B — GCP DEPLOYMENT

## B1: Dockerize the API

**File to create:** `services/api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg2 and python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for local file storage (uploads, generated docs)
RUN mkdir -p /app/data/uploads /app/generated

# Expose port
EXPOSE 8080

# Cloud Run uses PORT env var (default 8080)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**File to create:** `services/api/.dockerignore`

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
.env.*
!.env.example
data/uploads/
tests/
scripts/
*.md
```

---

## B2: Dockerize the Worker

**File to create:** `services/api/Dockerfile.worker`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/uploads /app/generated

# Start the RQ worker
CMD ["python", "-m", "app.worker"]
```

---

## B3: Dockerize the Web App

**File to create:** `apps/web/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-time env vars
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

RUN npm run build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy built assets
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

**Important:** For the standalone output to work, add to `apps/web/next.config.js` (or `.mjs`):

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // ... existing config
};

module.exports = nextConfig;
```

**File to create:** `apps/web/.dockerignore`

```
node_modules/
.next/
.env
.env.*
!.env.example
e2e/
playwright-report/
```

---

## B4: GCP Project Setup

These are **one-time setup commands** run from your local machine using the `gcloud` CLI. If you don't have `gcloud` installed, install it from https://cloud.google.com/sdk/docs/install.

### B4.1 Prerequisites

```powershell
# Install gcloud CLI (if not already)
# https://cloud.google.com/sdk/docs/install

# Login and set project
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  redis.googleapis.com
```

Replace `YOUR_GCP_PROJECT_ID` with your actual GCP project ID throughout this document.

### B4.2 Set region

```powershell
# Use a region close to your users
$REGION = "us-central1"
gcloud config set run/region $REGION
```

---

## B5: Provision Cloud SQL (Postgres)

```powershell
# Create Cloud SQL instance (smallest tier for cost savings)
gcloud sql instances create winnow-db `
  --database-version=POSTGRES_16 `
  --tier=db-f1-micro `
  --region=us-central1 `
  --storage-size=10GB `
  --storage-auto-increase `
  --availability-type=zonal `
  --database-flags=cloudsql.iam_authentication=on

# Create the database
gcloud sql databases create winnow --instance=winnow-db

# Create a user
gcloud sql users create winnow-user `
  --instance=winnow-db `
  --password=YOUR_SECURE_DB_PASSWORD
```

**Enable pgvector on Cloud SQL:**
Cloud SQL for PostgreSQL supports pgvector natively. After connecting, run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Or include it in your Alembic migrations (which you already have from PROMPT15).

**Get the connection name** (needed for Cloud Run):
```powershell
gcloud sql instances describe winnow-db --format="value(connectionName)"
# Output: YOUR_PROJECT:us-central1:winnow-db
```

---

## B6: Provision Google Cloud Storage (GCS)

```powershell
# Create bucket for resume uploads and generated documents
gcloud storage buckets create gs://winnow-resumes-YOUR_PROJECT `
  --location=us-central1 `
  --uniform-bucket-level-access

# Set lifecycle rule: delete objects after 365 days (optional, for cost)
# Or manage via console
```

---

## B7: Provision Redis (Memorystore)

For MVP, you can use a small Memorystore Redis instance. Alternatively, for cost savings, run Redis as a sidecar container on Cloud Run (not recommended for production but works for MVP).

**Option A: Memorystore (recommended for production)**
```powershell
gcloud redis instances create winnow-redis `
  --size=1 `
  --region=us-central1 `
  --redis-version=redis_7_0 `
  --tier=basic
```

**Option B: Redis Cloud free tier**
Use a free Redis Cloud instance from https://redis.com/try-free/ (up to 30MB, sufficient for MVP RQ queues).

---

## B8: Secret Manager

Store all secrets in GCP Secret Manager instead of environment variables:

```powershell
# Database URL
echo -n "postgresql+asyncpg://winnow-user:YOUR_SECURE_DB_PASSWORD@/winnow?host=/cloudsql/YOUR_PROJECT:us-central1:winnow-db" | `
  gcloud secrets create DB_URL --data-file=-

# Auth secret
echo -n "YOUR_PRODUCTION_AUTH_SECRET_32_CHARS_MIN" | `
  gcloud secrets create AUTH_SECRET --data-file=-

# Admin token
echo -n "YOUR_PRODUCTION_ADMIN_TOKEN" | `
  gcloud secrets create ADMIN_TOKEN --data-file=-

# Redis URL (from Memorystore or Redis Cloud)
echo -n "redis://REDIS_HOST:6379/0" | `
  gcloud secrets create REDIS_URL --data-file=-

# Anthropic API key (for tailoring and embeddings)
echo -n "sk-ant-..." | `
  gcloud secrets create ANTHROPIC_API_KEY --data-file=-

# Voyage API key (if using Voyage for embeddings)
echo -n "pa-..." | `
  gcloud secrets create VOYAGE_API_KEY --data-file=-
```

---

## B9: Artifact Registry (Container Registry)

```powershell
# Create a Docker repository in Artifact Registry
gcloud artifacts repositories create winnow `
  --repository-format=docker `
  --location=us-central1 `
  --description="Winnow container images"
```

---

## B10: Build and Push Container Images

```powershell
# Authenticate Docker with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push API image
cd services/api
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest

# Build and push Worker image
docker build -f Dockerfile.worker -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/worker:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/worker:latest

# Build and push Web image
cd ../../apps/web
docker build `
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com `
  -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest
```

---

## B11: Deploy to Cloud Run

### B11.1 Deploy the API

```powershell
gcloud run deploy winnow-api `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest `
  --region=us-central1 `
  --platform=managed `
  --allow-unauthenticated `
  --port=8080 `
  --memory=512Mi `
  --cpu=1 `
  --min-instances=0 `
  --max-instances=5 `
  --timeout=300 `
  --add-cloudsql-instances=YOUR_PROJECT:us-central1:winnow-db `
  --set-secrets="DB_URL=DB_URL:latest,AUTH_SECRET=AUTH_SECRET:latest,ADMIN_TOKEN=ADMIN_TOKEN:latest,REDIS_URL=REDIS_URL:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" `
  --set-env-vars="AUTH_COOKIE_NAME=rm_session,AUTH_TOKEN_EXPIRES_DAYS=7,GCS_BUCKET=winnow-resumes-YOUR_PROJECT,EMBEDDING_PROVIDER=sentence_transformers,EMBEDDING_DIMENSION=384"
```

### B11.2 Deploy the Worker

```powershell
gcloud run deploy winnow-worker `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/worker:latest `
  --region=us-central1 `
  --platform=managed `
  --no-allow-unauthenticated `
  --memory=1Gi `
  --cpu=1 `
  --min-instances=0 `
  --max-instances=3 `
  --timeout=900 `
  --add-cloudsql-instances=YOUR_PROJECT:us-central1:winnow-db `
  --set-secrets="DB_URL=DB_URL:latest,REDIS_URL=REDIS_URL:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" `
  --set-env-vars="EMBEDDING_PROVIDER=sentence_transformers,EMBEDDING_DIMENSION=384,GCS_BUCKET=winnow-resumes-YOUR_PROJECT"
```

### B11.3 Deploy the Web App

```powershell
gcloud run deploy winnow-web `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest `
  --region=us-central1 `
  --platform=managed `
  --allow-unauthenticated `
  --port=3000 `
  --memory=256Mi `
  --cpu=1 `
  --min-instances=0 `
  --max-instances=5
```

### B11.4 Get the service URLs

```powershell
gcloud run services describe winnow-api --region=us-central1 --format="value(status.url)"
gcloud run services describe winnow-web --region=us-central1 --format="value(status.url)"
```

---

## B12: Run Migrations on Cloud SQL

Connect to Cloud SQL and run Alembic migrations:

```powershell
# Option A: Use Cloud SQL Proxy
gcloud sql connect winnow-db --user=winnow-user --database=winnow

# Then in the SQL shell:
# Run CREATE EXTENSION IF NOT EXISTS vector; (if pgvector migration hasn't run)

# Option B: Use Cloud Run Jobs for migration
gcloud run jobs create winnow-migrate `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/api:latest `
  --region=us-central1 `
  --add-cloudsql-instances=YOUR_PROJECT:us-central1:winnow-db `
  --set-secrets="DB_URL=DB_URL:latest" `
  --command="alembic" `
  --args="upgrade,head"

gcloud run jobs execute winnow-migrate --region=us-central1
```

---

## B13: Cloud Scheduler (Job Ingestion Cron)

Schedule the job ingestion to run periodically:

```powershell
# Get the API service URL
$API_URL = gcloud run services describe winnow-api --region=us-central1 --format="value(status.url)"

# Create a Cloud Scheduler job that triggers ingestion every 6 hours
gcloud scheduler jobs create http winnow-ingest-jobs `
  --schedule="0 */6 * * *" `
  --uri="$API_URL/api/admin/ingest?admin_token=YOUR_PRODUCTION_ADMIN_TOKEN" `
  --http-method=POST `
  --location=us-central1 `
  --time-zone="America/Chicago" `
  --attempt-deadline=300s
```

---

## B14: CORS Update for Production

**File to modify:** `services/api/app/main.py`

Update CORS to include the production web URL:

```python
import os

ALLOWED_ORIGINS = [
    "http://localhost:3000",     # Local dev
    "http://127.0.0.1:3000",    # Local dev alt
]

# Add production URL from environment
PROD_WEB_URL = os.environ.get("CORS_ORIGIN")
if PROD_WEB_URL:
    ALLOWED_ORIGINS.append(PROD_WEB_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Add `CORS_ORIGIN` to the Cloud Run deployment:
```powershell
gcloud run services update winnow-api `
  --set-env-vars="CORS_ORIGIN=https://winnow-web-XXXXX-uc.a.run.app"
```

---

## B15: Auth Cookie Configuration for Production

In production, auth cookies must be `Secure=True` and `SameSite=None` (for cross-origin Cloud Run URLs) or `SameSite=Lax` (if using custom domain).

**File to modify:** `services/api/app/services/auth.py`

Ensure the cookie settings adapt to environment:

```python
import os

IS_PRODUCTION = os.environ.get("ENV", "dev") != "dev"

def set_auth_cookie(response, token: str):
    response.set_cookie(
        key=os.environ.get("AUTH_COOKIE_NAME", "rm_session"),
        value=token,
        httponly=True,
        secure=IS_PRODUCTION,          # True in production (HTTPS)
        samesite="none" if IS_PRODUCTION else "lax",  # "none" for cross-origin Cloud Run
        path="/",
        max_age=60 * 60 * 24 * int(os.environ.get("AUTH_TOKEN_EXPIRES_DAYS", "7")),
    )
```

Add `ENV=production` to the Cloud Run API deployment env vars.

---

## B16: GitHub Actions — Deploy on Merge to Main

**File to create:** `.github/workflows/deploy.yml`

```yaml
name: Deploy to GCP

on:
  push:
    branches: [main]

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  API_IMAGE: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/winnow/api
  WORKER_IMAGE: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/winnow/worker
  WEB_IMAGE: us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/winnow/web

jobs:
  deploy-api:
    name: Deploy API
    runs-on: ubuntu-latest
    needs: []  # Add "api-test" from ci.yml if using reusable workflows
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - uses: google-github-actions/setup-gcloud@v2
      
      - name: Configure Docker
        run: gcloud auth configure-docker us-central1-docker.pkg.dev
      
      - name: Build and push API image
        run: |
          cd services/api
          docker build -t ${{ env.API_IMAGE }}:${{ github.sha }} -t ${{ env.API_IMAGE }}:latest .
          docker push ${{ env.API_IMAGE }}:${{ github.sha }}
          docker push ${{ env.API_IMAGE }}:latest
      
      - name: Deploy API to Cloud Run
        run: |
          gcloud run deploy winnow-api \
            --image=${{ env.API_IMAGE }}:${{ github.sha }} \
            --region=${{ env.REGION }} \
            --platform=managed

      - name: Run migrations
        run: |
          gcloud run jobs execute winnow-migrate --region=${{ env.REGION }} --wait

  deploy-worker:
    name: Deploy Worker
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - uses: google-github-actions/setup-gcloud@v2
      
      - name: Configure Docker
        run: gcloud auth configure-docker us-central1-docker.pkg.dev
      
      - name: Build and push Worker image
        run: |
          cd services/api
          docker build -f Dockerfile.worker -t ${{ env.WORKER_IMAGE }}:${{ github.sha }} -t ${{ env.WORKER_IMAGE }}:latest .
          docker push ${{ env.WORKER_IMAGE }}:${{ github.sha }}
          docker push ${{ env.WORKER_IMAGE }}:latest
      
      - name: Deploy Worker to Cloud Run
        run: |
          gcloud run deploy winnow-worker \
            --image=${{ env.WORKER_IMAGE }}:${{ github.sha }} \
            --region=${{ env.REGION }} \
            --platform=managed

  deploy-web:
    name: Deploy Web
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      
      - id: auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - uses: google-github-actions/setup-gcloud@v2
      
      - name: Configure Docker
        run: gcloud auth configure-docker us-central1-docker.pkg.dev
      
      - name: Build and push Web image
        run: |
          cd apps/web
          docker build \
            --build-arg NEXT_PUBLIC_API_BASE_URL=${{ secrets.API_URL }} \
            -t ${{ env.WEB_IMAGE }}:${{ github.sha }} \
            -t ${{ env.WEB_IMAGE }}:latest .
          docker push ${{ env.WEB_IMAGE }}:${{ github.sha }}
          docker push ${{ env.WEB_IMAGE }}:latest
      
      - name: Deploy Web to Cloud Run
        run: |
          gcloud run deploy winnow-web \
            --image=${{ env.WEB_IMAGE }}:${{ github.sha }} \
            --region=${{ env.REGION }} \
            --platform=managed
```

### B16.1 GitHub Secrets to configure

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret Name | Value |
|-------------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | JSON key of a GCP service account with Cloud Run, Artifact Registry, Cloud SQL, and Secret Manager permissions |
| `API_URL` | The Cloud Run URL for winnow-api (e.g., `https://winnow-api-xxxxx-uc.a.run.app`) |

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Test fixtures | `services/api/tests/conftest.py` | CREATE or UPDATE |
| Test helpers | `services/api/tests/helpers.py` | CREATE |
| Health tests | `services/api/tests/test_health.py` | CREATE |
| Auth tests | `services/api/tests/test_auth.py` | CREATE |
| Profile tests | `services/api/tests/test_profile.py` | CREATE |
| Matches tests | `services/api/tests/test_matches.py` | CREATE |
| Dashboard tests | `services/api/tests/test_dashboard.py` | CREATE |
| Admin tests | `services/api/tests/test_admin.py` | CREATE |
| Playwright config | `apps/web/playwright.config.ts` | CREATE |
| E2E: landing | `apps/web/e2e/landing.spec.ts` | CREATE |
| E2E: auth | `apps/web/e2e/auth.spec.ts` | CREATE |
| E2E: dashboard | `apps/web/e2e/dashboard.spec.ts` | CREATE |
| CI workflow | `.github/workflows/ci.yml` | CREATE |
| Deploy workflow | `.github/workflows/deploy.yml` | CREATE |
| API Dockerfile | `services/api/Dockerfile` | CREATE |
| Worker Dockerfile | `services/api/Dockerfile.worker` | CREATE |
| Web Dockerfile | `apps/web/Dockerfile` | CREATE |
| API .dockerignore | `services/api/.dockerignore` | CREATE |
| Web .dockerignore | `apps/web/.dockerignore` | CREATE |
| Next.js config (standalone) | `apps/web/next.config.js` | MODIFY — add `output: 'standalone'` |
| CORS (production) | `services/api/app/main.py` | MODIFY — add CORS_ORIGIN env var |
| Auth cookies (production) | `services/api/app/services/auth.py` | MODIFY — Secure + SameSite for prod |
| Dev dependencies | `services/api/requirements-dev.txt` | MODIFY — add pytest-cov |
| Web package.json | `apps/web/package.json` | MODIFY — add e2e scripts |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Test Infrastructure (Steps 1–5)

1. **Step 1:** Add `pytest-cov` to `services/api/requirements-dev.txt`. Install it.
2. **Step 2:** Create the test database:
   ```powershell
   docker exec -it infra-postgres-1 psql -U resumematch -c "CREATE DATABASE resumematch_test;"
   ```
3. **Step 3:** Create or update `services/api/tests/conftest.py` with all fixtures.
4. **Step 4:** Create `services/api/tests/helpers.py` with test data helpers.
5. **Step 5:** Create all test files: `test_health.py`, `test_auth.py`, `test_profile.py`, `test_matches.py`, `test_dashboard.py`, `test_admin.py`.

### Phase 2: Run Tests Locally (Step 6)

6. **Step 6:** Run tests and fix any failures:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   $env:TEST_DB_URL="postgresql://resumematch:resumematch@localhost:5432/resumematch_test"
   python -m pytest tests/ -v --cov=app
   ```

### Phase 3: Playwright E2E (Steps 7–9)

7. **Step 7:** Create `apps/web/playwright.config.ts`.
8. **Step 8:** Create e2e test files in `apps/web/e2e/`.
9. **Step 9:** Run e2e tests:
   ```powershell
   # Ensure start-dev.ps1 is running (API + web)
   cd apps/web
   npx playwright install
   npx playwright test
   ```

### Phase 4: GitHub Actions CI (Step 10)

10. **Step 10:** Create `.github/workflows/ci.yml`. Push to GitHub. Verify the workflow runs on your next push.

### Phase 5: Dockerfiles (Steps 11–14)

11. **Step 11:** Create `services/api/Dockerfile` and `services/api/.dockerignore`.
12. **Step 12:** Create `services/api/Dockerfile.worker`.
13. **Step 13:** Create `apps/web/Dockerfile` and `apps/web/.dockerignore`. Add `output: 'standalone'` to `next.config.js`.
14. **Step 14:** Test Docker builds locally:
    ```powershell
    cd services/api
    docker build -t winnow-api:local .
    docker build -f Dockerfile.worker -t winnow-worker:local .
    cd ../../apps/web
    docker build --build-arg NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 -t winnow-web:local .
    ```

### Phase 6: GCP Setup (Steps 15–21)

15. **Step 15:** Install `gcloud` CLI. Authenticate and set project.
16. **Step 16:** Enable GCP APIs (Cloud Run, Cloud SQL, etc.).
17. **Step 17:** Create Cloud SQL instance + database + user (B5).
18. **Step 18:** Create GCS bucket (B6).
19. **Step 19:** Set up Redis — Memorystore or Redis Cloud free tier (B7).
20. **Step 20:** Store secrets in Secret Manager (B8).
21. **Step 21:** Create Artifact Registry repository (B9).

### Phase 7: Deploy (Steps 22–27)

22. **Step 22:** Build and push container images to Artifact Registry (B10).
23. **Step 23:** Deploy API to Cloud Run (B11.1).
24. **Step 24:** Deploy Worker to Cloud Run (B11.2).
25. **Step 25:** Deploy Web to Cloud Run (B11.3).
26. **Step 26:** Run migrations on Cloud SQL (B12).
27. **Step 27:** Create Cloud Scheduler job for ingestion cron (B13).

### Phase 8: Production Configuration (Steps 28–30)

28. **Step 28:** Update CORS for production API URL (B14).
29. **Step 29:** Update auth cookie settings for production (B15).
30. **Step 30:** Create `.github/workflows/deploy.yml` and configure GitHub secrets (B16).

### Phase 9: Verify (Step 31)

31. **Step 31:** End-to-end verification:
    - [ ] Visit the web Cloud Run URL — landing page loads
    - [ ] Sign up a new account — auth works
    - [ ] Upload a resume — file stored in GCS, parsing works
    - [ ] View matches — jobs are matched and scored
    - [ ] Check Cloud Scheduler — ingestion runs on schedule
    - [ ] Push a commit to `main` — CI runs tests, deploy workflow deploys
    - [ ] `/health` returns `{"status": "ok"}`
    - [ ] `/ready` returns `{"status": "ok"}` (DB connected)

---

## Cost Estimate (v1 MVP)

Per ARCHITECTURE §5, cost-conscious defaults:

| Service | Tier | Estimated Monthly Cost |
|---------|------|----------------------|
| Cloud Run (API) | min=0, max=5, 512Mi | $0–$15 (scale to zero) |
| Cloud Run (Worker) | min=0, max=3, 1Gi | $0–$10 |
| Cloud Run (Web) | min=0, max=5, 256Mi | $0–$10 |
| Cloud SQL (Postgres) | db-f1-micro, 10GB | ~$8 |
| Redis (Cloud free tier) | 30MB | $0 |
| GCS | Pay per use | <$1 |
| Secret Manager | 6 secrets | <$1 |
| Cloud Scheduler | 1 job | $0 (free tier) |
| Artifact Registry | Storage | <$1 |
| **Total** | | **~$10–$45/month** |

---

## Non-Goals (Do NOT implement in this prompt)

- Custom domain setup (use Cloud Run default URLs for MVP)
- CDN / Cloud Armor / WAF (future)
- Staging environment (deploy to prod first, add staging later)
- Auto-scaling tuning (default Cloud Run settings are fine for MVP)
- Database connection pooling with PgBouncer (Cloud SQL handles this)
- Log aggregation beyond Cloud Run default logging
- Uptime monitoring / alerting (use GCP built-in for now)

---

## Summary Checklist

### Testing
- [ ] Test fixtures: conftest.py with DB session, client, auth fixtures
- [ ] Test helpers: create_test_job, create_test_match, create_test_profile
- [ ] API tests: health, auth (signup/login/logout/me), profile, matches, dashboard, admin
- [ ] Tests pass locally with `pytest tests/ -v`
- [ ] Coverage ≥ 50% on critical paths
- [ ] Playwright configured with e2e tests for landing, auth, dashboard
- [ ] E2E tests pass locally

### CI/CD
- [ ] `.github/workflows/ci.yml`: lint + test on every push/PR
- [ ] `.github/workflows/deploy.yml`: build + deploy on merge to main
- [ ] GitHub secrets configured: GCP_PROJECT_ID, GCP_SA_KEY, API_URL

### Dockerfiles
- [ ] `services/api/Dockerfile` (API)
- [ ] `services/api/Dockerfile.worker` (Worker)
- [ ] `apps/web/Dockerfile` (Web with standalone output)
- [ ] All three build successfully locally

### GCP Infrastructure
- [ ] Cloud SQL instance + database + user created
- [ ] pgvector extension enabled on Cloud SQL
- [ ] GCS bucket created
- [ ] Redis provisioned (Memorystore or Cloud free tier)
- [ ] Secrets stored in Secret Manager
- [ ] Artifact Registry repository created

### Deployment
- [ ] API deployed to Cloud Run (winnow-api)
- [ ] Worker deployed to Cloud Run (winnow-worker)
- [ ] Web deployed to Cloud Run (winnow-web)
- [ ] Migrations run on Cloud SQL
- [ ] Cloud Scheduler job ingestion cron created
- [ ] CORS updated for production
- [ ] Auth cookies secure in production
- [ ] Health + ready endpoints respond correctly

Return code changes only.
