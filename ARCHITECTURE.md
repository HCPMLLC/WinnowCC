# ARCHITECTURE.md — ResumeMatch (Web + Mobile + Cloud)

## 0) Goals (what this architecture optimizes for)
- Beginner-friendly development and deployment
- Cloud-first compute (local machine stays responsive)
- Clear separation of concerns (web, mobile, API, workers)
- Async pipelines for resume parsing, job ingestion, matching, and tailoring
- Security-by-default for PII (resumes, profile data)

---

## 1) High-level system diagram (v1)

[Client Apps]
  - Web (Next.js)  --->  [API Gateway: FastAPI on Cloud Run]
  - Mobile (Expo)  --->         |
                                v
                          [Postgres: Cloud SQL]
                                |
                                v
                 [Async Workers: Cloud Run Jobs or Cloud Run Worker Service]
                     |        |        |
                     v        v        v
                Resume Parse  Matching  Tailoring
                     |
                     v
              [Object Storage: Google Cloud Storage]

[Job Sources]
  - Provider API/Feed  --->  [Ingestion Worker] ---> [Job table + embeddings]

---

## 2) Components (what each one does)

### 2.1 Web App (Next.js + TypeScript)
- Authentication UI
- Resume upload UI
- Profile editor UI
- Matches dashboard (filters + explanations)
- Tailored resume download list
- Minimal tracking UI

### 2.2 Mobile App (Expo + React Native + TypeScript)
- Login
- Matches list + job detail
- Trigger tailored resume generation
- Light profile preference editing
- Notifications/alerts (optional in v1)

### 2.3 API (FastAPI + Python)
Primary responsibilities:
- Auth token verification
- CRUD for Candidate Profile + Preferences
- Upload coordination (signed URLs to GCS)
- Match retrieval + filtering
- Tailor request submission (enqueue job)
- Tracking updates

### 2.4 Database (Postgres + pgvector)
Core tables:
- users
- resume_documents
- candidate_profiles (versioned)
- jobs (normalized + content hash)
- matches (match_score, readiness_score, reasons JSON)
- tailored_resumes (docx_url, change_log JSON)
- application_tracking

### 2.5 Cache/Queue (Redis)
- Queue: resume parsing, job ingestion, embedding generation, matching, tailoring
- Cache: job filters, match lists, rate limits

### 2.6 Workers (async pipelines)
All heavy operations are async:
- Parse resume -> CandidateProfile (version bump)
- Ingest jobs (scheduled)
- Generate embeddings (jobs + maybe profile)
- Compute matches (for user/profile_version)
- Generate tailored resume variants (grounded + ATS DOCX)

---

## 3) Cloud deployment on Google Cloud (recommended)

### 3.1 Services
- Cloud Run (API) — `resumematch-api`
- Cloud Run (worker service) OR Cloud Run Jobs — `resumematch-worker`
- Cloud SQL (Postgres) — `resumematch-db`
- Memorystore Redis (optional early) OR managed Redis later
- Cloud Storage bucket — `resumematch-resumes`
- Secret Manager — store API keys, DB URL, Stripe keys
- Cloud Scheduler — triggers ingestion jobs

### 3.2 Networking + Security
- API served via HTTPS
- Cloud SQL via private connection (recommended) or secure connector
- Object storage access via signed URLs (upload/download)
- Never store raw resume text in logs
- Principle of least privilege for service accounts

---

## 4) Local development architecture (Windows 11 Pro)

### 4.1 Local services via docker-compose
- Postgres
- Redis
- (Optional) MinIO for S3-like storage locally; but easiest: use GCS even in dev

### 4.2 Local run
- Web: `pnpm dev` (or npm)
- API: `uvicorn` in dev mode
- Worker: `python -m worker` or Celery/RQ worker

### 4.3 Switching between laptop and desktop
- GitHub = source of truth
- No local-only state
- `.env` never committed; `.env.example` is

---

## 5) Cost-conscious defaults (v1)
- Cloud Run min instances = 0 (scale to zero)
- Cloud SQL: smallest reasonable instance initially
- Store large objects in GCS (not DB)
- Batch compute embeddings (not per request)
- Cache match lists when possible

---

## 6) Observability + Reliability (v1)
- Error tracking: Sentry (web + api)
- Structured logging with PII redaction
- Health endpoints:
  - `/health` basic
  - `/ready` checks DB connection (optional)

---

## 7) Environments
- `dev`: local + test GCS bucket
- `staging`: cloud deployment for QA
- `prod`: production cloud deployment

Each has separate:
- DB
- GCS bucket
- secrets
- Stripe mode (test vs live)

---

## 8) Deployment pipeline (simple v1)
- GitHub repo
- On merge to `main`:
  - build + deploy web (Vercel or Cloud Run static hosting approach)
  - build + deploy API to Cloud Run
  - deploy worker service / jobs

---

## 9) Data handling rules (non-negotiable)
- Resume content is sensitive PII
- Encrypt at rest (cloud defaults) + TLS in transit
- Never log resume text
- Users can delete account and all stored artifacts
- Tailoring must be grounded in profile/resume facts
%%[ ProductName: Distiller ]%%
Aptos-Bold not found, using Courier.
%%[ Flushing: rest of job (to end-of-file) will be ignored ]%%
%%[ Warning: PostScript error. No PDF file produced. ] %%
