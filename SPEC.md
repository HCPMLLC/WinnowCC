# SPEC.md — Resume-to-Jobs Consumer SaaS (Web + Mobile) v1

**Project Name (working):** ResumeMatch  
**Audience:** Consumer (any job seeker)  
**Timeline Target:** 6 months to public launch  
**Platforms:** Web app (desktop-first), Mobile app (iOS/Android via Expo), Cloud-hosted backend  
**Primary Goal:** Help users get more interviews by turning their resume into a structured profile, matching to jobs, and generating ATS-safe tailored resumes with transparent reasoning.

---

## 1) Product Positioning: Competitive Exploit Opportunities (Must-Include)

This product explicitly exploits common weaknesses in ZipRecruiter, LinkedIn, Indeed, Monster:

1. **Shallow candidate understanding → Living Profile**
   - Resume is parsed into a **structured candidate profile** (editable, persistent, continuously improved).
2. **One-size-fits-all applying → Per-job tailoring**
   - Generate a job-specific resume variant **optimized for the job** and **ATS-safe by default**.
3. **Opaque matching → Explainable scores**
   - Every job match includes **why it matched** and **what’s missing**.
4. **Clicks over outcomes → Interview readiness**
   - Provide an **Interview Readiness Score** (heuristic, explainable; not a guaranteed probability).
5. **Fragmented workflow → One dashboard**
   - Search → match → tailor → track applications in one place.
6. **Low trust → Grounded generation + audit trail**
   - Tailored content must be grounded in user-provided experience.
   - Provide **change log** and **source grounding** (what text came from which role/bullet).

These are not “nice-to-haves.” They are core requirements.

---

## 2) Core User Flows (MVP)

### Flow A — Onboarding + Profile
1. User signs up / logs in
2. Uploads resume (PDF/DOCX)
3. System extracts a **Candidate Profile**
4. User reviews/edits:
   - target roles/titles
   - locations/remote preference
   - job type (FT/PT/contract)
   - expected salary range
   - industries (optional)
   - “must-have” vs “nice-to-have” skills (optional)

### Flow B — Job Matching
1. User clicks “Find Matches”
2. System fetches jobs from supported sources
3. System scores & ranks jobs
4. Dashboard shows:
   - Match Score (0–100)
   - Interview Readiness Score (0–100)
   - Reasons (top 3–7)
   - Gaps (skills/requirements missing)
   - Filters (location, remote, salary, date posted, source)

### Flow C — Tailored Resume Generation
1. User opens a job match
2. Click “Generate ATS Resume”
3. System outputs:
   - DOCX (required)
   - PDF (optional)
   - A “What Changed” summary + change log

### Flow D — Tracking (MVP-lite)
1. User marks job: saved / applied / interviewing / rejected / offer
2. Notes + links (minimal)

---

## 3) MVP Feature Requirements

### 3.1 Resume Upload & Parsing
- Accept: PDF, DOCX
- Store original file in object storage
- Extract text reliably
- LLM-assisted extraction into strict JSON schema:
  - Basics: name, email, phone, location, links
  - Experience: companies, titles, dates, bullets, technologies
  - Education & certs
  - Skills (normalized keywords)
- Must support user editing/corrections
- Maintain parsing traceability:
  - For each extracted item, store “source snippet” reference where feasible

### 3.2 Candidate Profile (Living Profile)
- Canonical, editable profile object with versioning:
  - `profile_version` increments on update
- Preferences explicitly captured (not inferred silently)
- Inferred suggestions allowed but must be labeled “Suggested” and user-confirmed

### 3.3 Job Ingestion (MVP scope)
- Start with 1–2 legitimate sources (API/feeds/aggregator)
- Normalize to a common Job schema
- Deduplicate postings (source id/url + content hash)
- Store job text + metadata
- Create embeddings for semantic matching

### 3.4 Matching + Explainability
Provide two scores:

**A) Match Score (0–100)**
- Weighted blend:
  - skill overlap (must-have weighted higher)
  - title similarity / taxonomy mapping
  - location fit + remote constraints
  - salary fit (if available)
  - seniority / YOE signals (heuristic)

**B) Interview Readiness Score (0–100)**
- Heuristic (not a claim of guaranteed probability)
- Inputs:
  - match score
  - evidence strength (resume contains concrete bullets supporting required skills)
  - gap severity (missing must-haves)
  - posting recency (small boost)

**Explainability Requirements**
- Show:
  - matched skills (top N)
  - missing/weak skills (top N)
  - which experience bullets support the match
  - preference fits (remote/location/salary/job type)

### 3.5 Tailored Resume (ATS-safe)
- Generate job-specific resume variant grounded in:
  - candidate profile
  - original resume bullets
  - user edits
- Do NOT invent employers, titles, degrees, dates, certifications, or tools not present
- Resume format rules:
  - single column
  - standard headings
  - no tables/text boxes/icons
  - consistent date formats
- Output:
  - DOCX required
  - PDF optional
- Provide:
  - change log: list of modified sections + rationale
  - “keyword alignment” summary (truthful)

### 3.6 Dashboard
- Tabs:
  - Profile
  - Matches
  - Resumes
  - Tracking
- Match list with filters and sorting
- Job detail page:
  - description
  - reasons/gaps
  - generate tailored resume
  - save/apply status

### 3.7 Subscription (defer tier specifics)
- Must support:
  - free trial or limited free plan
  - paid subscription (Stripe)
  - usage limits (e.g., tailored resumes / month)
- Billing integration should be designed early but can be activated late.

---

## 4) Non-Goals (for v1)
- “All job boards” coverage claim (v1: limited supported sources)
- Auto-apply / applying on user’s behalf
- Guaranteed interview probability claims
- Heavy recruiter/employer features
- Complex desktop native app (web-first; optional wrapper later)

