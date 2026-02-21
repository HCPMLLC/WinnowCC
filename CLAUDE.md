# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Winnow is a three-sided hiring platform (candidates, employers, recruiters) that parses resumes, ingests jobs from multiple sources, computes match scores with Interview Probability Scores (IPS), generates tailored resumes and cover letters, provides career intelligence insights, and includes an AI concierge (Sieve). Tiered subscription billing (free/starter/pro) gates feature access per segment. It's a monorepo with a Next.js frontend, FastAPI backend, Expo mobile app, Chrome extension, and async job workers.

## Repository Structure

```
apps/web/              Next.js 14 frontend (TypeScript, React 18, Tailwind CSS)
apps/mobile/           Expo React Native app (iOS + Android)
apps/chrome-extension/ Chrome extension for LinkedIn sourcing
services/api/          FastAPI backend (Python 3.11, SQLAlchemy, Alembic)
infra/                 Docker Compose (Postgres 16, Redis 7)
```

## Build and Development Commands

### Quick Start (Windows PowerShell)
```powershell
.\start-dev.ps1     # Starts infra, API, worker, and web in separate windows
```

### Manual Startup
```powershell
# Infrastructure
cd infra && docker compose up -d

# API (in services/api with venv activated)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker (separate terminal)
python -m app.worker

# Web (in apps/web)
npm run dev
```

### Testing and Linting
```powershell
# API
cd services/api
.\scripts\test.ps1      # pytest -q
.\scripts\lint.ps1      # ruff check .
.\scripts\format.ps1    # ruff format .

# Web
cd apps/web
npm run lint
npm run format
```

### Database Migrations
```powershell
cd services/api
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Architecture

### Request Flow
1. Web/mobile frontend calls API at `NEXT_PUBLIC_API_BASE_URL` (default: http://127.0.0.1:8000)
2. API authenticates via HttpOnly cookie (`rm_session`) containing JWT (supports OAuth via Auth0)
3. Billing middleware checks plan tier and enforces feature limits (daily counters, boolean gates)
4. Heavy operations (resume parsing, matching, tailoring) are enqueued to RQ (Redis Queue)
5. Worker processes jobs asynchronously and stores results in Postgres
6. Stripe webhooks update subscription status via `/api/webhooks/stripe`

### Key Backend Services (services/api/app/services/)
- `auth.py` - JWT/cookie authentication (includes OAuth via Auth0)
- `billing.py` - Tiered pricing enforcement, plan limits, daily usage tracking
- `profile_parser.py` - Resume to profile extraction
- `matching.py` - Job match scoring
- `tailor.py` - Tailored resume generation
- `cover_letter_generator.py` - Per-job cover letter generation
- `career_intelligence.py` - Career trajectory, salary intelligence, market position
- `sieve_chat.py` - AI concierge conversational assistant
- `embedding.py` - pgvector semantic search (sentence-transformers or Voyage)
- `job_ingestion.py` / `job_pipeline.py` - Multi-source job ingestion pipeline
- `job_fraud_detector.py` - 14-signal job posting fraud detection
- `trust_gate.py` - Consent/compliance validation
- `trust_scoring.py` - Candidate trust scoring
- `data_export.py` - GDPR-compliant data export (ZIP)
- `account_deletion.py` / `cascade_delete.py` - Full account deletion with cascades
- `distribution.py` - Multi-board job distribution
- `employer_analytics.py` / `employer_billing.py` - Employer-side features
- `queue.py` - RQ job queue wrapper

### Key API Routers (services/api/app/routers/)
40 routers registered in `main.py`. Key ones:
- `auth.py` - Login, signup, logout, OAuth, password reset
- `billing.py` - Subscription plans, Stripe checkout, billing status with usage/limits
- `account.py` - Data export (tier-gated), account deletion
- `resume.py` - Upload and parsing coordination
- `profile.py` - Candidate profile CRUD
- `matches.py` - Job matches with tier-based visibility, IPS filtering, semantic search
- `tailor.py` - Tailored resume requests (tier-limited)
- `candidate_insights.py` - Career intelligence endpoints (Pro only): market position, salary, trajectory
- `sieve.py` - AI concierge chat (daily message limit by tier)
- `dashboard.py` - Dashboard data and recommendations
- `jobs.py` - Job listing and management
- `employer.py` - Employer workspace, job posting, candidate management
- `recruiter.py` - Recruiter registration and workspace
- `distribution.py` - Multi-board job distribution
- `trust.py`, `admin_trust.py` - Trust/consent management
- `onboarding.py` - Candidate onboarding flow
- `references.py` - Professional references

### Database Models (services/api/app/models/)
29 model files, 50+ model classes. Core tables:
- **Users & Auth**: users (with OAuth fields, email verification)
- **Candidates**: candidates (plan_tier: free/starter/pro), candidate_profiles (versioned), candidate_trust
- **Jobs**: jobs, job_parsed_details, job_runs, job_forms
- **Matching**: matches (with IPS fields), tailored_resumes
- **Billing**: daily_usage_counters (per-day tier enforcement), usage_counters
- **AI Features**: sieve_conversations, career_intelligence tables
- **Employer**: employer_profiles, employer_jobs, employer_team_members, employer_compliance_logs, employer_job_candidates
- **Recruiter**: recruiter_profiles, recruiter_team_members
- **Distribution**: job_distributions, distribution_events, board_connections
- **Documents**: resume_documents, parsed_resume_documents, merged_packets
- **Trust**: trust_audit_log, candidate_trust

## Environment Variables

### API (services/api/.env) — see `.env.example` for full list
```
# Database & Cache
DB_URL=postgresql://resumematch:resumematch@localhost:5432/resumematch
REDIS_URL=redis://localhost:6379/0

