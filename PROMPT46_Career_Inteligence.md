# PROMPT46: Career Intelligence Platform — Employer, Agency & Recruiter Features

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 33–45 before making changes.

## Purpose

Transform Winnow Career Concierge from a candidate-first job matching platform into a **full Career Intelligence Platform** serving three stakeholders: **employers**, **staffing agencies**, and **professional recruiters**. This prompt implements four interlocking systems:

1. **Career Intelligence Engine** — AI-powered tools that give recruiters/employers candidate insights no competitor offers (recruiter briefs, market positioning, salary intelligence, predictive time-to-fill, career trajectory).
2. **Chrome Extension for LinkedIn Sourcing** — A browser extension that lets recruiters source candidates from LinkedIn directly into Winnow with one click.
3. **Employer/Recruiter Feature Comparison Page** — A public-facing comparison matrix (matching the existing candidate-side `/competitive` page) positioning Winnow against Recruit CRM, CATSOne, Bullhorn, and Zoho Recruit.
4. **Universal Migration Toolkit** — A zero-friction data import system that auto-detects the source platform (Bullhorn, Recruit CRM, CATSOne, Zoho Recruit, or generic CSV) and imports everything: candidates, contacts, companies, jobs, placements, emails, notes, activities, tags, parent/child relationships, logos, LinkedIn URLs, custom fields, and full history.

**Design philosophy:** Every feature must be AI-native, explainable, and demonstrate intelligence that legacy ATS/CRM platforms cannot replicate without rebuilding from scratch.

---

## Triggers — When to Use This Prompt

- Building recruiter-facing or employer-facing AI intelligence tools.
- Implementing Chrome extension for LinkedIn candidate sourcing.
- Creating the recruiter/employer competitive comparison page.
- Building the data migration/import system from competitor platforms.
- Product asks for "recruiter tools," "agency features," "migration," "Chrome extension," or "competitive comparison for employers."

---

## What Already Exists (DO NOT recreate — read the codebase first)

### Candidate Side (PROMPTs 1–24)
1. **Auth:** `services/api/app/services/auth.py` — JWT cookies, `get_current_user`
2. **Resume parsing:** `services/api/app/services/profile_parser.py` — PDF/DOCX → structured JSON
3. **Job ingestion:** `services/api/app/services/` + provider adapters
4. **Matching engine:** `services/api/app/services/matching.py` — 6-dimension composite scoring + semantic
5. **Tailored resume:** `services/api/app/services/tailor.py`, `docx_builder.py`
6. **IPS:** in `matching.py`
7. **Application tracking:** `application_tracking` table, status on `matches`
8. **Sieve AI:** `services/api/app/services/sieve.py`, `routers/sieve.py`
9. **Semantic search (pgvector):** embeddings on `jobs` and `candidate_profiles`
10. **Candidate feature comparison:** `apps/web/app/competitive/page.tsx`

### Employer Side (PROMPTs 33–45)
1. **Database:** `employer_profiles`, `employer_jobs`, `employer_candidate_views`, `employer_saved_candidates`
2. **`users.role`:** `'candidate'`, `'employer'`, `'both'`
3. **Models:** `services/api/app/models/employer.py`
4. **Schemas:** `services/api/app/schemas/employer.py`
5. **Routes:** `services/api/app/routers/employer.py`
6. **Employer UI:** `apps/web/app/employer/`
7. **Distribution engine:** `services/api/app/services/distribution.py`, `board_adapters/` (PROMPT44)
8. **Employer subscription:** Stripe (PROMPT39)

### Infrastructure
- **Monorepo:** `apps/web/` (Next.js 14) + `services/api/` (FastAPI) + `infra/` (Docker Compose)
- **Postgres 16 + pgvector**, Redis 7, RQ worker
- **Alembic migrations:** `services/api/alembic/`
- **Anthropic SDK:** already in `requirements.txt`

### Key Conventions
- **Python:** Ruff, 88 char lines, snake_case
- **TypeScript:** Prettier + ESLint
- **Migrations:** `cd services/api && alembic revision --autogenerate -m "description" && alembic upgrade head`
- **Lint:** `cd services/api && python -m ruff check . && python -m ruff format .`
- **Frontend lint:** `cd apps/web && npm run lint`

---

# PART 1 — Career Intelligence Engine

## What It Does

Gives employers, agencies, and recruiters AI-powered candidate intelligence that no competing ATS/CRM provides. These are living, AI-generated strategic insights — not dashboards of static data.

## 1.1 Database — Intelligence Tables

Create an Alembic migration:

```bash
cd services/api && alembic revision --autogenerate -m "add career intelligence tables"
```

