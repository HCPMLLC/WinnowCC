# Winnow — Strategic Gap Exploitation: Cursor Implementation Prompts

## PROMPT44 through PROMPT55

### 12 Sequenced Prompts to Exploit Critical Gaps in Job Distribution, Candidate Matching & Employer Services

---

## What This Document Is

The Winnow strategic analysis identified 10 systemic gaps in the recruiting industry — gaps that no current platform (LinkedIn, Indeed, ZipRecruiter, programmatic advertisers) adequately addresses. Winnow already has a strong candidate-side platform (PROMPTs 1–24) and the beginnings of a two-sided marketplace (PROMPTs 33–43). These 12 new prompts build the features that transform Winnow from a job-matching tool into the industry's first truly integrated recruiting platform.

**Each prompt below is designed to be copied in full and pasted directly into Cursor AI.**

---

## What Already Exists (DO NOT Recreate)

Before using these prompts, understand what's already built:

### Candidate Side (PROMPTs 1–24)
- Auth (JWT cookies, `get_current_user`): `services/api/app/services/auth.py`
- Resume parsing & profile: `services/api/app/services/profile_parser.py`
- Job ingestion (Remotive, The Muse, etc.): `services/api/app/services/` + provider adapters
- Matching engine (skill overlap + semantic): `services/api/app/services/matching.py`
- Tailored ATS resume generation: `services/api/app/services/tailor.py`, `docx_builder.py`
- Cover letters: included in tailor pipeline
- Interview probability scoring: in `matching.py`
- Application tracking: `application_tracking` table, status on `matches`
- Dashboard metrics: `services/api/app/routers/dashboard.py`
- Sieve AI assistant: `services/api/app/services/sieve.py`, `routers/sieve.py`
- Subscription billing (candidate-side Stripe): `services/api/app/routers/billing.py`
- Semantic search (pgvector): embeddings on `jobs` and `candidate_profiles`
- Data export & account deletion: `services/api/app/services/data_export.py`
- Security hardening, monitoring, Sentry: PROMPTs 21–22

### Employer Side (PROMPTs 33–43)
- Database schema: `employer_profiles`, `employer_jobs`, `employer_candidate_views`, `employer_saved_candidates`
- `users.role` column: `'candidate'`, `'employer'`, `'both'`
- `candidate_profiles` visibility: `open_to_opportunities`, `profile_visibility`
- SQLAlchemy models: `services/api/app/models/employer.py`
- Pydantic schemas: `services/api/app/schemas/employer.py`
- API routes: `services/api/app/routers/employer.py`
- Frontend auth with role switching: PROMPT37
- Employer UI pages: `apps/web/app/employer/` (dashboard, jobs, candidates, settings)
- Employer subscription/billing (Stripe): PROMPT39
- Mobile app (Expo): PROMPT40
- Job uploader with AI parsing: PROMPT43

### Infrastructure
- Monorepo: `apps/web/` (Next.js 14) + `services/api/` (FastAPI) + `infra/` (Docker Compose)
- Postgres 16 + pgvector, Redis 7
- RQ worker: `services/api/app/worker.py`
- Queue service: `services/api/app/services/queue.py`
- Alembic migrations: `services/api/alembic/`
- Cloud Run deployment: PROMPT16/41

### Key Conventions
- **Python style:** Ruff, 88 char lines, snake_case
- **TypeScript style:** Prettier + ESLint
- **Migrations:** `cd services/api && alembic revision --autogenerate -m "description" && alembic upgrade head`
- **Lint:** `cd services/api && python -m ruff check . && python -m ruff format .`
- **Frontend lint:** `cd apps/web && npm run lint`

---

## Gap → Prompt Mapping

| Strategic Gap | Prompt(s) |
|---|---|
| Data Freshness (6–24hr feed delays) | PROMPT44, PROMPT45 |
| Format Fragmentation (every board has different specs) | PROMPT44, PROMPT46 |
| Quality vs. Volume (optimizing clicks, not hires) | PROMPT46, PROMPT50 |
| Attribution & Analytics (no cross-board visibility) | PROMPT47 |
| Candidate Experience (black holes, duplicates, no status) | PROMPT48 |
| Compliance & Audit (manual OFCCP tracking, no bias detection) | PROMPT49 |
| Bias & Equity (algorithms perpetuate historical patterns) | PROMPT49 |
| Talent Pipeline (every req starts from zero) | PROMPT50 |
| Cost Transparency (opaque pricing, no cost-per-quality-hire) | PROMPT47 |
| Public Sector Needs (USAJobs disconnected from commercial boards) | PROMPT51 |

---

# PROMPT 44: Multi-Board Job Distribution Engine

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 33–43 before making changes.

## Purpose

Build the core distribution engine that pushes employer jobs from Winnow to external job boards (LinkedIn, Indeed, ZipRecruiter, Glassdoor, Google for Jobs) via API or structured feed. This is the single most important feature for exploiting the **data freshness** and **format fragmentation** gaps — Winnow becomes the single source of truth that syncs in minutes, not hours.

## Gap Exploited

- **Data Freshness:** Current XML feeds update every 6–24 hours. Winnow syncs within minutes.
- **Format Fragmentation:** Each board has unique specs. Winnow normalizes once, adapts per board.

## What Already Exists (DO NOT recreate)

1. **Employer jobs table:** `employer_jobs` with title, description, requirements, location, salary, status, etc. (PROMPT33)
2. **Employer models:** `services/api/app/models/employer.py` — `EmployerJob` model (PROMPT34)
3. **Employer routes:** `services/api/app/routers/employer.py` — CRUD for employer jobs (PROMPT36)
4. **Job parser:** `services/api/app/services/job_parser.py` — extracts structured intelligence from job text (PROMPT10)
5. **Worker/queue:** `services/api/app/worker.py` + `services/api/app/services/queue.py` — RQ background jobs
6. **Job uploader:** PROMPT43 — AI-powered .docx upload to create jobs

## What to Build

### Part 1: Database — Distribution Tables

Create an Alembic migration adding these tables:

**`board_connections`** — stores employer's credentials/config per external board:
- `id` (UUID PK)
- `employer_id` (FK → employer_profiles.id, CASCADE)
- `board_type` (VARCHAR 50) — 'linkedin', 'indeed', 'ziprecruiter', 'glassdoor', 'google_jobs', 'usajobs', 'custom'
- `board_name` (VARCHAR 255) — display name
- `api_key_encrypted` (TEXT nullable) — encrypted credentials
- `api_secret_encrypted` (TEXT nullable)
- `feed_url` (VARCHAR 500 nullable) — for XML feed-based boards
- `is_active` (BOOLEAN default true)
- `config` (JSONB nullable) — board-specific settings (posting defaults, category mappings)
- `last_sync_at` (TIMESTAMP nullable)
- `last_sync_status` (VARCHAR 50 nullable) — 'success', 'partial', 'failed'
- `last_sync_error` (TEXT nullable)
- `created_at`, `updated_at`
- UNIQUE constraint on (employer_id, board_type)