# Auth
AUTH_SECRET=dev-secret-change-me    # Keep stable for session persistence
AUTH_COOKIE_NAME=rm_session
AUTH_TOKEN_EXPIRES_DAYS=7
AUTH0_DOMAIN=...                    # OAuth (optional)
AUTH0_CLIENT_ID=...
AUTH0_CLIENT_SECRET=...

# AI
ANTHROPIC_API_KEY=...               # Used by LLM services

# Job Sources
JOB_SOURCES=remotive,themuse,...    # See services/api/README.md for full list
ADMIN_TOKEN=dev-admin-token

# Stripe Billing (per-segment: candidate, employer, recruiter)
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_CANDIDATE_STARTER_MO=...
STRIPE_PRICE_CANDIDATE_PRO_MO=...
# ... (see .env.example for all Stripe price IDs)

# Email
RESEND_API_KEY=...
RESEND_FROM_EMAIL=...

# Embeddings
EMBEDDING_PROVIDER=sentence-transformers  # or "voyage"
EMBEDDING_DIMENSION=384

# Error Tracking
SENTRY_DSN=...
FRONTEND_URL=http://localhost:3000
```

### Web (apps/web/.env.local)
```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_ADMIN_TOKEN=dev-admin-token
```

## Three-Segment Pricing Architecture

Winnow serves three user segments with independent pricing and feature gates:

### Candidates (free / starter $9/mo / pro $29/mo)
- **Tiered enforcement** via `CANDIDATE_PLAN_LIMITS` in `services/api/app/services/billing.py`
- Limits: `matches_visible`, `tailor_requests`, `cover_letters`, `sieve_messages_per_day`, `semantic_searches_per_day`
- Boolean gates: `data_export`, `career_intelligence`
- IPS detail levels: `score_only` (free) → `breakdown` (starter) → `full_coaching` (pro)
- Daily limits tracked via `DailyUsageCounter` model (PostgreSQL upsert + SQLite fallback for tests)
- Helpers: `get_tier_limit()`, `check_feature_access()`, `check_daily_limit()`, `increment_daily_counter()`

### Employers (starter $49/mo / pro $149/mo)
- Job posting, distribution, candidate management, compliance reporting

### Recruiters (solo $79/mo / team $149/mo / agency $299/mo)
- CRM pipeline, multi-channel outreach, client management, migration toolkit

### Frontend Audience Toggle
- Landing page (`apps/web/app/page.tsx`) has seeker/employer/recruiter audience toggle
- Each audience sees different hero, features, pricing, and competitive comparison
- Competitive comparisons: candidates vs job boards, employers vs ATS (Greenhouse/Lever/Workable/BambooHR), recruiters vs CRMs (Bullhorn/Recruit CRM/CATSOne/Zoho)

## Code Style

- **Python**: Ruff formatter/linter, 88 char line length, snake_case modules
- **TypeScript**: Prettier + ESLint (next lint), lowercase route folders

## Related Documentation

- `AGENTS.md` - Repository guidelines (structure, naming, testing, commits)
- `ARCHITECTURE.md` - System design, cloud deployment details
- `services/api/README.md` - Job ingestion source configuration

## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately – don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes – don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests – then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **✶✶Plan First✶✶**: Write plan to `tasks/todo.md` with checkable items
2. **✶✶Verify Plan✶✶**: Check in before starting implementation
3. **✶✶Track Progress✶✶**: Mark items complete as you go
4. **✶✶Explain Changes✶✶**: High-level summary at each step
5. **✶✶Document Results✶✶**: Add review section to `tasks/todo.md`
6. **✶✶Capture Lessons✶✶**: Update `tasks/lessons.md` after corrections

## Core Principles

- **✶✶Simplicity First✶✶**: Make every change as simple as possible. Impact minimal code.
- **✶✶No Laziness✶✶**: Find root causes. No temporary fixes. Senior developer standards.
- **✶✶Minimal Impact✶✶**: Changes should only touch what's necessary. Avoid introducing bugs.