**`recruiter_candidate_briefs`** — auto-generated candidate summaries:
- `id` (UUID PK)
- `candidate_profile_id` (FK → candidate_profiles.id, CASCADE)
- `employer_job_id` (FK → employer_jobs.id nullable, CASCADE) — null = general brief
- `generated_by_user_id` (FK → users.id nullable)
- `brief_type` (VARCHAR 50) — `'general'`, `'job_specific'`, `'submittal'`
- `brief_json` (JSONB NOT NULL) — structured brief content
- `brief_text` (TEXT NOT NULL) — plain-text version for copy/paste
- `model_used` (VARCHAR 100)
- `created_at` (TIMESTAMP)

**`market_intelligence`** — salary and market positioning data:
- `id` (UUID PK)
- `scope_type` (VARCHAR 50) — `'role'`, `'industry'`, `'location'`
- `scope_key` (VARCHAR 255) — e.g., `'Software Engineer'`, `'San Francisco'`
- `data_json` (JSONB NOT NULL) — aggregated market data
- `sample_size` (INTEGER)
- `generated_at`, `expires_at` (TIMESTAMP)
- UNIQUE on (scope_type, scope_key)

**`time_to_fill_predictions`** — predictive hiring analytics:
- `id` (UUID PK)
- `employer_job_id` (FK → employer_jobs.id, CASCADE)
- `predicted_days` (INTEGER)
- `confidence` (NUMERIC(3,2)) — 0.00–1.00
- `factors_json` (JSONB)
- `actual_days` (INTEGER nullable) — for model feedback loop
- `created_at` (TIMESTAMP)

**`career_trajectories`** — candidate career path predictions:
- `id` (UUID PK)
- `candidate_profile_id` (FK → candidate_profiles.id, CASCADE)
- `trajectory_json` (JSONB NOT NULL) — predicted roles, salary ranges, skills
- `model_used` (VARCHAR 100)
- `created_at`, `expires_at` (TIMESTAMP)

Indexes on: `recruiter_candidate_briefs(candidate_profile_id, employer_job_id)`, `market_intelligence(scope_type, scope_key)`, `time_to_fill_predictions(employer_job_id)`.

## 1.2 SQLAlchemy Models

**File to create:** `services/api/app/models/career_intelligence.py`

Create models for `RecruiterCandidateBrief`, `MarketIntelligence`, `TimeFillPrediction`, `CareerTrajectory`. Import in `services/api/app/models/__init__.py`.

## 1.3 Career Intelligence Service

**File to create:** `services/api/app/services/career_intelligence.py`

This is the crown jewel of the platform. Six capabilities:

### Capability 1: Recruiter Candidate Brief Generator

```python
async def generate_candidate_brief(
    candidate_profile_id: UUID,
    employer_job_id: UUID | None,
    brief_type: str,  # 'general', 'job_specific', 'submittal'
    db: Session,
) -> dict:
```

When a recruiter views a candidate, Winnow generates a structured brief for client emails or ATS notes.

**Brief types:**
- `general`: 1-paragraph elevator pitch + structured summary. For browsing without a specific job.
- `job_specific`: Matches candidate against a job. Includes fit rationale, skill alignment, gap analysis, and why they should be interviewed.
- `submittal`: Client-ready document. Everything in `job_specific` plus formatted for email/PDF.

**Output schema (return as JSON):**
```json
{
    "elevator_pitch": "2-3 sentence punchy summary",
    "headline": "Senior Backend Engineer | 8 YoE | Python/Go | Fintech",
    "strengths": ["Evidence-backed strength 1", "..."],
    "concerns": ["Honest gap 1", "..."],
    "fit_rationale": "Why they fit THIS job (null for general)",
    "skills_alignment": {
        "matched": [{"skill": "Python", "evidence": "Led 3-person team building payment APIs in Python for 4 years"}],
        "missing": [{"skill": "Kubernetes", "severity": "nice_to_have"}]
    },
    "compensation_note": "Targeting $160K, job range is $140-180K — aligned",
    "availability": "2 weeks notice",
    "recommended_action": "Interview immediately",
    "full_text": "Complete formatted brief for copy/paste"
}
```

**Implementation approach:**
- Load candidate profile (`profile_json`) and optionally the job + existing match data.
- Call Claude (Anthropic API, already in requirements.txt) with a system prompt that enforces grounding: "NEVER fabricate — every claim must come from the candidate data."
- Persist result to `recruiter_candidate_briefs` table.
- Use `claude-sonnet-4-5-20250514` for cost efficiency.

### Capability 2: Market Position Score (Percentile)

```python
async def compute_market_position(
    candidate_profile_id: UUID,
    employer_job_id: UUID,
    db: Session,
) -> dict:
```

Shows where a candidate ranks vs. all other applicants for the same role. Returns percentile, strengths vs. field, weaknesses vs. field.