**`job_distributions`** — tracks each job's status on each board:
- `id` (UUID PK)
- `employer_job_id` (FK → employer_jobs.id, CASCADE)
- `board_connection_id` (FK → board_connections.id, CASCADE)
- `external_job_id` (VARCHAR 255 nullable) — the ID on the remote board
- `status` (VARCHAR 50) — 'pending', 'submitted', 'live', 'expired', 'failed', 'removed'
- `submitted_at`, `live_at`, `removed_at` (TIMESTAMP nullable)
- `feed_payload` (JSONB nullable) — exact data sent to the board
- `error_message` (TEXT nullable)
- `impressions` (INTEGER default 0)
- `clicks` (INTEGER default 0)
- `applications` (INTEGER default 0)
- `cost_spent` (NUMERIC(10,2) default 0)
- `created_at`, `updated_at`
- UNIQUE constraint on (employer_job_id, board_connection_id)

**`distribution_events`** — audit log for every distribution action:
- `id` (UUID PK)
- `distribution_id` (FK → job_distributions.id, CASCADE)
- `event_type` (VARCHAR 50) — 'submitted', 'confirmed_live', 'updated', 'removed', 'error', 'metrics_synced'
- `event_data` (JSONB nullable)
- `created_at`

Add indexes on: `job_distributions.status`, `job_distributions.employer_job_id`, `board_connections.employer_id`, `distribution_events.distribution_id`.

### Part 2: SQLAlchemy Models

**File to create:** `services/api/app/models/distribution.py`

Create models for `BoardConnection`, `JobDistribution`, `DistributionEvent`. Add relationships:
- `EmployerProfile.board_connections` → list of BoardConnection
- `EmployerJob.distributions` → list of JobDistribution
- `BoardConnection.distributions` → list of JobDistribution
- `JobDistribution.events` → list of DistributionEvent

Import in `services/api/app/models/__init__.py`.

### Part 3: Board Adapter Interface

**File to create:** `services/api/app/services/board_adapters/__init__.py`
**File to create:** `services/api/app/services/board_adapters/base.py`

Create an abstract base class `BoardAdapter` with this interface:

```python
from abc import ABC, abstractmethod

class BoardAdapter(ABC):
    """Interface for all job board integrations."""
    
    board_type: str  # 'linkedin', 'indeed', etc.
    
    @abstractmethod
    async def validate_credentials(self, connection: BoardConnection) -> bool:
        """Test that the stored credentials are valid."""
    
    @abstractmethod
    async def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Push a job to this board. Returns {'external_id': '...', 'status': 'live'|'pending'}."""
    
    @abstractmethod
    async def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update an existing job on this board."""
    
    @abstractmethod
    async def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove/unpublish a job from this board."""
    
    @abstractmethod
    async def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Pull impressions, clicks, applications from the board."""
    
    @abstractmethod
    def format_job(self, job: EmployerJob) -> dict:
        """Transform job data into this board's required format."""
```

### Part 4: Board Adapters — Implement 3 Adapters

**File to create:** `services/api/app/services/board_adapters/indeed.py`
**File to create:** `services/api/app/services/board_adapters/google_jobs.py`
**File to create:** `services/api/app/services/board_adapters/xml_feed.py`

For Indeed and Google for Jobs, implement real adapters that format jobs according to each board's API/schema specifications. For Google for Jobs, generate structured data (JSON-LD `JobPosting` schema) that employers can embed in their career pages.

The `xml_feed.py` adapter generates standard XML job feeds (HR-XML / HRXML compatible) that any board can ingest — this is the universal fallback for boards without direct API access.

For v1, if we don't have real API keys, implement the adapters with full formatting logic but stub the actual HTTP calls with clear `# TODO: Replace with real API call` comments. The formatting and data transformation must be production-ready.

### Part 5: Distribution Service

**File to create:** `services/api/app/services/distribution.py`

This orchestrates all distribution operations:

```python
async def distribute_job(employer_job_id: UUID, board_types: list[str] | None, db: Session):
    """Distribute a job to specified boards (or all active connections)."""

async def update_distribution(employer_job_id: UUID, db: Session):
    """Push updates to all boards where this job is live."""

async def remove_from_boards(employer_job_id: UUID, db: Session):
    """Remove a job from all boards (called when job status → closed/paused)."""

async def sync_metrics(employer_job_id: UUID, db: Session):
    """Pull latest metrics from all boards for this job."""

async def sync_all_metrics(employer_id: UUID, db: Session):
    """Pull metrics for all active distributions for an employer."""
```

When an employer sets `employer_jobs.status` to `'active'`, automatically trigger distribution to all active board connections. When status changes to `'paused'` or `'closed'`, automatically remove from all boards. Log every action to `distribution_events`.

### Part 6: Distribution Router

**File to create:** `services/api/app/routers/distribution.py`

Endpoints (all require employer auth via `require_employer` dependency):

- `GET /api/distribution/connections` — list employer's board connections
- `POST /api/distribution/connections` — add a new board connection (board_type, credentials, config)
- `PUT /api/distribution/connections/{id}` — update connection settings
- `DELETE /api/distribution/connections/{id}` — remove a board connection
- `POST /api/distribution/connections/{id}/test` — validate credentials
- `POST /api/distribution/jobs/{job_id}/distribute` — distribute a specific job to boards
- `POST /api/distribution/jobs/{job_id}/remove` — remove a job from all boards
- `GET /api/distribution/jobs/{job_id}/status` — get distribution status across all boards
- `POST /api/distribution/sync-metrics` — trigger metrics sync for all active distributions

Register in `services/api/app/main.py`.

### Part 7: Auto-Distribution Worker Job

**File to modify:** `services/api/app/worker.py`