---

## 5) Safety, Privacy, Compliance (Hard Requirements)
- PII protection:
  - encryption in transit (TLS)
  - encryption at rest for storage
- No resume text in logs
- Data retention:
  - user can delete account and all data
  - export profile and generated resumes
- Demographics:
  - only if user explicitly provides it
  - must be separated and not used for ranking by default
- LLM grounding:
  - generation must cite which user-provided content it is derived from (internal traceability)

---

## 6) Tech Stack (Recommended)

### Frontend
- Web: Next.js (React), TypeScript
- Mobile: React Native + Expo, TypeScript
- Shared UI patterns, separate apps

### Backend
- Python FastAPI
- Postgres (with pgvector)
- Redis (queues/caching)
- Worker system for background tasks (Celery/RQ)

### Storage
- Cloud object storage for resumes (Google Cloud Storage if using GCP, S3 if AWS)

### Cloud (default)
- **Google Cloud**:
  - Cloud Run (API)
  - Cloud SQL (Postgres)
  - Memorystore (Redis) or Redis on VM (MVP)
  - GCS bucket
  - Cloud Scheduler (cron) for ingestion jobs
  - Secret Manager

---

## 7) Data Model (High-Level)

### User
- id, email, auth_provider, created_at

### ResumeDocument
- id, user_id
- original_file_url
- extracted_text (or pointer)
- uploaded_at

### CandidateProfile
- id, user_id, version
- basics JSON
- experience JSON[]
- education JSON[]
- skills JSON[]
- preferences JSON
- updated_at

### Job
- id
- source, source_job_id, url
- title, company, location, remote_flag
- salary_min, salary_max, currency (nullable)
- description_text
- embedding vector
- posted_at, ingested_at
- content_hash

### Match
- id, user_id, job_id, profile_version
- match_score, readiness_score
- reasons JSON (matched_skills, gaps, evidence_refs, preference_fit)
- created_at

### TailoredResume
- id, user_id, job_id, profile_version
- docx_url, pdf_url (optional)
- change_log JSON
- created_at

### ApplicationTracking
- id, user_id, job_id
- status enum: saved/applied/interviewing/rejected/offer
- notes text, updated_at

---

## 8) API Endpoints (MVP)

### Auth
- handled by auth provider (e.g., Clerk/Auth.js) or custom

### Profile
- `GET /api/profile`
- `PUT /api/profile` (updates + version bump)

### Resume
- `POST /api/resume/upload` (returns resume_document_id)
- `POST /api/resume/parse/{resume_document_id}` (async; enqueues job)
- `GET /api/resume/{resume_document_id}`

### Jobs & Matching
- `POST /api/matches/refresh` (async recompute matches)
- `GET /api/matches?filters...`
- `GET /api/matches/{match_id}`

### Tailored Resume
- `POST /api/tailor/{job_id}` (async)
- `GET /api/tailored/{tailored_resume_id}`

### Tracking
- `PUT /api/tracking/{job_id}`

### Health
- `GET /health`

---

## 9) Background Jobs

1. Resume parsing job
2. Job ingestion job (scheduled)
3. Embedding generation job
4. Match computation job
5. Tailored resume generation job
6. Cleanup/data retention job (on delete requests)

All long-running tasks must be async via queue.

---

## 10) UX Requirements (Key Screens)

### Web (desktop-first)
- Auth screens
- Upload resume + parsing status
- Profile editor (skills + preferences + experience)
- Matches list + filters + sorting
- Job detail with reasons/gaps + “Generate ATS Resume”
- Generated resumes list + download
- Tracking board/list (minimal)

### Mobile (Expo)
- Auth
- Matches list + job detail
- Trigger tailored resume generation
- View/download links (or email to self)
- Basic profile preferences edit (full editing can remain web-only in v1)

---

## 11) Quality Bar / Acceptance Criteria

### Parsing
- At least 80% of resumes produce a usable profile without manual fixes
- Users can correct anything quickly

### Matching
- Each match must show reasons and gaps (no black box)
- Sorting is stable and explainable

### Tailoring
- Must not hallucinate facts
- Must produce ATS-safe DOCX consistently
- Change log must be generated for every resume

### Reliability
- Resume upload and parsing should complete within a reasonable time (async with progress)
- Errors must be user-friendly and actionable

---

## 12) Dev Workflow (Windows Desktop + Windows Laptop)

### Repo & Branching
- GitHub repo is source of truth
- Branch per feature: `feature/<name>`
- Merge via PR even if solo (keeps history clean)

### Local Dev
- `docker-compose` runs Postgres + Redis locally
- `.env.example` committed; real `.env` never committed

### Working across machines
- Desktop: commit + push
- Laptop: pull + continue
- No local-only state; all state in cloud or committed files

---

## 13) Codex CLI Usage Rules (for safe generation)

- Codex must read this SPEC.md before coding
- All generated LLM prompts must:
  - enforce JSON schema validation for extraction
  - enforce “no hallucinations” for tailoring
  - enforce ATS formatting rules
- After generation:
  - run tests / lint
  - verify endpoints manually

---

## 14) Roadmap (6 months)

### Month 1
- Web + API scaffold, auth, dashboard skeleton, profile schema

### Month 2
- Resume upload + parsing + editable profile

### Month 3
- Job ingestion (1–2 sources) + matching + explainability dashboard

### Month 4
- Tailored ATS resume generation + doc output + change logs

### Month 5
- Mobile app (Expo) core flows + alerts

### Month 6
- Subscriptions + security hardening + monitoring + launch prep + app store submissions

---

## 15) Open Decisions (Track but don’t block)
- Exact job data providers for v1
- Subscription tiers and limits
- Desktop installer vs web-only for “desktop”
- Whether to support cover-letter generation (likely v2)