**Implementation:** Query all matches for the job, sort by `match_score`, find the target candidate's position, compute percentile.

### Capability 3: Salary Intelligence Engine

```python
async def salary_intelligence(
    role_title: str,
    location: str | None,
    db: Session,
) -> dict:
```

Aggregates anonymized salary data from active jobs. Returns percentile bands (P10/P25/P50/P75/P90), remote premium, trend direction.

**Implementation:** Query `jobs` table for matching titles with salary data. Compute percentiles from midpoints. Cache in `market_intelligence` table with 7-day expiry.

### Capability 4: Predictive Time-to-Fill

```python
async def predict_time_to_fill(
    employer_job_id: UUID,
    db: Session,
) -> dict:
```

Predicts days to fill based on role type, salary competitiveness, remote policy, applicant pipeline, and historical data. Returns prediction with confidence interval and factor breakdown.

**Implementation:** Compare job attributes against historical closed jobs. Compute base estimate, adjust by factors (salary vs. market, remote policy, pipeline volume). Persist to `time_to_fill_predictions`.

### Capability 5: Career Trajectory Prediction

```python
async def predict_career_trajectory(
    candidate_profile_id: UUID,
    db: Session,
) -> dict:
```

Predicts what roles and salary ranges will open up for a candidate in 6-12 months. Uses Claude to analyze career progression rate and skill growth.

### Capability 6: Employer Notification on High-IPS Match

```python
async def notify_employer_high_match(
    employer_job_id: UUID,
    candidate_profile_id: UUID,
    match_score: float,
    db: Session,
) -> None:
```

When a candidate matches a job at IPS 80+, auto-generate a brief and queue a notification to the employer. Wire this into `matching.py` as a post-match hook.

## 1.4 Career Intelligence Router

**File to create:** `services/api/app/routers/career_intelligence.py`

Endpoints (require employer/recruiter role via `require_employer_or_recruiter` dependency):

- `POST /api/intelligence/brief/{candidate_profile_id}` — generate brief (query params: `job_id`, `brief_type`)
- `GET /api/intelligence/market-position/{candidate_profile_id}/{job_id}` — percentile ranking
- `GET /api/intelligence/salary?role=&location=` — salary intelligence
- `GET /api/intelligence/time-to-fill/{job_id}` — time-to-fill prediction
- `GET /api/intelligence/trajectory/{candidate_profile_id}` — career trajectory (available to candidates and recruiters)

**Register in `services/api/app/main.py`:**
```python
from app.routers.career_intelligence import router as intelligence_router
app.include_router(intelligence_router)
```

## 1.5 Frontend — Intelligence Dashboard

**File to create:** `apps/web/app/employer/intelligence/page.tsx`

Build a page at `/employer/intelligence` with four panels:

1. **Candidate Brief Generator** — Select candidate + optional job → "Generate Brief" → displays structured brief with "Copy to Clipboard" (copies `full_text`).
2. **Salary Intelligence** — Role + location input → percentile bar chart (Recharts) + market insight.
3. **Time-to-Fill Predictor** — Select active job → predicted days with confidence band, color-coded factor cards, suggestions.
4. **Market Position** — Candidate-job pair → percentile gauge, strengths/weaknesses vs. field.

Add "Intelligence" link to employer sidebar navigation.

## 1.6 Success Criteria — Part 1

- [ ] Recruiter can generate general, job-specific, and submittal briefs with one click
- [ ] Brief content is grounded — zero fabricated claims
- [ ] "Copy to Clipboard" works for full brief text
- [ ] Market position shows percentile against actual applicant pool
- [ ] Salary intelligence returns percentile bands from real job data
- [ ] Time-to-fill prediction with factor breakdown and suggestions
- [ ] Career trajectory returns realistic 6/12-month role predictions
- [ ] High-IPS match triggers employer notification with auto-generated brief
- [ ] All intelligence data persisted for audit and improvement

---

# PART 2 — Chrome Extension for LinkedIn Sourcing

## What It Does

A Manifest V3 Chrome extension that lets recruiters source candidates from LinkedIn profile pages into Winnow with one click. Captures publicly visible data and creates a candidate record.

## 2.1 Extension Structure

**Directory to create:** `apps/chrome-extension/`

```
apps/chrome-extension/
├── manifest.json
├── popup/
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
├── content/
│   └── linkedin.js         # Injected into linkedin.com/in/* pages
├── background/
│   └── service-worker.js
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md
```

## 2.2 manifest.json (Manifest V3)