Add a new worker function `process_distribution` that:
1. Is enqueued when an employer job status changes to 'active'
2. Gets all active board connections for the employer
3. Calls each adapter's `submit_job` sequentially
4. Creates `JobDistribution` records with results
5. Logs all events to `distribution_events`
6. Handles failures per-board (one board failing doesn't block others)

Add a scheduled worker function `sync_distribution_metrics` that:
1. Runs every 15 minutes (configure via Redis scheduler or cron)
2. Fetches metrics for all 'live' distributions
3. Updates impressions, clicks, applications counts
4. Logs metrics events

### Part 8: Frontend — Board Connections Management

**File to create:** `apps/web/app/employer/connections/page.tsx`

Build a page at `/employer/connections` where employers:
- See all connected boards with status indicators (active/inactive/error)
- Add a new board connection (select board type → enter credentials → test → save)
- Edit or remove existing connections
- See last sync time and status for each connection

Add a "Boards" link to the employer sidebar navigation.

### Part 9: Frontend — Distribution Status on Job Detail

**File to modify:** `apps/web/app/employer/jobs/[id]/page.tsx`

Add a "Distribution" tab/section to the job detail page showing:
- Which boards this job is live on (with status badges: pending/live/failed/removed)
- Per-board metrics (impressions, clicks, applications)
- "Distribute to More Boards" button
- "Remove from All Boards" button
- Distribution event timeline

## Migration & Testing

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add distribution tables"
alembic upgrade head
python -m ruff check . && python -m ruff format .

cd ../../apps/web
npm run lint
```

Test manually:
1. Create employer account, add board connections
2. Create a job, set status to 'active'
3. Verify distribution records are created
4. Check distribution status on job detail page
5. Verify metrics sync updates counts

## Success Criteria

- [ ] Migration creates 3 new tables with proper indexes and constraints
- [ ] BoardAdapter abstract class defined with all required methods
- [ ] 3 adapters implemented (Indeed, Google Jobs, XML feed)
- [ ] Distribution service orchestrates submit/update/remove/sync
- [ ] Auto-distribution triggers when job status → active
- [ ] Auto-removal triggers when job status → paused/closed
- [ ] Distribution router has all endpoints with employer auth
- [ ] Worker handles distribution async with per-board error isolation
- [ ] Scheduled metrics sync runs every 15 minutes
- [ ] Frontend connections management page works
- [ ] Job detail page shows distribution status and per-board metrics
- [ ] All events logged to distribution_events audit table

---

# PROMPT 45: Real-Time Board Sync & Freshness Engine

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPT44 before making changes.

## Purpose

Ensure Winnow's job data stays fresh across all boards in near real-time. When a job is edited, filled, or closed, changes propagate to all boards within minutes — not hours. This directly attacks the **data freshness** gap where current XML feeds leave stale jobs visible for 6–24 hours.

## Gap Exploited

- **Data Freshness:** Candidates applying to already-filled jobs; employers screening ghost applicants.

## What Already Exists (DO NOT recreate)

Everything from PROMPT44: distribution tables, board adapters, distribution service, worker jobs.

## What to Build

### Part 1: Change Detection Hooks

**File to modify:** `services/api/app/routers/employer.py`

Add hooks to the existing employer job CRUD endpoints:
- When `PUT /api/employer/jobs/{id}` updates title, description, requirements, salary, or location → enqueue `sync_job_to_boards` worker job
- When `PATCH /api/employer/jobs/{id}/status` changes to 'paused' or 'closed' → enqueue `remove_job_from_boards` worker job
- When `PATCH /api/employer/jobs/{id}/status` changes to 'active' (re-activation) → enqueue `distribute_job` worker job

### Part 2: Freshness Monitor Worker

**File to create:** `services/api/app/services/freshness_monitor.py`

A scheduled worker job that runs every 5 minutes:
1. Query all `job_distributions` with status='live'
2. Check if the parent `employer_job` status is still 'active'
3. If the job is paused/closed but distribution is still 'live', trigger removal
4. Compare `employer_job.updated_at` vs `job_distribution.updated_at` — if the job was edited more recently, trigger an update push
5. Check for distributions stuck in 'pending' for more than 30 minutes and retry
6. Check for distributions in 'failed' status and retry up to 3 times with exponential backoff
7. Log all actions to `distribution_events`

### Part 3: Webhook Receiver for Board Callbacks

**File to create:** `services/api/app/routers/webhooks.py`

Some boards (LinkedIn, Indeed) send webhooks when a job's status changes on their side (e.g., expired, flagged, removed by board moderation). Create a webhook receiver:
- `POST /api/webhooks/board/{board_type}` — receives webhook payloads from boards
- Verifies webhook signatures (per board's specification)
- Updates `job_distributions` status accordingly
- Logs events to `distribution_events`
- Skips auth (webhooks are unauthenticated but signature-verified)

Register in `main.py`. Add webhook paths to any auth skip lists.

### Part 4: Freshness Dashboard Widget

**File to modify:** `apps/web/app/employer/dashboard/page.tsx`

Add a "Distribution Health" card to the employer dashboard showing:
- Total active distributions across all boards
- Count by status (live / pending / failed)
- "Last synced" timestamp
- Any boards with errors (red warning badge)
- "Sync Now" button that triggers immediate metrics pull

## Success Criteria

- [ ] Job edits trigger automatic sync to all live boards
- [ ] Job close/pause triggers automatic removal from all boards
- [ ] Freshness monitor catches and fixes stale/stuck distributions
- [ ] Failed distributions retry with exponential backoff (max 3 attempts)
- [ ] Webhook receiver processes board callbacks
- [ ] Employer dashboard shows distribution health at a glance

---

# PROMPT 46: Adaptive Content Optimizer

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–45 before making changes.

## Purpose

Automatically tailor each job posting's content for each board's unique audience and algorithm. LinkedIn professionals expect different language than Indeed hourly workers. This exploits the **format fragmentation** and **quality vs. volume** gaps — Winnow posts aren't one-size-fits-all.

## Gap Exploited

- **Format Fragmentation:** One generic posting everywhere vs. audience-tailored content per board.
- **Quality vs. Volume:** Optimizing for qualified applicants, not just clicks.

## What Already Exists (DO NOT recreate)

1. Board adapters from PROMPT44 with `format_job()` method
2. Job parser from PROMPT10 that extracts structured job intelligence
3. Tailor service from PROMPT12 that rewrites content using Claude (candidate resumes, but same pattern applies)

## What to Build

### Part 1: Content Optimizer Service

**File to create:** `services/api/app/services/content_optimizer.py`

Uses Claude (Anthropic API, already in requirements.txt) to optimize job postings per board:

```python
async def optimize_for_board(job: EmployerJob, board_type: str, db: Session) -> dict:
    """
    Take a job posting and optimize its content for a specific board's audience.
    Returns optimized title, description, requirements suitable for that board.
    
    Board-specific optimization rules:
    - LinkedIn: Professional tone, emphasize growth/culture/impact, include company story
    - Indeed: Clear and scannable, emphasize pay/benefits/schedule, simple language
    - ZipRecruiter: Keyword-dense for matching algorithm, highlight qualifications clearly
    - Google for Jobs: Structured data optimized, salary transparency, clean HTML
    - USAJobs: Government format compliance, KSA language, GS grade mapping
    """
```

Key rules for the LLM prompt:
- NEVER fabricate information — only rephrase and restructure what the employer wrote
- Maintain factual accuracy of salary, location, requirements
- Adapt tone and emphasis, not substance
- Generate a `content_diff` showing what was changed and why

### Part 2: Bias Scanner Integration

Before optimizing content, run a bias scan on the original job description:
- Detect gendered language ("rockstar", "ninja", "manpower")
- Detect unnecessarily exclusionary requirements ("must have 10+ years" when 5 would suffice)
- Detect age-coded language ("digital native", "energetic")
- Flag but don't auto-fix — surface to employer with suggestions

**File to create:** `services/api/app/services/job_bias_scanner.py`

```python
async def scan_job_for_bias(job: EmployerJob) -> dict:
    """
    Returns {
        'bias_score': 0-100 (0 = no bias detected, 100 = heavily biased),
        'flags': [{'type': 'gendered', 'text': 'rockstar', 'suggestion': 'top performer', 'severity': 'medium'}],
        'inclusive_alternatives': {...}
    }
    """
```

### Part 3: Quality Validation Layer

**File to create:** `services/api/app/services/posting_validator.py`

Before any job is distributed, validate:
- EEO statement present (warn if missing, configurable to block)
- Salary range included (required in CO, CA, NY, WA — check against job location)
- Apply URL is valid (HTTP 200 check)
- No broken formatting (malformed HTML/markdown)
- Description length meets board minimums (e.g., Indeed requires 150+ chars)
- No PII in posting (social security, personal phone numbers)

### Part 4: Optimization Router

Add endpoints to `services/api/app/routers/distribution.py`:
- `POST /api/distribution/jobs/{job_id}/preview/{board_type}` — preview optimized content for a specific board without posting
- `GET /api/distribution/jobs/{job_id}/bias-scan` — get bias scan results
- `GET /api/distribution/jobs/{job_id}/validation` — get validation results

### Part 5: Frontend — Optimization Preview

**File to modify:** `apps/web/app/employer/jobs/[id]/page.tsx`

Add a "Preview by Board" section to the job detail page:
- Dropdown to select a board type
- Side-by-side view: original posting vs. optimized version
- Bias scan results with flag icons and suggestions
- Validation checklist (green check / yellow warning / red error)
- "Accept Optimizations" button that saves the optimized version for that board

## Success Criteria

- [ ] Content optimizer adapts tone/structure per board using Claude
- [ ] Bias scanner detects gendered, age-coded, and exclusionary language
- [ ] Posting validator checks EEO, salary, URL, formatting, length, PII
- [ ] Preview endpoint returns optimized content without publishing
- [ ] Frontend shows side-by-side original vs. optimized
- [ ] Bias flags displayed with severity and suggestions
- [ ] Validation results shown as checklist with pass/warn/fail

---

# PROMPT 47: Cross-Board Analytics & True Attribution

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–46 before making changes.

## Purpose

Give employers complete, honest, cross-channel visibility into where their money and postings are performing — including the industry's first **cost-per-quality-hire** metric. This exploits the **attribution** and **cost transparency** gaps.

## Gap Exploited

- **Attribution & Analytics:** No current platform provides cross-board visibility with multi-touch attribution.
- **Cost Transparency:** Programmatic platforms hide margins; Winnow shows real cost-per-outcome.

## What Already Exists (DO NOT recreate)

1. `employer_jobs` with `view_count`, `application_count` (PROMPT33)
2. `job_distributions` with per-board `impressions`, `clicks`, `applications`, `cost_spent` (PROMPT44)
3. `distribution_events` audit log (PROMPT44)
4. Employer analytics summary schema: `EmployerAnalyticsSummary` (PROMPT35)
5. Existing employer dashboard: `apps/web/app/employer/dashboard/page.tsx`

## What to Build

### Part 1: Analytics Events Table

Add an Alembic migration for:

**`employer_analytics_events`** — fine-grained tracking:
- `id` (UUID PK)
- `employer_id` (FK → employer_profiles.id)
- `employer_job_id` (FK → employer_jobs.id nullable)
- `event_type` (VARCHAR 50) — 'impression', 'click', 'apply_start', 'apply_complete', 'screen_pass', 'interview_scheduled', 'offer_extended', 'hire'
- `source_board` (VARCHAR 50) — which board this event originated from
- `candidate_id` (FK → candidate_profiles.id nullable) — for attribution tracking
- `cost` (NUMERIC(10,2) nullable) — cost associated with this event
- `metadata` (JSONB nullable) — additional context
- `created_at`

Index on (employer_id, event_type, created_at) for fast aggregation.

### Part 2: Analytics Engine Service

**File to create:** `services/api/app/services/employer_analytics.py`

```python
async def get_funnel_by_board(employer_id: UUID, job_id: UUID | None, date_range: tuple, db: Session) -> dict:
    """
    Returns funnel metrics per board:
    {
        'linkedin': {'impressions': 1200, 'clicks': 340, 'applications': 45, 'qualified': 12, 'interviews': 5, 'offers': 1, 'hires': 1},
        'indeed': {'impressions': 3400, 'clicks': 890, 'applications': 120, 'qualified': 8, ...},
        ...
    }
    """

async def get_cost_per_outcome(employer_id: UUID, date_range: tuple, db: Session) -> dict:
    """
    Returns cost metrics that ACTUALLY MATTER:
    {
        'cost_per_application': 12.50,
        'cost_per_qualified_application': 45.00,
        'cost_per_interview': 120.00,
        'cost_per_hire': 2400.00,
        'by_board': {
            'linkedin': {'cost_per_hire': 1800, 'roi_score': 85},
            'indeed': {'cost_per_hire': 3200, 'roi_score': 62},
        }
    }
    """

async def get_time_to_fill(employer_id: UUID, date_range: tuple, db: Session) -> dict:
    """Average days from job posted to hire, broken down by board, role type, and location."""

async def get_source_attribution(employer_id: UUID, job_id: UUID, db: Session) -> list[dict]:
    """
    Multi-touch attribution: for each hire, show the full journey.
    E.g., 'First saw on LinkedIn → Applied via Indeed → Hired'
    """

async def get_board_recommendations(employer_id: UUID, db: Session) -> list[dict]:
    """
    Based on historical data, recommend which boards to use for the employer's
    next job based on role type, location, seniority level.
    """
```

### Part 3: Analytics Router

**File to create:** `services/api/app/routers/employer_analytics.py`

- `GET /api/employer/analytics/overview` — summary metrics (active jobs, total spend, hires this month)
- `GET /api/employer/analytics/funnel?job_id=&start_date=&end_date=` — funnel by board
- `GET /api/employer/analytics/cost` — cost-per-outcome breakdown
- `GET /api/employer/analytics/time-to-fill` — time-to-fill by board/role
- `GET /api/employer/analytics/attribution/{job_id}` — multi-touch attribution for a job
- `GET /api/employer/analytics/recommendations` — board recommendations

Register in `main.py`.

### Part 4: Frontend — Analytics Dashboard

**File to create:** `apps/web/app/employer/analytics/page.tsx`

Build a comprehensive analytics page at `/employer/analytics` with:
1. **Summary cards:** Total spend, hires this period, avg cost-per-hire, avg time-to-fill
2. **Funnel chart:** Visual funnel (impressions → clicks → applications → qualified → interviews → offers → hires) with board-color coding
3. **Cost-per-outcome table:** Board-by-board comparison of cost-per-application, cost-per-interview, cost-per-hire
4. **Time-to-fill chart:** Line chart showing trend over time with board comparison
5. **Board recommendations:** Cards suggesting which boards to use for upcoming roles
6. **Date range selector:** Last 7/30/90 days, custom range

Use `recharts` (already installed in the project) for charts.

Add "Analytics" link to employer sidebar navigation.

## Success Criteria

- [ ] Analytics events table captures full hiring funnel
- [ ] Funnel breakdown by board with real counts
- [ ] Cost-per-quality-hire metric calculated (not just cost-per-click)
- [ ] Multi-touch attribution shows candidate journey across boards
- [ ] Board recommendations based on historical performance
- [ ] Time-to-fill tracking by board, role, location
- [ ] Frontend dashboard with charts, tables, and date filtering
- [ ] All data scoped to employer (multi-tenant security)

---

# PROMPT 48: Candidate Experience Layer — Status Transparency & Deduplication

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–47 before making changes.

## Purpose

Transform the candidate experience from the industry-standard "black hole" into a transparent, respectful process. Candidates know where they stand, see each job once (no duplicates), and receive thoughtful communication at every stage. This exploits the **candidate experience** gap.

## Gap Exploited

- **Candidate Experience:** Duplicate listings, application black holes, no status updates, redirect friction.

## What Already Exists (DO NOT recreate)

1. Candidate-side application tracking: `application_tracking` table with statuses (PROMPT11)
2. Candidate profile: `candidate_profiles` with `profile_json`, visibility settings (PROMPT33)
3. Matches with status: `matches.application_status` (saved/applied/interviewing/rejected/offer)
4. Email service: `services/api/app/services/email_service.py` (if exists) or Resend SDK

## What to Build

### Part 1: Application Status Push Notifications

**File to create:** `services/api/app/services/candidate_notifications.py`

When an employer changes a candidate's application status (via employer dashboard), automatically notify the candidate:
- **Applied → Screening:** "Your application for [Job Title] at [Company] is being reviewed."
- **Screening → Interview:** "Great news! [Company] would like to interview you for [Job Title]."
- **Interview → Offer:** "Congratulations! [Company] has extended an offer for [Job Title]."
- **Any → Rejected:** "[Company] has decided to move forward with other candidates for [Job Title]. [Optional: employer-written feedback]"

Notifications via email (Resend SDK). Store notification history in a new `candidate_notifications` table:
- `id`, `candidate_id` (FK), `employer_job_id` (FK nullable), `notification_type`, `subject`, `body`, `sent_at`, `read_at`

### Part 2: Employer-Side Status Management

**File to modify:** `services/api/app/routers/employer.py`

Add endpoint for employers to update candidate application status:
- `PATCH /api/employer/applications/{application_id}/status` — accepts new status + optional feedback message
- When status changes, triggers notification to candidate
- Logs to compliance audit trail
- Syncs back to candidate's `application_tracking` if they're a Winnow user

### Part 3: Job Deduplication Service

**File to create:** `services/api/app/services/job_deduplicator.py`

When candidates search or browse jobs:
- Detect duplicate jobs (same employer, same title, same location posted on multiple boards)
- Show each unique job ONCE with a "Also posted on: LinkedIn, Indeed" indicator
- Use content hashing + title/company/location similarity to detect duplicates
- This leverages the existing `job_parsed_details` enriched data

### Part 4: Candidate-Side Status Dashboard

**File to modify:** `apps/web/app/dashboard/page.tsx`

Enhance the existing candidate dashboard to show:
- Notification feed: recent status updates from employers
- Application pipeline visualization: how many apps at each stage (applied → screening → interview → offer)
- "No response" indicator: flag applications with no status change in 14+ days

### Part 5: Respectful Rejection with Recommendations

When a candidate is rejected:
- Include optional employer feedback (if provided)
- Include "Similar roles you might like" — 3 active jobs matching the candidate's profile
- Include "How to strengthen your application" — based on the gap between candidate profile and rejected job's requirements

## Success Criteria

- [ ] Candidates receive email notifications on every status change
- [ ] Employers can update application status with optional feedback
- [ ] Notification history stored and retrievable
- [ ] Job deduplication shows each unique job once
- [ ] Candidate dashboard shows notification feed and pipeline
- [ ] Rejected candidates get feedback + similar job recommendations
- [ ] All status changes logged for compliance

---

# PROMPT 49: Compliance Engine & Bias Detection

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–48 before making changes.

## Purpose

Build compliance and equity into Winnow's infrastructure — automated OFCCP audit trails, proactive DEI sourcing recommendations, and bias detection in job postings. This exploits the **compliance** and **bias & equity** gaps.

## Gap Exploited

- **Compliance & Audit:** Manual tracking of posting locations/dates; no integrated OFCCP/EEO reporting.
- **Bias & Equity:** Algorithms perpetuate historical patterns; no proactive DEI sourcing.

## What Already Exists (DO NOT recreate)

1. Candidate-side trust/compliance: `candidate_trust` table, `trust_audit_log` (PROMPTs 4/21)
2. Job bias scanner (if built in PROMPT46): `services/api/app/services/job_bias_scanner.py`
3. Distribution events audit log: `distribution_events` (PROMPT44)

## What to Build

### Part 1: Compliance Audit Log (Employer-Side)

Add an Alembic migration for:

**`employer_compliance_log`**:
- `id` (UUID PK)
- `employer_id` (FK → employer_profiles.id)
- `employer_job_id` (FK → employer_jobs.id nullable)
- `event_type` (VARCHAR 50) — 'job_posted', 'job_edited', 'job_closed', 'candidate_viewed', 'candidate_status_changed', 'distribution_sent', 'distribution_removed', 'eeo_report_generated', 'ofccp_export'
- `event_data` (JSONB) — full audit payload
- `board_type` (VARCHAR 50 nullable)
- `user_id` (FK → users.id nullable — who triggered it)
- `ip_address` (VARCHAR 45 nullable)
- `created_at`

Index on (employer_id, event_type, created_at).

### Part 2: Compliance Service

**File to create:** `services/api/app/services/employer_compliance.py`

```python
def log_compliance_event(employer_id, event_type, event_data, job_id=None, user_id=None, db=None):
    """Log every auditable action."""

async def generate_ofccp_report(employer_id: UUID, date_range: tuple, db: Session) -> dict:
    """
    Generate OFCCP-ready audit report:
    - Every job posted with dates, boards, and duration
    - Candidate flow data: applicants by source, status outcomes
    - Disposition summary: why candidates were rejected at each stage
    - EEO data summary (if collected)
    """

async def generate_eeo_summary(employer_id: UUID, job_id: UUID | None, db: Session) -> dict:
    """
    EEO-1 compatible summary (voluntary self-ID data if collected):
    - Applicant demographics by job category
    - Hire rates by demographic group
    - Adverse impact analysis
    """

async def get_posting_compliance_status(employer_job_id: UUID, db: Session) -> dict:
    """
    Check a job's compliance status:
    - EEO statement present? 
    - Posted to required boards (for government contractors)?
    - Salary transparency compliance (by state)?
    - Posting duration meets minimum requirements?
    """
```

### Part 3: DEI Sourcing Recommendations

**File to create:** `services/api/app/services/dei_sourcing.py`

```python
async def analyze_candidate_pool_diversity(employer_id: UUID, job_id: UUID, db: Session) -> dict:
    """
    Analyze the current applicant pool and identify diversity gaps.
    Returns recommendations for additional sourcing channels:
    - HBCUs and minority-serving institution career boards
    - Veteran job boards (e.g., Hire Heroes USA, Military.com)
    - Disability-focused boards (e.g., AbilityJobs, Getting Hired)
    - Women-in-tech boards (e.g., PowerToFly, Women Who Code)
    - Professional associations for underrepresented groups
    """
```

### Part 4: Compliance Router

Add to `services/api/app/routers/employer.py` or create `services/api/app/routers/employer_compliance.py`:

- `GET /api/employer/compliance/log?job_id=&event_type=&start_date=&end_date=` — paginated audit log
- `GET /api/employer/compliance/report/ofccp?start_date=&end_date=` — generate OFCCP report (returns JSON or triggers PDF/CSV export)
- `GET /api/employer/compliance/job/{job_id}/status` — compliance checklist for a job
- `GET /api/employer/compliance/dei-recommendations/{job_id}` — DEI sourcing recommendations

### Part 5: Frontend — Compliance Dashboard

**File to create:** `apps/web/app/employer/compliance/page.tsx`

Build a page at `/employer/compliance` with:
1. **Compliance score card:** Overall compliance health (% of jobs meeting all requirements)
2. **Audit log viewer:** Searchable, filterable timeline of all compliance events
3. **OFCCP report generator:** Date range selector → "Generate Report" → download CSV/PDF
4. **Per-job compliance checklist:** Green/yellow/red status for EEO, salary transparency, posting duration
5. **DEI recommendations panel:** Which additional sourcing channels to add for current open roles

Add "Compliance" link to employer sidebar navigation.

## Success Criteria

- [ ] Every employer action logged to compliance audit trail
- [ ] OFCCP report generator produces complete audit data
- [ ] Per-job compliance status checks (EEO, salary, posting duration)
- [ ] DEI sourcing recommendations with specific board suggestions
- [ ] Bias scanner from PROMPT46 integrated into compliance dashboard
- [ ] Frontend compliance page with audit log, reports, and DEI panel
- [ ] All compliance data exportable as CSV

---

# PROMPT 50: Silver Medalist Talent Pipeline CRM

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 33–49 before making changes.

## Purpose

Build a living talent pipeline so employers never start from zero. Strong candidates who weren't selected for one role are automatically tagged, scored, and available for future roles. This exploits the **talent pipeline** gap.

## Gap Exploited

- **Talent Pipeline:** Every req starts from zero; silver medalists forgotten; recurring sourcing costs.

## What Already Exists (DO NOT recreate)

1. Employer saved candidates: `employer_saved_candidates` with notes (PROMPT33)
2. Candidate profiles with skills, experience, semantic embeddings (PROMPTs 9, 15)
3. Matching engine with semantic similarity (PROMPT15)

## What to Build

### Part 1: Pipeline Tables

Add an Alembic migration for:

**`talent_pipeline`**:
- `id` (UUID PK)
- `employer_id` (FK → employer_profiles.id, CASCADE)
- `candidate_profile_id` (FK → candidate_profiles.id, CASCADE)
- `pipeline_status` (VARCHAR 50) — 'silver_medalist', 'warm_lead', 'nurturing', 'contacted', 'not_interested', 'hired'
- `source_job_id` (FK → employer_jobs.id nullable) — the job they originally applied/were considered for
- `match_score` (INTEGER nullable) — how well they matched the source job
- `tags` (JSONB) — employer-defined tags ['backend', 'senior', 'visa-required']
- `notes` (TEXT nullable) — recruiter notes
- `last_contacted_at` (TIMESTAMP nullable)
- `next_followup_at` (TIMESTAMP nullable)
- `consent_given` (BOOLEAN default false)
- `consent_date` (TIMESTAMP nullable)
- `created_at`, `updated_at`
- UNIQUE constraint on (employer_id, candidate_profile_id)

### Part 2: Pipeline Service

**File to create:** `services/api/app/services/talent_pipeline.py`

```python
async def add_to_pipeline(employer_id, candidate_id, source_job_id, status, tags, notes, db):
    """Add a candidate to the talent pipeline (with consent check)."""

async def search_pipeline(employer_id, filters: dict, db) -> list:
    """
    Search the pipeline by: skills, tags, pipeline_status, match_score range.
    Uses semantic similarity against a new job's requirements to find
    pipeline candidates who might be good fits.
    """

async def suggest_pipeline_candidates(employer_id, new_job_id, db) -> list:
    """
    For a new job posting, automatically surface pipeline candidates
    who might be a good fit. Uses embedding similarity between the
    new job's requirements and the pipeline candidates' profiles.
    """

async def auto_add_silver_medalists(employer_id, job_id, db):
    """
    When a job is filled, automatically add all candidates who reached
    the interview stage but weren't hired as 'silver_medalist' in the pipeline.
    Requires candidate consent.
    """
```

### Part 3: Pipeline Router

Add to employer routes or create `services/api/app/routers/talent_pipeline.py`:

- `GET /api/employer/pipeline` — list pipeline with filters
- `POST /api/employer/pipeline` — add candidate to pipeline
- `PUT /api/employer/pipeline/{id}` — update status, tags, notes
- `DELETE /api/employer/pipeline/{id}` — remove from pipeline
- `GET /api/employer/pipeline/suggestions/{job_id}` — get pipeline candidates matching a new job
- `POST /api/employer/pipeline/auto-add/{job_id}` — auto-add silver medalists from a filled job

### Part 4: Frontend — Pipeline Page

**File to create:** `apps/web/app/employer/pipeline/page.tsx`

Build a Kanban-style or list view at `/employer/pipeline`:
- Columns by status: Silver Medalist → Warm Lead → Nurturing → Contacted → Hired
- Each card: candidate name (or anonymous), skills, match score, tags, last contact date
- Drag-and-drop between columns to change status
- Bulk actions: tag multiple candidates, export list
- Search/filter by skills, tags, source job
- "Suggested for [Job Title]" section when a new job is active

Add "Pipeline" link to employer sidebar navigation.

## Success Criteria

- [ ] Pipeline table stores candidates with status, tags, notes, consent
- [ ] Auto-add silver medalists when a job is filled
- [ ] Semantic search finds pipeline candidates matching new jobs
- [ ] Pipeline suggestions surface relevant candidates for new postings
- [ ] Candidate consent required before adding to pipeline
- [ ] Frontend Kanban/list view with search, filter, drag-and-drop
- [ ] Pipeline data exportable for outreach campaigns

---

# PROMPT 51: Public Sector Integration (USAJobs)

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–50 before making changes.

## Purpose

Add native integration with USAJobs and state government job portals, eliminating the parallel manual workflow that plagues government recruiters. This exploits the **public sector needs** gap.

## Gap Exploited

- **Public Sector Needs:** Government systems disconnected from commercial boards; double the manual work.

## What Already Exists (DO NOT recreate)

1. Board adapter interface from PROMPT44: `services/api/app/services/board_adapters/base.py`
2. Distribution engine from PROMPT44
3. Compliance engine from PROMPT49

## What to Build

### Part 1: USAJobs Board Adapter

**File to create:** `services/api/app/services/board_adapters/usajobs.py`

Implement the `BoardAdapter` interface for USAJobs:
- USAJobs API is publicly documented at `developer.usajobs.gov`
- Requires API key + User-Agent email for authentication
- `format_job()` must map Winnow fields to USAJobs format: position title, pay plan, series, grade, duty location, who may apply, etc.
- Handle USAJobs-specific fields: announcement number, control number, hiring path, security clearance level
- Map employment types: competitive service, excepted service, SES
- Include KSA (Knowledge, Skills, Abilities) mapping from job requirements

### Part 2: Government Compliance Extensions

**File to modify:** `services/api/app/services/employer_compliance.py`

Add government-specific compliance checks:
- Veterans' preference tracking (VEVRAA)
- Section 503 disability compliance
- Required posting duration (minimum days for government positions)
- Merit system principles verification
- Competitive vs. excepted service designation

### Part 3: GS Grade Auto-Mapping

**File to create:** `services/api/app/services/gs_mapper.py`

```python
def map_salary_to_gs_grade(salary_min: int, salary_max: int, location: str) -> dict:
    """
    Map a salary range to the appropriate GS grade range,
    accounting for locality pay tables.
    Returns {'gs_low': 'GS-12', 'gs_high': 'GS-14', 'pay_plan': 'GS'}
    """
```

### Part 4: State Portal Adapters

**File to create:** `services/api/app/services/board_adapters/state_portal.py`

A configurable adapter for state government job portals:
- Template-based: employer provides the state portal's submission URL and field mappings
- Supports common state portal patterns (NeoGov, NEOGOV-based systems)
- Generates PDF/DOCX formatted postings for manual upload portals (fallback)

### Part 5: Frontend — Government Board Setup

**File to modify:** `apps/web/app/employer/connections/page.tsx`

Add a "Government Boards" section to the board connections page:
- USAJobs connection setup (API key + email)
- State portal selection (dropdown of common state portals)
- Government-specific posting defaults (announcement number prefix, hiring path, etc.)
- Compliance reminder banner: "Government postings require minimum [X] day duration"

## Success Criteria

- [ ] USAJobs adapter formats jobs to USAJobs API specification
- [ ] GS grade auto-mapping from salary ranges with locality pay
- [ ] Government compliance checks added to compliance engine
- [ ] State portal adapter handles common portal patterns
- [ ] Frontend enables USAJobs connection setup
- [ ] Distribution engine treats government boards same as commercial (unified workflow)
- [ ] VEVRAA and Section 503 tracking in compliance reports

---

# PROMPT 52: Recruiter Workload Intelligence & Action Queue

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–51 before making changes.

## Purpose

Surface the highest-priority actions for recruiters each day — which candidates to follow up with, which postings are underperforming, which hiring managers need updates. This exploits the **recruiter empowerment** pillar from the strategic plan.

## What to Build

### Part 1: Action Queue Service

**File to create:** `services/api/app/services/recruiter_actions.py`

```python
async def generate_daily_actions(employer_id: UUID, user_id: UUID, db: Session) -> list[dict]:
    """
    Generate prioritized action items for a recruiter:
    1. Candidates awaiting response for 48+ hours (URGENT)
    2. Interviews scheduled in next 48 hours needing prep
    3. Jobs with declining application rates (below average for role type)
    4. Pipeline candidates matching newly posted jobs
    5. Distributions with errors needing attention
    6. Compliance items due (posting about to expire, reports due)
    7. Hiring manager update reminders
    
    Each action: {priority: 1-5, type, title, description, action_url, due_by}
    """
```

### Part 2: Action Router

- `GET /api/employer/actions` — get prioritized action queue
- `POST /api/employer/actions/{id}/dismiss` — dismiss an action
- `POST /api/employer/actions/{id}/snooze` — snooze for X hours

### Part 3: Frontend — Action Queue Widget

Add to `apps/web/app/employer/dashboard/page.tsx`:
- "Today's Actions" panel with prioritized cards
- Each card: icon, title, description, action button, dismiss/snooze
- Color coding by priority (red=urgent, yellow=important, blue=informational)
- Badge count in sidebar navigation showing pending action count

## Success Criteria

- [ ] Action queue generates prioritized daily to-do list
- [ ] Actions cover: candidate follow-ups, underperforming jobs, pipeline matches, compliance items
- [ ] Frontend shows action cards with priority color coding
- [ ] Dismiss and snooze work correctly
- [ ] Badge count updates in sidebar navigation

---

# PROMPT 53: Collaborative Hiring Workspace

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 33–52 before making changes.

## Purpose

Eliminate email chains and spreadsheet tracking by giving hiring managers, interviewers, and recruiters a shared workspace with structured feedback and real-time status.

## What to Build

### Part 1: Team Members & Permissions

Add migration for `employer_team_members`:
- `id`, `employer_id`, `user_id`, `role` ('recruiter', 'hiring_manager', 'interviewer', 'viewer')
- `job_access` (JSONB) — which jobs this team member can see (null = all)
- `invited_at`, `accepted_at`

### Part 2: Interview Feedback Cards

Add migration for `interview_feedback`:
- `id`, `employer_job_id`, `candidate_profile_id`, `interviewer_user_id`
- `interview_type` ('phone_screen', 'technical', 'behavioral', 'panel', 'final')
- `rating` (1–5), `recommendation` ('strong_yes', 'yes', 'neutral', 'no', 'strong_no')
- `strengths` (TEXT), `concerns` (TEXT), `notes` (TEXT)
- `submitted_at`

### Part 3: Hiring Workspace Router

- `GET /api/employer/jobs/{job_id}/workspace` — full workspace view: all candidates, feedback, status
- `POST /api/employer/jobs/{job_id}/feedback` — submit interview feedback
- `GET /api/employer/jobs/{job_id}/scorecard` — aggregated interview scorecard per candidate
- `POST /api/employer/team/invite` — invite team member
- `GET /api/employer/team` — list team members

### Part 4: Frontend — Workspace Page

**File to create:** `apps/web/app/employer/jobs/[id]/workspace/page.tsx`

- Candidate pipeline view (columns: applied → screening → interview → offer → hired)
- Click a candidate to see all interview feedback, notes, scorecard
- Submit feedback form with rating, recommendation, strengths, concerns
- Aggregated scorecard showing all interviewers' ratings side-by-side
- Activity feed: who did what, when (status changes, feedback submitted, notes added)

## Success Criteria

- [ ] Team members can be invited with role-based access
- [ ] Interviewers can submit structured feedback
- [ ] Aggregated scorecards show all feedback side-by-side
- [ ] Hiring workspace replaces email/spreadsheet tracking
- [ ] Activity feed shows all hiring team actions
- [ ] Access scoped by team member permissions

---

# PROMPT 54: Market Intelligence & Compensation Benchmarking

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–53 before making changes.

## Purpose

Give recruiters data-driven ammunition for conversations with hiring managers — real-time compensation benchmarking, time-to-fill benchmarks, and competitive hiring intelligence.

## What to Build

### Part 1: Market Data Aggregation

**File to create:** `services/api/app/services/market_intelligence.py`

Aggregate anonymized data from Winnow's job database:

```python
async def get_salary_benchmarks(title: str, location: str, db: Session) -> dict:
    """
    From all jobs in Winnow's database for similar titles/locations:
    - 25th, 50th, 75th percentile salaries
    - Sample size
    - Trend (up/down/flat vs. 90 days ago)
    """

async def get_time_to_fill_benchmarks(title: str, location: str, db: Session) -> dict:
    """Average time-to-fill for similar roles in similar locations."""

async def get_competitive_landscape(employer_id: UUID, job_id: UUID, db: Session) -> dict:
    """
    How many other employers are hiring for similar roles right now?
    How does this employer's salary compare to market?
    What skills are most in-demand for this role type?
    """
```

### Part 2: Intelligence Router

- `GET /api/employer/intelligence/salary?title=&location=` — salary benchmarks
- `GET /api/employer/intelligence/time-to-fill?title=&location=` — time benchmarks
- `GET /api/employer/intelligence/competitive/{job_id}` — competitive landscape for a job

### Part 3: Frontend — Intelligence Panel

Add a "Market Intelligence" tab to the job detail page:
- Salary benchmark chart (where this job falls vs. market)
- Time-to-fill estimate based on similar roles
- Competitive landscape: how many similar jobs are open, average salary range
- "Adjust Salary" suggestion if below market median

## Success Criteria

- [ ] Salary benchmarks aggregated from Winnow's job database
- [ ] Time-to-fill benchmarks by role and location
- [ ] Competitive landscape shows similar open roles
- [ ] All data anonymized (no employer names in benchmarks)
- [ ] Frontend shows market data on job detail page

---

# PROMPT 55: End-to-End Integration Test & Polish

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 44–54 before making changes.

## Purpose

Verify all strategic gap-exploitation features work together end-to-end. Run through complete employer workflows, fix integration bugs, and ensure the platform is cohesive.

## What to Test

### Workflow 1: Full Distribution Lifecycle
1. Employer creates a job → sets status to 'active'
2. Distribution engine pushes to all connected boards automatically
3. Edit the job → changes sync to all boards within minutes
4. Fill the job → automatically removed from all boards
5. Verify distribution_events audit log is complete

### Workflow 2: Analytics & Attribution
1. Simulate applications from different boards (create analytics events)
2. Verify funnel by board shows correct counts
3. Verify cost-per-quality-hire calculates correctly
4. Check board recommendations are reasonable

### Workflow 3: Candidate Experience
1. Candidate applies to a job via matches
2. Employer changes status to "Interview"
3. Verify candidate receives email notification
4. Verify candidate dashboard shows status update
5. Employer rejects candidate → verify respectful rejection email with similar job suggestions

### Workflow 4: Compliance
1. Post a job without EEO statement → compliance checker flags it
2. Run bias scan on job with gendered language → flags returned
3. Generate OFCCP report → verify all posting/distribution events included
4. Check DEI recommendations appear for jobs with limited applicant diversity

### Workflow 5: Talent Pipeline
1. Fill a job → silver medalists auto-added to pipeline (with consent)
2. Post a new similar job → pipeline suggestions surface relevant candidates
3. Search pipeline by skills → correct results returned

### Workflow 6: Collaboration
1. Invite team member as interviewer
2. Submit interview feedback
3. Verify aggregated scorecard

### Linting & Formatting
```powershell
cd services/api
python -m ruff check . && python -m ruff format .
cd ../../apps/web
npm run lint
```

## Success Criteria

- [ ] All 6 workflows pass end-to-end
- [ ] No broken imports or missing dependencies
- [ ] All new API endpoints return correct responses
- [ ] All new frontend pages render without errors
- [ ] All migrations run cleanly
- [ ] No regressions to existing candidate-side features
- [ ] Linting passes for both Python and TypeScript