```json
{
  "manifest_version": 3,
  "name": "Winnow Career Concierge — LinkedIn Sourcer",
  "version": "1.0.0",
  "description": "Source candidates from LinkedIn directly into Winnow.",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["https://www.linkedin.com/*"],
  "action": { "default_popup": "popup/popup.html" },
  "content_scripts": [{
    "matches": ["https://www.linkedin.com/in/*"],
    "js": ["content/linkedin.js"],
    "run_at": "document_idle"
  }],
  "background": { "service_worker": "background/service-worker.js" }
}
```

## 2.3 Content Script — `content/linkedin.js`

Extracts publicly visible data from LinkedIn profile DOM:
- Full name, headline, location, profile photo URL
- Current company
- Experience entries (title, company, dates)
- Education entries (school, degree)
- Skills (visible skills section)
- LinkedIn profile URL

**Critical:** Only reads what the logged-in recruiter can already see. Does NOT bypass authentication, access private data, or violate platform ToS. Content is extracted from DOM elements only.

The content script listens for a `chrome.runtime.onMessage` with action `"extractProfile"` and responds with the extracted data object.

## 2.4 Popup — `popup/popup.html` + `popup.js`

**States:**
1. **Not connected** — Shows API URL + token fields and "Connect" button. Stores in `chrome.storage.local`.
2. **Connected, not on LinkedIn** — Shows "Navigate to a LinkedIn profile to use Winnow Sourcer."
3. **Connected, on LinkedIn** — Shows "Extract Profile" button. After extraction: shows preview (photo, name, headline, location) + job selector dropdown (loads employer's active jobs from API) + "Save to Winnow" button.

**Popup.js flow:**
1. On load, check `chrome.storage.local` for `apiUrl` and `apiToken`.
2. Check if active tab URL contains `linkedin.com/in/`.
3. "Extract Profile" sends message to content script, receives profile data, displays preview.
4. "Save to Winnow" POSTs to `/api/intelligence/source/linkedin` with `{profile, tag_job_id}`.

## 2.5 Backend Endpoint

Add to `services/api/app/routers/career_intelligence.py`:

```python
@router.post("/source/linkedin")
async def source_from_linkedin(payload: dict, user=Depends(require_employer_or_recruiter), db=Depends(get_db)):
```

**Logic:**
1. Check if candidate exists by `linkedin_url` match in `profile_json.basics.linkedin_url`.
2. If exists: merge new data (update photo, headline, add new skills without duplicating). Increment version.
3. If new: create `User` (with `is_sourced=True`, `sourced_by=user.id`) + `CandidateProfile`.
4. Convert LinkedIn extract to Winnow `profile_json` schema (map fields).
5. If `tag_job_id` provided, enqueue match computation.
6. Queue embedding generation.
7. Return `{candidate_id, status: "created"|"updated", linkedin_url}`.

## 2.6 Success Criteria — Part 2

- [ ] Extension installs in Chrome and shows popup
- [ ] Content script extracts name, headline, location, experience, education, skills from LinkedIn profiles
- [ ] Popup shows preview before saving
- [ ] Save creates/updates candidate in Winnow database
- [ ] Dedup works — saving same LinkedIn profile twice updates, not duplicates
- [ ] Job tagging works — extracted candidate gets matched against selected job
- [ ] Embedding generation queued for imported profiles

---

# PART 3 — Employer/Recruiter Feature Comparison Page

## What It Does

A public-facing comparison at `/competitive/employers` positioning Winnow against Recruit CRM, CATSOne, Bullhorn, and Zoho Recruit. Same interactive matrix design as existing candidate comparison at `/competitive`.

## 3.1 Create the Page

**File to create:** `apps/web/app/competitive/employers/page.tsx`

Model EXACTLY after the existing `apps/web/app/competitive/page.tsx` structure. Must be a `"use client"` React component.

### Competitor Configuration

```tsx
const COMPETITORS = [
  { key: "winnow", name: "Winnow", highlight: true, type: "career_intelligence" },
  { key: "recruitcrm", name: "Recruit CRM", type: "ats_crm" },
  { key: "catsone", name: "CATSOne", type: "ats_crm" },
  { key: "bullhorn", name: "Bullhorn", type: "ats_crm" },
  { key: "zoho", name: "Zoho Recruit", type: "ats_crm" },
];
```

Type labels: `career_intelligence` → "Career Intelligence Platform" (green badge), `ats_crm` → "ATS + CRM" (blue badge).

### Feature Categories and Data

**Category: AI & Candidate Intelligence (11 features)**

| Feature | Winnow | RecruitCRM | CATSOne | Bullhorn | Zoho |
|---------|--------|------------|---------|----------|------|
| AI candidate scoring & match explanation | full | none | none | partial | partial |
| Interview Probability Score (IPS) | full | none | none | none | none |
| Skill gap analysis with evidence | full | none | none | none | none |
| Auto-generated recruiter candidate briefs | full | none | none | none | none |
| Predictive time-to-fill | full | none | none | none | none |
| Salary intelligence engine | full | none | none | none | none |
| Market position (percentile) scoring | full | none | none | none | none |
| Career trajectory prediction | full | none | none | none | none |
| AI-grounded resume tailoring for candidates | full | none | none | none | none |
| Semantic search (pgvector embeddings) | full | none | none | partial | partial |
| Sieve AI concierge (proactive assistant) | full | none | none | none | none |

**Category: Job Distribution & Management (8 features)**

| Feature | Winnow | RecruitCRM | CATSOne | Bullhorn | Zoho |
|---------|--------|------------|---------|----------|------|
| One-click multi-board distribution | full | full | partial | full | partial |
| Auto-sync edits to all boards | full | partial | none | partial | none |
| Auto-remove on close/pause | full | partial | none | partial | none |
| Per-board content optimization (AI) | full | none | none | none | none |
| Job posting bias detection | full | none | none | none | none |
| AI-powered .docx job parsing | full | none | none | none | none |
| Cross-board analytics & attribution | full | partial | none | partial | partial |
| Real-time distribution status tracking | full | partial | none | partial | none |

**Category: Recruiter CRM & Pipeline (8 features)**

| Feature | Winnow | RecruitCRM | CATSOne | Bullhorn | Zoho |
|---------|--------|------------|---------|----------|------|
| Client/company CRM pipeline | partial | full | partial | full | full |
| Email sequences & drip campaigns | partial | partial | none | none | partial |
| Multi-channel outreach (email+SMS+LinkedIn) | partial | partial | none | none | partial |
| Chrome extension for LinkedIn sourcing | full | full | partial | full | partial |
| Invoicing & back-office billing | none | full | none | full | partial |
| Kanban pipeline view | full | full | full | full | full |
| Candidate hotlists & tags | full | full | full | full | full |
| Activity logging & notes | full | full | full | full | full |

**Category: Trust, Compliance & Quality (6 features)**

| Feature | Winnow | RecruitCRM | CATSOne | Bullhorn | Zoho |
|---------|--------|------------|---------|----------|------|
| Automated trust scoring (candidate) | full | none | none | none | none |
| 14-signal job fraud detection | full | none | none | none | none |
| OFCCP compliance reporting | full | none | none | partial | none |
| DEI sourcing recommendations | full | none | none | none | none |
| GDPR full data export + deletion | full | partial | partial | partial | partial |
| Privacy-respecting candidate search | full | none | none | none | none |

**Category: Migration & Platform (7 features)**

| Feature | Winnow | RecruitCRM | CATSOne | Bullhorn | Zoho |
|---------|--------|------------|---------|----------|------|
| Zero-friction migration toolkit | full | partial | none | partial | partial |
| Auto-detect source platform | full | none | none | none | none |
| Import history, notes, activities | full | partial | none | partial | partial |
| Mobile app (native) | full | full | none | partial | partial |
| Transparent flat-rate pricing | full | full | full | none | full |
| No implementation fees | full | full | full | none | full |
| Open API | full | full | partial | full | full |

### Score Computation

Same logic as candidate comparison page: `full` = 1, `partial` = 0.5, `none` = 0. Sort columns by score descending. Winnow always first.

### Methodology Note

```
Scores reflect publicly documented features as of February 2026.
Full = built-in and production-ready. Partial = limited, requires add-ons, or needs third-party tools. None = not available.
Winnow scores include features in active development. Competitive data sourced from vendor docs, user reviews, and independent analysis.
```

## 3.2 Navigation Tabs

**File to modify:** `apps/web/app/competitive/page.tsx`

Add tab links at the top of the existing page:

```tsx
<div className="flex gap-4 mb-8">
  <Link href="/competitive" className="text-lg font-bold border-b-2 border-blue-500">For Candidates</Link>
  <Link href="/competitive/employers" className="text-lg text-gray-400 hover:text-white">For Employers & Recruiters</Link>
</div>
```

Add same tabs (active state reversed) to the new employer page.

## 3.3 Success Criteria — Part 3

- [ ] Page renders at `/competitive/employers` with interactive matrix
- [ ] All 5 categories display correctly with accurate data
- [ ] Score cards compute and sort correctly
- [ ] Category filter buttons work (All, AI features, CRM features, etc.)
- [ ] Tab navigation between candidate and employer comparison pages works
- [ ] Mobile responsive
- [ ] Methodology note present at bottom

---

# PART 4 — Universal Migration Toolkit

## What It Does

A zero-friction import system. The user uploads a data export file (or provides API credentials). Winnow **automatically detects** the source platform, maps every field, and imports everything without manual field mapping.

**Import entities:** Candidates, contacts, companies/clients, jobs/requisitions, placements/hires, notes, activities, emails, tags, custom fields, logos, LinkedIn URLs, parent/child relationships, and full history.

## 4.1 Database — Migration Tables

Add Alembic migration:

**`migration_jobs`** — tracks each import operation:
- `id` (UUID PK)
- `user_id` (FK → users.id)
- `source_platform` (VARCHAR 50) — `'bullhorn'`, `'recruitcrm'`, `'catsone'`, `'zoho'`, `'csv_generic'`, `'auto_detected'`
- `source_platform_detected` (VARCHAR 50 nullable)
- `status` (VARCHAR 50) — `'pending'`, `'analyzing'`, `'mapping'`, `'importing'`, `'validating'`, `'complete'`, `'failed'`, `'partial'`
- `config_json` (JSONB) — import settings
- `stats_json` (JSONB) — running stats per entity type
- `error_log` (JSONB) — array of errors
- `source_file_path` (VARCHAR 500 nullable)
- `api_credentials_encrypted` (TEXT nullable)
- `started_at`, `completed_at`, `created_at`, `updated_at`

**`migration_entity_map`** — tracks every imported entity for rollback and dedup:
- `id` (UUID PK)
- `migration_job_id` (FK → migration_jobs.id, CASCADE)
- `source_entity_type` (VARCHAR 50) — `'candidate'`, `'company'`, `'contact'`, `'job'`, `'placement'`, `'note'`, `'activity'`, `'email'`
- `source_entity_id` (VARCHAR 255)
- `winnow_entity_type` (VARCHAR 50)
- `winnow_entity_id` (UUID)
- `parent_source_id` (VARCHAR 255 nullable) — for parent/child relationships
- `raw_data` (JSONB) — original data for audit
- `status` (VARCHAR 50) — `'imported'`, `'merged'`, `'skipped'`, `'error'`
- `error_message` (TEXT nullable)
- `created_at`
- Index on (migration_job_id, source_entity_type, source_entity_id)

## 4.2 Platform Fingerprinting Service

**File to create:** `services/api/app/services/migration/platform_detector.py`

**This is the magic.** Given a CSV, JSON, or ZIP file, it determines which platform exported it.

### Platform Signatures

Each platform produces exports with unique fingerprints:

| Platform | CSV Header Fingerprints | Filename Patterns |
|----------|------------------------|-------------------|
| Bullhorn | `candidateID`, `firstName`, `lastName`, `businessSectors`, `isDeleted`, `clientCorporationID` | `bullhorn`, `bh_export` |
| Recruit CRM | `Candidate Name`, `Email`, `Pipeline Stage`, `Hot Degree`, `Candidate Owner` | `recruitcrm`, `rcrm_` |
| CATSOne | `first_name`, `last_name`, `cats_id`, `entered_by`, `hot_candidate` | `cats`, `catsone` |
| Zoho Recruit | `First Name`, `Last Name`, `RECRUITID`, `Modified Time`, `Candidate Owner` | `zoho`, `recruit_` |

**Detection algorithm:**
1. **Filename scoring** — match against known filename patterns (+0.2 confidence).
2. **Header scoring** — match required headers (+0.5) and optional headers (+0.3 weighted).
3. **ZIP structure** — scan internal filenames for entity patterns (candidates.csv, clientCorporation.csv, etc.).
4. **JSON keys** — match top-level or first-item keys against signatures.
5. **Threshold** — if best platform score < 0.5, fall back to `generic` with AI-assisted mapping.

**Function signature:**
```python
def detect_platform(file_path: str) -> dict:
    """
    Returns {
        "platform": "bullhorn" | "recruitcrm" | "catsone" | "zoho_recruit" | "generic",
        "confidence": 0.0-1.0,
        "evidence": ["Header 'candidateID' matches Bullhorn", ...],
        "entity_types_found": ["candidate", "company", "job"],
        "row_count": 1547,
        "field_mapping": {...}
    }
    """
```

### Complete Field Mappings

Build exhaustive field mappings in a `FIELD_MAPPINGS` dict for all four platforms. Key mappings per platform:

**Bullhorn candidate:** `candidateID` → source_id, `firstName` → basics.first_name, `lastName` → basics.last_name, `email` → basics.email, `companyName` → basics.current_company, `skillList` → skills.raw_text, `linkedPersonID` → relationships.parent_id, `salary` → preferences.salary_current, `customText1-20` → custom_fields.

**Bullhorn company:** `clientCorporationID` → source_id, `name` → company_name, `companyURL` → website, `industry` → industry.

**Bullhorn job:** `jobOrderID` → source_id, `title` → title, `clientCorporationID` → company_source_id (for relationship resolution).

**Bullhorn placement:** `placementID` → source_id, `candidateID` → candidate_source_id, `jobOrderID` → job_source_id.

**Recruit CRM candidate:** `Candidate Name` → _full_name (split to first/last), `Email` → basics.email, `LinkedIn` → basics.linkedin_url, `Pipeline Stage` → source.status.

**CATSOne candidate:** `first_name` → basics.first_name, `cats_id` → source_id, `key_skills` → skills.raw_text.

**Zoho Recruit candidate:** `First Name` → basics.first_name, `RECRUITID` → source_id, `Skill Set` → skills.raw_text.

## 4.3 Import Engine

**File to create:** `services/api/app/services/migration/import_engine.py`

### Import Pipeline

```python
async def run_migration(migration_job_id: UUID, db: Session) -> dict:
```

**Steps:**
1. Load migration job config.
2. Detect platform (if `auto_detected`).
3. Parse source files (CSV/JSON/ZIP → entity-typed dicts).
4. Import in dependency order: **companies → contacts → candidates → jobs → placements → notes → activities → emails**.
5. Resolve parent/child relationships using `entity_map` (source_id → winnow_id).
6. Handle duplicates: dedup candidates by email, companies by name, contacts by email.
7. Queue embedding generation for all imported candidates.
8. Update `migration_job.stats_json` with per-entity counts.
9. Commit in batches of 100 rows.

### Entity Import Functions

For each entity type, implement an `_import_X` function that:
1. Applies field mapping (`_apply_field_mapping` using dot-notation paths like `basics.first_name`).
2. Checks for duplicates (by email for candidates/contacts, by name for companies).
3. If duplicate found: merges new data into existing record without overwriting user edits.
4. If new: creates User + CandidateProfile (for candidates), EmployerProfile (for companies), etc.
5. Returns the Winnow entity ID.
6. Records in `migration_entity_map` for audit and rollback.

### AI-Assisted Generic Mapping (Fallback)

For `generic` platform detection, use Claude to analyze column headers and sample data:

```python
async def ai_assisted_mapping(headers: list[str], sample_rows: list[dict]) -> dict:
    """
    When auto-detection fails, use Claude to infer field mappings.
    Send headers + 3 sample rows. Claude returns a mapping dict.
    """
```

This makes the toolkit work even with completely unknown CSV formats.

### Relationship Resolution

After all entities are imported:

```python
def _resolve_relationships(migration_job_id, entity_map, db):
    """
    Walk through migration_entity_map and resolve parent/child references.
    E.g., Bullhorn's linkedPersonID or clientCorporationID on candidates.
    """
```

For each entity with a `parent_source_id`, look up the Winnow ID in `entity_map` and create the relationship (e.g., assign candidate to company, link contact to company).

## 4.4 Migration Router

**File to create:** `services/api/app/routers/migration.py`

Endpoints (require employer/recruiter/admin role):

- `POST /api/migration/upload` — upload file (multipart form), save to temp storage, detect platform, return `{migration_job_id, detected_platform, confidence, entity_types, row_count}`.
- `GET /api/migration/{id}` — get migration job status and stats.
- `POST /api/migration/{id}/start` — begin the import (enqueue RQ job). Optional `config_json` body for overrides (skip certain entity types, conflict resolution strategy).
- `GET /api/migration/{id}/preview` — returns first 5 rows per entity type with mapped field names for user review before committing.
- `POST /api/migration/{id}/rollback` — delete all entities created by this migration job (using `migration_entity_map`).
- `GET /api/migration/{id}/errors` — paginated error log.
- `GET /api/migration/history` — list all migration jobs for current user.

**Register in `services/api/app/main.py`:**
```python
from app.routers.migration import router as migration_router
app.include_router(migration_router)
```

## 4.5 Frontend — Migration Wizard

**File to create:** `apps/web/app/employer/migrate/page.tsx`

Build a 4-step wizard at `/employer/migrate`:

### Step 1: Upload
- Drag-and-drop file upload zone (accepts `.csv`, `.json`, `.zip`, `.xlsx`).
- "Or connect via API" option — fields for platform selector, API URL, API key.
- Shows supported platforms with logos: Bullhorn, Recruit CRM, CATSOne, Zoho Recruit.
- Upload button triggers `POST /api/migration/upload`.

### Step 2: Detection & Preview
- After upload, shows auto-detected platform with confidence badge ("Bullhorn detected — 94% confidence").
- Shows entity counts: "Found 1,547 candidates, 342 companies, 89 jobs, 45 placements."
- Shows preview table: first 5 rows per entity with Winnow field mapping highlighted.
- "Override Platform" dropdown (in case auto-detection is wrong).
- "Start Import" button.

### Step 3: Import Progress
- Real-time progress bar per entity type (polls `GET /api/migration/{id}` every 2 seconds).
- Shows: Candidates (480/500 ✓), Companies (340/342 ✓), Jobs (importing... 45/89).
- Error counter with expandable error log.

### Step 4: Summary
- Import complete summary: imported counts, skipped (duplicates), errors.
- "View Imported Candidates" button → navigates to `/employer/candidates`.
- "Rollback Import" button (with confirmation dialog).

Add "Migrate Data" link to employer sidebar navigation.

## 4.6 Success Criteria — Part 4

- [ ] Upload CSV/JSON/ZIP triggers auto-detection
- [ ] Bullhorn export detected with > 0.8 confidence
- [ ] Recruit CRM export detected with > 0.8 confidence
- [ ] CATSOne export detected with > 0.6 confidence
- [ ] Zoho Recruit export detected with > 0.8 confidence
- [ ] Unknown formats fall back to AI-assisted mapping
- [ ] Candidates imported with full profile_json including skills, experience, education
- [ ] Companies imported with name, website, industry, contacts
- [ ] Jobs imported and linked to companies
- [ ] Placements imported and linked to candidates + jobs
- [ ] Duplicate candidates (same email) merged, not duplicated
- [ ] Parent/child relationships resolved after import
- [ ] LinkedIn URLs preserved
- [ ] Custom fields preserved in profile_json.custom_fields
- [ ] Embeddings generated for all imported candidates
- [ ] Rollback deletes all entities created by that migration
- [ ] Preview shows mapped data before committing
- [ ] Progress updates in real-time during import
- [ ] Error log accessible with row-level detail

---

# File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Intelligence models | `services/api/app/models/career_intelligence.py` | CREATE |
| Intelligence service | `services/api/app/services/career_intelligence.py` | CREATE |
| Intelligence router | `services/api/app/routers/career_intelligence.py` | CREATE |
| Intelligence dashboard | `apps/web/app/employer/intelligence/page.tsx` | CREATE |
| Chrome extension | `apps/chrome-extension/` (full directory) | CREATE |
| Employer comparison page | `apps/web/app/competitive/employers/page.tsx` | CREATE |
| Candidate comparison (tabs) | `apps/web/app/competitive/page.tsx` | MODIFY — add tab links |
| Platform detector | `services/api/app/services/migration/platform_detector.py` | CREATE |
| Import engine | `services/api/app/services/migration/import_engine.py` | CREATE |
| Migration models | `services/api/app/models/migration.py` | CREATE |
| Migration router | `services/api/app/routers/migration.py` | CREATE |
| Migration wizard UI | `apps/web/app/employer/migrate/page.tsx` | CREATE |
| API main | `services/api/app/main.py` | MODIFY — register 2 new routers |
| Models __init__ | `services/api/app/models/__init__.py` | MODIFY — import new models |
| Alembic migration | `services/api/alembic/versions/` | CREATE (auto-generated) |

---

# Implementation Order (for Cursor)

### Phase 1: Database + Models (30 min)
1. Create Alembic migration with all new tables (intelligence + migration).
2. Create `career_intelligence.py` and `migration.py` model files.
3. Import in `__init__.py`. Run `alembic upgrade head`.

### Phase 2: Career Intelligence Engine (2-3 hours)
4. Create `services/career_intelligence.py` with all 6 capabilities.
5. Create `routers/career_intelligence.py` with all endpoints.
6. Register router in `main.py`.
7. Create `apps/web/app/employer/intelligence/page.tsx`.

### Phase 3: Chrome Extension (1-2 hours)
8. Create `apps/chrome-extension/` directory and all files.
9. Add `/source/linkedin` endpoint to intelligence router.
10. Test: load extension in Chrome, navigate to LinkedIn, extract and save.

### Phase 4: Comparison Page (1-2 hours)
11. Create `apps/web/app/competitive/employers/page.tsx`.
12. Add tab navigation to existing `competitive/page.tsx`.
13. Verify scoring and sorting.

### Phase 5: Migration Toolkit (3-4 hours)
14. Create `services/migration/platform_detector.py` with all platform signatures.
15. Create `services/migration/import_engine.py` with full pipeline.
16. Create `routers/migration.py` with all endpoints.
17. Create `apps/web/app/employer/migrate/page.tsx` wizard.
18. Test with sample Bullhorn and Recruit CRM exports.

### Phase 6: Verification (1 hour)
19. Run full lint: `cd services/api && python -m ruff check . && python -m ruff format .`
20. Run frontend lint: `cd apps/web && npm run lint`
21. Test all API endpoints via `/docs`.
22. Test Chrome extension end-to-end.
23. Test migration with sample data files.
24. Verify employer comparison page renders correctly.

---

## Version

**PROMPT46_Career_Inteligence v1.0**
Last updated: 2026-02-11
