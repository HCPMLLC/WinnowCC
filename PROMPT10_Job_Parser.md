# PROMPT10: Senior Recruiter Job Parser — Deep Extraction, Fraud Detection & Candidate Matching

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Implement a professional senior-recruiter-grade **Job Posting Parser** that treats every job posting the way a 25-year staffing veteran would: reading between the lines, extracting every requirement precisely, detecting fraud and duplicates aggressively, and mapping extracted data against the candidate profile with surgical precision.

This is NOT a keyword matcher. This is a **full-context job intelligence engine** that understands industry terminology, seniority signals, hidden requirements, compensation norms, and company context — then maps all of it against every dimension of the candidate's profile to produce an honest, quantified match.

---

## Triggers — When to Use This Prompt

- Building or refining the job posting ingestion and parsing pipeline.
- Improving match quality beyond simple keyword overlap.
- Adding fraud/duplicate detection to job ingestion.
- Enriching the `jobs` table with structured extracted fields.
- Implementing deep candidate-to-job comparison logic.
- Product asks for "recruiter-grade matching," "job intelligence," or "deep job parsing."

---

## Architecture Overview

This prompt adds/modifies three layers:

1. **Job Parser Service** (`services/api/app/services/job_parser.py`) — Extracts structured intelligence from raw job postings.
2. **Fraud & Duplicate Detector** (`services/api/app/services/job_fraud_detector.py`) — Flags and excludes fraudulent, spam, and duplicate postings.
3. **Deep Match Scorer** (enhancements to `services/api/app/services/matching.py`) — Uses parsed job intelligence + full candidate profile for precise scoring.

---

## Stage 1: Enriched Job Data Model

### 1.1 New table: `job_parsed_details`

Create an Alembic migration. This table stores the structured extraction from each job posting.

**Table: `job_parsed_details`**

| Column | Type | Description |
|--------|------|-------------|
| id | int PK | Auto-increment |
| job_id | int FK jobs.id, unique | One parsed record per job |
| parsed_at | timestamp | When parsing completed |
| parse_version | int | Schema version for future upgrades (start at 1) |
| — **Role Classification** — | | |
| normalized_title | string | Cleaned, standardized title (e.g., "Senior Project Manager") |
| seniority_level | string enum | intern, junior, mid, senior, lead, principal, director, vp, c_level |
| employment_type | string enum | full_time, part_time, contract, contract_to_hire, internship, temporary, freelance |
| estimated_duration_months | int nullable | For contract roles: estimated duration in months |
| — **Location & Work Mode** — | | |
| parsed_city | string nullable | Extracted city |
| parsed_state | string nullable | Extracted state/province |
| parsed_country | string nullable | Extracted country (default US if ambiguous + US indicators) |
| work_mode | string enum | onsite, remote, hybrid |
| travel_percent | int nullable | Estimated travel percentage (0–100) |
| relocation_offered | bool | Whether relocation assistance mentioned |
| — **Compensation Intelligence** — | | |
| salary_min_parsed | int nullable | Parsed or inferred minimum salary |
| salary_max_parsed | int nullable | Parsed or inferred maximum salary |
| salary_currency | string default 'USD' | Currency |
| salary_type | string enum | annual, hourly, monthly, daily |
| benefits_mentioned | jsonb | Array of benefit keywords found (e.g., ["401k", "health", "equity", "pto"]) |
| compensation_confidence | string enum | explicit (stated in posting), inferred (from title/industry norms), unknown |
| — **Requirements Extraction** — | | |
| required_skills | jsonb | Array of {skill, category, is_must_have, context_snippet} |
| preferred_skills | jsonb | Array of {skill, category, is_must_have: false, context_snippet} |
| required_certifications | jsonb | Array of {cert_name, normalized_name, required_or_preferred} |
| required_education | jsonb | {min_degree, field_of_study, equivalent_experience_ok} |
| required_years_experience | int nullable | Minimum years explicitly stated |
| preferred_years_experience | int nullable | Preferred years if different from required |
| required_clearance | string nullable | Security clearance if mentioned (e.g., "Secret", "Top Secret") |
| tools_and_technologies | jsonb | Array of specific tools/platforms/software mentioned |
| — **Company Intelligence** — | | |
| company_industry | string nullable | Inferred industry (e.g., "Healthcare", "Financial Services") |
| company_size_signal | string nullable | Startup, SMB, mid-market, enterprise (from clues in posting) |
| department | string nullable | Extracted department (e.g., "IT", "Supply Chain", "Engineering") |
| reports_to | string nullable | If mentioned: who this role reports to |
| team_size_signal | string nullable | Any team size clues (e.g., "team of 12") |
| — **Posting Quality & Metadata** — | | |
| posting_quality_score | int 0–100 | How complete/professional the posting is |
| red_flags | jsonb | Array of {flag_code, severity, description} for fraud/quality issues |
| is_likely_fraudulent | bool default false | Final fraud determination |
| is_duplicate_of_job_id | int nullable FK jobs.id | If this is a duplicate, points to the canonical job |
| duplicate_confidence | float nullable | 0.0–1.0 confidence it's a duplicate |
| raw_responsibilities | jsonb | Array of extracted responsibility/duty strings |
| raw_qualifications | jsonb | Array of raw qualification strings as written |

### 1.2 Add columns to existing `jobs` table

Add via Alembic migration:

| Column | Type | Description |
|--------|------|-------------|
| is_active | bool default true | Set false for detected fraud/expired |
| dedup_group_id | string nullable | Group ID for duplicate clusters |
| first_seen_at | timestamp nullable | First time this job was ingested (for staleness detection) |
| last_seen_at | timestamp nullable | Most recent time this job appeared in a feed |

---

## Stage 2: Job Parser Service

### File: `services/api/app/services/job_parser.py`

Implement a `JobParserService` class that takes a raw job record (from the `jobs` table) and produces a `job_parsed_details` row.

### 2.1 Title Normalization

```
Input:  "Sr. PM / Scrum Master (Remote - US Only!)"
Output: normalized_title = "Senior Project Manager / Scrum Master"
        seniority_level = "senior"
        work_mode = "remote"
```

Rules:
- Expand abbreviations: Sr. → Senior, Jr. → Junior, Mgr → Manager, PM → Project Manager, BA → Business Analyst, Dev → Developer, Eng → Engineer, etc.
- Strip parenthetical location/mode info (extract it first).
- Map to seniority: intern, junior (I/II, Associate), mid (III, no qualifier), senior (Sr., Senior, IV), lead, principal, director, VP, C-level (CTO, CIO, etc.).
- Handle dual titles (e.g., "PM / Scrum Master") — store both, primary first.

### 2.2 Employment Type & Duration Extraction

Scan the full posting text for:
- **Type keywords**: "full-time," "part-time," "contract," "C2H," "contract-to-hire," "W2," "1099," "Corp-to-Corp," "temp," "temporary," "freelance," "internship."
- **Duration signals**: "6-month engagement," "12-month contract," "through December 2026," date ranges.
- If no explicit type is found, default to `full_time` but set a low confidence flag.

### 2.3 Location & Work Mode Parsing

Extract from title, location field, AND description body:
- City, State, Country — use pattern matching for "City, ST" and "City, State" formats.
- Work mode: scan for "remote," "hybrid," "onsite," "on-site," "in-office," "telecommute," "work from home," "WFH."
- Handle qualifiers: "Remote - US Only," "Hybrid (3 days onsite)," "Must be within commuting distance of..."
- Travel: "up to 25% travel," "travel required," "no travel."
- Relocation: "relocation assistance available," "relocation package."

### 2.4 Compensation Extraction & Inference

**Explicit extraction** (highest confidence):
- Parse dollar amounts: "$120,000 - $150,000/year," "$65-$85/hr," "$5,000/month."
- Handle ranges, single values, and "up to" / "starting at" language.
- Detect currency: USD default; look for €, £, CAD, etc.
- Detect type: annual (default for salaried), hourly (for contract/hourly mentions), monthly, daily.

**Inference** (when not stated):
- Use `normalized_title` + `seniority_level` + `parsed_city` + `company_industry` to estimate a salary range from built-in lookup tables.
- Mark `compensation_confidence = "inferred"` and store the source logic in a reason field.
- Built-in salary reference data (embed a reasonable default table):
  - Senior Project Manager, Healthcare, US: $120K–$160K
  - Software Engineer, Mid, US: $100K–$140K
  - Contract PM, hourly, US: $60–$90/hr
  - (Include 15–20 common title/seniority/industry combinations as defaults; this is a starting heuristic.)

### 2.5 Requirements Extraction (The Core)

This is where the senior recruiter eye matters most. Parse the FULL job description to extract:

**A) Skills — Required vs. Preferred**

- Scan sections labeled: "Requirements," "Qualifications," "Must Have," "Required," "Minimum Qualifications."
- Scan sections labeled: "Preferred," "Nice to Have," "Desired," "Bonus," "Plus."
- For each skill found:
  - `skill`: the skill name (e.g., "MS Project," "Agile," "Python")
  - `category`: technical, methodology, tool, soft_skill, domain_knowledge
  - `is_must_have`: true if in required section, false if in preferred section
  - `context_snippet`: the sentence or bullet where this skill was found (for explainability)

**B) Certifications**

- Scan for known cert patterns: PMP, CAPM, CSM, SAFe, AWS, Azure, CISSP, Six Sigma, ITIL, etc.
- Also detect: "certification required," "certified in," "must hold."
- Normalize names: "PMP®" → "PMP", "Certified Scrum Master" → "CSM."
- Mark required vs. preferred based on section context.

**C) Education**

- Extract: degree level (Bachelor's, Master's, PhD, Associate's), field of study, and whether "or equivalent experience" is accepted.
- Handle: "BS/BA in Computer Science or related field," "Master's preferred."

**D) Experience — Years & Context**

- Extract explicit year requirements: "5+ years," "7-10 years," "minimum 3 years."
- Extract experience context: "experience in healthcare IT," "experience managing $5M+ budgets," "experience with Epic/Cerner."
- Distinguish required minimum from preferred/ideal.

**E) Tools & Technologies**

- Extract specific named tools/platforms: "ServiceNow," "Jira," "SharePoint," "Salesforce," "Epic," "SAP," "Workday," "Power BI," "Smartsheet," etc.
- Separate from generic skills (e.g., "project management" is a skill; "MS Project" is a tool).

**F) Responsibilities/Duties**

- Extract bullet points or sentences from "Responsibilities," "What You'll Do," "Key Duties" sections.
- Store as `raw_responsibilities` array for matching against candidate experience bullets.

### 2.6 Company Intelligence

From the posting text + company name, infer:
- **Industry**: Look for domain keywords (healthcare, financial services, insurance, technology, government, manufacturing, etc.).
- **Company size signal**: "Fortune 500," "startup," "growing team of 20," "enterprise organization," number of employees if stated.
- **Department**: "IT department," "Supply Chain," "Engineering team," "Legal."
- **Reporting structure**: "reports to the CIO," "reporting to VP of Engineering."

### 2.7 Posting Quality Score (0–100)

Score the posting itself for completeness and professionalism:

| Signal | Points |
|--------|--------|
| Has clear title | +10 |
| Has explicit salary/compensation | +15 |
| Has structured requirements section | +10 |
| Has company description | +5 |
| Has location details | +10 |
| Has employment type stated | +5 |
| Has application deadline | +5 |
| Has hiring manager info | +10 |
| Description > 200 words | +5 |
| Description < 50 words (too short) | -15 |
| No grammatical red flags (excessive caps, broken formatting) | +10 |
| Has benefits mentioned | +5 |
| Has clear responsibilities section | +10 |

Clamp to 0–100.

---

## Stage 3: Fraud & Duplicate Detection

### File: `services/api/app/services/job_fraud_detector.py`

### 3.1 Fraud Detection Signals

Score each job for fraud risk. Accumulate red flag points:

| Signal | Code | Severity | Points |
|--------|------|----------|--------|
| No company name or generic company name ("Confidential", "Hiring Now") | `no_company` | medium | +15 |
| Description is < 50 words | `too_short` | medium | +15 |
| Salary vastly above market (> 2x expected for title/seniority) | `salary_too_high` | high | +20 |
| Asks for payment, fees, or financial info from candidate | `payment_required` | critical | +50 |
| Contains known scam phrases: "make money from home," "no experience needed" for senior roles, "wire transfer," "personal bank" | `scam_language` | critical | +50 |
| Email domain is free provider (gmail, yahoo, hotmail) for a large company | `free_email_domain` | medium | +15 |
| URL domain does not match company name | `url_mismatch` | low | +10 |
| Posted date > 90 days ago and still active | `stale_posting` | low | +10 |
| Duplicated across 5+ sources with identical text | `excessive_crosspost` | low | +5 |
| Description is mostly ALL CAPS | `excessive_caps` | medium | +10 |
| Description contains excessive emoji or special characters | `unprofessional_format` | low | +5 |
| Salary listed as "$0" or unreasonably low (< $10/hr for professional role) | `unrealistic_salary` | medium | +15 |
| Company not found in any business registry/known employer list (future enhancement) | `unknown_employer` | low | +5 |
| Job reposted with different title but same description hash | `title_swap_repost` | medium | +15 |

**Thresholds:**
- `fraud_score` < 20 → `is_likely_fraudulent = false`, no action
- `fraud_score` 20–39 → `is_likely_fraudulent = false`, store red_flags for transparency
- `fraud_score` 40–59 → `is_likely_fraudulent = false`, flag for admin review, lower posting_quality_score
- `fraud_score` ≥ 60 → `is_likely_fraudulent = true`, set `jobs.is_active = false`, exclude from matching

Store all red flags in `job_parsed_details.red_flags` as `[{flag_code, severity, description, points}]`.

### 3.2 Duplicate Detection (Multi-Layer)

Detect duplicates using a layered approach. Two jobs are duplicates if ANY of these match:

**Layer 1: Exact content hash** (already exists in `jobs.content_hash`)
- Same `content_hash` = definite duplicate. Keep earliest `ingested_at` as canonical.

**Layer 2: Title + Company + Location fuzzy match**
- Normalize: lowercase, strip punctuation, strip common suffixes ("Inc.", "LLC", "Corp").
- If `normalized_title` matches AND `company` fuzzy match (Levenshtein distance ≤ 2 or token overlap ≥ 80%) AND location matches (same city+state or both remote):
  - `duplicate_confidence = 0.85`
  - Mark as duplicate of the earliest-ingested canonical job.

**Layer 3: Description similarity**
- Compute Jaccard similarity of description word tokens (after stopword removal).
- If similarity > 0.80 AND same company (fuzzy):
  - `duplicate_confidence = 0.90`
  - Mark as duplicate.

**Layer 4: Same company + same title + overlapping date window**
- If same company (fuzzy) + same title (fuzzy) + posted within 14 days of each other:
  - `duplicate_confidence = 0.75`
  - Mark as likely duplicate for admin review.

**Deduplication behavior:**
- Assign a `dedup_group_id` (UUID) to all jobs in a duplicate cluster.
- The job with the earliest `first_seen_at` is the canonical record.
- Duplicates get `is_duplicate_of_job_id` set to the canonical job's ID.
- When returning matches, merge duplicate clusters: show one job per cluster, aggregate `sources` (e.g., "Found on: Remotive, The Muse, Indeed").
- The existing `GET /api/matches` already deduplicates by title+company — enhance this with the `dedup_group_id` for more reliable dedup.

### 3.3 Staleness Detection

- If a job was `first_seen_at` > 60 days ago and `last_seen_at` < 14 days ago → still active, no action.
- If a job was `first_seen_at` > 90 days ago and `last_seen_at` > 30 days ago → likely expired, set `is_active = false`.
- On each ingestion run, update `last_seen_at` for re-seen jobs.

---

## Stage 4: Deep Candidate-to-Job Match Scoring

### Enhancements to `services/api/app/services/matching.py`

Replace or augment the existing skill-overlap matching with a multi-dimensional comparison that mirrors how a senior recruiter evaluates fit.

### 4.1 Dimension: Skills Match (0–100, weight 0.30)

Use `job_parsed_details.required_skills` and `preferred_skills` against `candidate_profiles.profile_json.skills`.

**Sub-scoring:**
- For each `required_skill` (is_must_have=true):
  - Exact match in candidate skills: +full points
  - Synonym/related match (e.g., "Agile" ↔ "Scrum," "MS Project" ↔ "Microsoft Project"): +80% points
  - Partial match (skill mentioned in experience bullets but not in skills list): +50% points
  - Not found: 0 points, add to `missing_skills`
- For each `preferred_skill`:
  - Same logic but at 50% weight of required skills.
- Normalize to 0–100.

**Synonym table** (embed a starter set, make extensible):
```
"Agile" ↔ "Scrum" ↔ "SAFe" ↔ "Kanban" (methodology family)
"MS Project" ↔ "Microsoft Project"
"Power BI" ↔ "PowerBI"
"SharePoint" ↔ "SP" ↔ "SPO" (SharePoint Online)
"JavaScript" ↔ "JS" ↔ "TypeScript" ↔ "TS"
"Python" ↔ "Python3"
"AWS" ↔ "Amazon Web Services"
"GCP" ↔ "Google Cloud" ↔ "Google Cloud Platform"
"CI/CD" ↔ "Continuous Integration" ↔ "Jenkins" ↔ "GitHub Actions"
```

### 4.2 Dimension: Experience Match (0–100, weight 0.25)

Compare candidate work history against job requirements:

**A) Years of experience fit:**
- `required_years_experience` vs. candidate's `years_experience` (from profile or computed from work history dates).
- Within range or above: 100 points.
- 1–2 years below: 70 points.
- 3+ years below: 30 points.
- Significantly over-qualified (10+ years above requirement): 80 points (slight penalty — recruiters know overqualified candidates may not stay).

**B) Industry/domain experience:**
- Does candidate have work history in the same `company_industry`?
- Match: +100 sub-points. Adjacent industry: +60. No match: +20.
- Use a simple industry adjacency map:
  ```
  Healthcare ↔ Health Insurance ↔ Pharmaceuticals
  Banking ↔ Financial Services ↔ Insurance
  Government ↔ Defense ↔ Aerospace
  Technology ↔ SaaS ↔ Telecommunications
  ```

**C) Responsibility alignment:**
- Compare `job_parsed_details.raw_responsibilities` against candidate's experience bullets.
- Token overlap scoring: for each job responsibility, find the best-matching candidate bullet.
- Weight by recency: recent experience (last 5 years) weighted 2x vs. older experience.

**D) Budget/scope signals:**
- If job mentions "$5M+ budgets" and candidate mentions "$5M-$15M" budgets → strong match.
- Extract numeric scope indicators from both sides and compare.

Combine A (40%) + B (20%) + C (30%) + D (10%) → normalize to 0–100.

### 4.3 Dimension: Certification Match (0–100, weight 0.10)

- For each `required_certification`: candidate has it → full points, doesn't → 0.
- For each `preferred_certification`: candidate has it → full points, doesn't → no penalty.
- Normalize. If job has no cert requirements, default this dimension to 80 (neutral — doesn't hurt).

Compare against `profile_json.certifications` (or equivalent field in the candidate profile).

### 4.4 Dimension: Location & Logistics Fit (0–100, weight 0.15)

- **Work mode match**: Candidate prefers remote, job is remote → 100. Candidate prefers remote, job is onsite → 20. Candidate prefers hybrid, job is hybrid → 100. Etc.
- **Location match**: If onsite/hybrid — is candidate in or willing to relocate to the job's city/state? Compare `candidate.location_city/state` against `job.parsed_city/state`. Same city → 100. Same state → 70. Different state → 30 (unless relocation_offered → 60).
- **Travel tolerance**: If job requires travel, does candidate's profile indicate willingness? (Use preferences if available; default to 50 if unknown.)

### 4.5 Dimension: Compensation Fit (0–100, weight 0.10)

- Compare candidate's `desired_salary_min/max` against job's `salary_min_parsed/max_parsed`.
- Candidate range overlaps job range → 100.
- Candidate minimum > job maximum → 20 (candidate expects more).
- Candidate maximum < job minimum → 80 (candidate is a salary bargain — still a match, slightly unusual).
- No salary data on either side → 50 (neutral).

### 4.6 Dimension: Title Alignment (0–100, weight 0.10)

- Compare candidate's target titles (from preferences) and most recent job titles against `normalized_title`.
- Exact match → 100.
- Same family but different seniority (e.g., candidate is "Project Manager," job is "Senior Project Manager"): → 70 (stretch) or 90 (step up, often desired).
- Related but different title (e.g., "Program Manager" vs. "Project Manager"): → 60.
- Unrelated: → 10.

### 4.7 Composite Match Score

```
composite_match = (
    skills_score      × 0.30 +
    experience_score  × 0.25 +
    cert_score        × 0.10 +
    location_score    × 0.15 +
    compensation_score × 0.10 +
    title_score       × 0.10
)
```

This composite replaces or supplements the existing `match_score`. Store as `match_score` on the Match record. Preserve reasons JSON with per-dimension breakdowns:

```json
{
  "skills": {"score": 82, "matched": [...], "missing": [...], "synonyms_used": [...]},
  "experience": {"score": 75, "years_fit": "exact", "industry_match": "adjacent", "top_bullet_matches": [...]},
  "certifications": {"score": 100, "matched": ["PMP"], "missing": []},
  "location": {"score": 90, "mode_fit": "remote_match", "geo_fit": "same_state"},
  "compensation": {"score": 70, "candidate_range": "130-180k", "job_range": "120-150k", "overlap": "partial"},
  "title": {"score": 85, "candidate_title": "Program Manager", "job_title": "Senior Project Manager", "alignment": "related_stretch"}
}
```

---

## Stage 5: Integration into Ingestion Pipeline

### 5.1 Modify the job ingestion worker

In the existing ingestion flow (where jobs are fetched from sources and stored):

1. **After storing a job** in the `jobs` table → immediately run `JobParserService.parse(job)` to populate `job_parsed_details`.
2. **After parsing** → run `JobFraudDetector.evaluate(job, parsed_details)` to set fraud flags and dedup.
3. **After fraud check** → if `is_likely_fraudulent = true`, set `jobs.is_active = false`.
4. **After dedup** → if duplicate found, set `is_duplicate_of_job_id` and `dedup_group_id`.

### 5.2 Re-parse endpoint (admin)

Add: `POST /api/admin/jobs/{job_id}/reparse`
- Re-runs the parser on a single job (useful after parser improvements).
- Protected by admin token.

Add: `POST /api/admin/jobs/reparse-all`
- Re-runs parser on all active jobs.
- Enqueue as background job (RQ).
- Protected by admin token.

### 5.3 Parsed details endpoint

Add: `GET /api/jobs/{job_id}/parsed`
- Returns `job_parsed_details` for a job.
- Requires auth. Useful for the frontend "Job Detail" view to show structured requirements.

### 5.4 Update match computation

When `POST /api/matches/refresh` or `POST /api/match/run` is called:
- Use `job_parsed_details` (if available) for the deep match scoring in Stage 4.
- If `job_parsed_details` does not exist for a job, fall back to the existing keyword-based matching.
- Exclude jobs where `is_active = false` or `is_likely_fraudulent = true`.
- When dedup groups exist, only match against the canonical job in each group.

---

## Stage 6: Frontend Enhancements

### 6.1 Match Detail — Show Parsed Intelligence

On the match detail view (`apps/web/app/matches/page.tsx` or a match detail page):

- Show the **per-dimension score breakdown** (skills, experience, certs, location, compensation, title) as a small bar chart or score cards.
- Show **matched skills** (green), **missing required skills** (red), **preferred skills you have** (blue).
- Show **certification match/gap**.
- Show **salary range comparison** (candidate range vs. job range, visual overlap).
- Show **job posting quality score** and any red flags (e.g., "⚠ No salary listed" or "⚠ Posted 45 days ago").

### 6.2 Match List — Fraud/Quality Indicators

On the matches list:
- Do NOT show jobs flagged `is_likely_fraudulent = true`.
- Show a small quality indicator (e.g., green/yellow/red dot) based on `posting_quality_score`.
- Show aggregated sources for deduplicated jobs (e.g., "Found on: Remotive, The Muse").

### 6.3 Admin — Fraud Queue

On the admin trust/quality page (or a new `/admin/job-quality` page):
- List jobs with `fraud_score` ≥ 40 for admin review.
- Allow admin to manually mark a job as fraudulent or legitimate.
- Show red flag details for each flagged job.

---

## Stage 7: Background Jobs & Scheduling

### 7.1 Parse job worker

Add RQ job: `parse_job_posting(job_id)`
- Loads job from DB.
- Runs `JobParserService.parse()`.
- Runs `JobFraudDetector.evaluate()`.
- Updates `job_parsed_details`, `jobs.is_active`, dedup fields.

### 7.2 Batch re-parse worker

Add RQ job: `reparse_all_jobs()`
- Iterates all active jobs.
- Re-parses and re-evaluates each.
- Useful after parser logic updates.

### 7.3 Staleness checker (scheduled)

Add a periodic job (run daily or on each ingestion cycle):
- Check all jobs for staleness (see Stage 3.3).
- Set `is_active = false` for expired jobs.
- Update `last_seen_at` for re-seen jobs.

---

## File and Component Reference

| What | Where |
|------|-------|
| Job Parser Service | `services/api/app/services/job_parser.py` (NEW) |
| Fraud Detector Service | `services/api/app/services/job_fraud_detector.py` (NEW) |
| Skill Synonym Table | `services/api/app/services/skill_synonyms.py` (NEW) |
| Salary Reference Data | `services/api/app/services/salary_reference.py` (NEW) |
| Industry Adjacency Map | `services/api/app/services/industry_map.py` (NEW) |
| Enhanced Matching | `services/api/app/services/matching.py` (MODIFY) |
| Job Parsed Details Model | `services/api/app/models/job_parsed_detail.py` (NEW) |
| Jobs Model (add columns) | `services/api/app/models/job.py` (MODIFY) |
| Admin Reparse Router | `services/api/app/routers/admin_jobs.py` (NEW) |
| Job Parsed Detail Endpoint | `services/api/app/routers/jobs.py` (NEW or MODIFY) |
| Alembic Migration | `services/api/alembic/versions/` (NEW) |
| Match Detail Frontend | `apps/web/app/matches/page.tsx` (MODIFY) |
| Admin Job Quality Page | `apps/web/app/admin/job-quality/page.tsx` (NEW) |
| Match Schemas | `services/api/app/schemas/matches.py` (MODIFY) |
| Job Schemas | `services/api/app/schemas/jobs.py` (NEW or MODIFY) |
| Worker Jobs | `services/api/app/services/queue.py` or worker module (MODIFY) |
| Ingestion Pipeline | `services/api/app/services/ingestion.py` or equivalent (MODIFY) |

---

## Environment Variables (if new ones needed)

None required for core functionality. All logic is deterministic and runs locally. Future enhancements (company verification APIs, salary data APIs) would add env vars.

---

## Implementation Order (for a beginner following in Cursor)

Follow these steps **in exact order**:

1. **Step 1:** Create the Alembic migration for `job_parsed_details` table and new `jobs` columns.
   - File: `services/api/alembic/versions/xxxx_add_job_parsed_details.py`
   - Run: `cd services/api && alembic upgrade head`

2. **Step 2:** Create the SQLAlchemy model for `job_parsed_details`.
   - File: `services/api/app/models/job_parsed_detail.py`
   - Update: `services/api/app/models/__init__.py` to import the new model.
   - Update: `services/api/app/models/job.py` to add the new columns.

3. **Step 3:** Create the skill synonym table.
   - File: `services/api/app/services/skill_synonyms.py`

4. **Step 4:** Create the salary reference data.
   - File: `services/api/app/services/salary_reference.py`

5. **Step 5:** Create the industry adjacency map.
   - File: `services/api/app/services/industry_map.py`

6. **Step 6:** Create the Job Parser Service.
   - File: `services/api/app/services/job_parser.py`

7. **Step 7:** Create the Fraud & Duplicate Detector.
   - File: `services/api/app/services/job_fraud_detector.py`

8. **Step 8:** Update the matching service with deep scoring.
   - File: `services/api/app/services/matching.py` (modify existing)

9. **Step 9:** Update the ingestion pipeline to call parser + fraud detector after storing jobs.
   - File: `services/api/app/services/ingestion.py` or equivalent (modify existing)

10. **Step 10:** Add new API endpoints (admin reparse, job parsed details).
    - Files: `services/api/app/routers/admin_jobs.py` (new), `services/api/app/routers/jobs.py` (new or modify)
    - Update: `services/api/app/main.py` to register new routers.

11. **Step 11:** Add schemas for new response types.
    - File: `services/api/app/schemas/jobs.py` (new or modify)

12. **Step 12:** Update frontend match detail to show parsed job intelligence.
    - File: `apps/web/app/matches/page.tsx` (modify)

13. **Step 13:** Add admin job quality review page.
    - File: `apps/web/app/admin/job-quality/page.tsx` (new)

14. **Step 14:** Add worker jobs for parsing and staleness checking.
    - Modify worker registration in `services/api/app/services/queue.py` or worker module.

15. **Step 15:** Test end-to-end: ingest a job → parse → fraud check → match against candidate profile → verify scores and reasons in API response.

---

## Testing

- Add unit tests for:
  - Title normalization (abbreviation expansion, seniority detection)
  - Salary extraction (various formats)
  - Fraud scoring (known scam phrases, short descriptions)
  - Duplicate detection (fuzzy matching)
  - Skills matching with synonyms
  - Experience year comparison
- Test files: `services/api/tests/test_job_parser.py`, `services/api/tests/test_job_fraud_detector.py`, `services/api/tests/test_deep_matching.py`

---

## Non-Goals (Do NOT implement in this prompt)

- External API calls for company verification (Crunchbase, LinkedIn API, etc.)
- ML/AI-based fraud detection (keep it deterministic and rule-based)
- Real-time salary data from external APIs (use embedded reference data)
- Automated job application on behalf of the user
- Scraping any website that prohibits it

---

## Summary Checklist

- [ ] Alembic migration: `job_parsed_details` table + new `jobs` columns
- [ ] SQLAlchemy model: `JobParsedDetail`
- [ ] Service: `JobParserService` with title normalization, type extraction, location parsing, salary extraction/inference, requirements extraction, company intelligence, quality scoring
- [ ] Service: `JobFraudDetector` with fraud scoring, duplicate detection (4 layers), staleness detection
- [ ] Service: Skill synonym table, salary reference data, industry adjacency map
- [ ] Enhanced matching: 6-dimension deep scoring (skills, experience, certs, location, compensation, title) with composite score and detailed reasons JSON
- [ ] Integration: Parser + fraud detector called during ingestion pipeline
- [ ] API: Admin reparse endpoints, job parsed details endpoint
- [ ] Frontend: Match detail shows per-dimension breakdown, skill match/gap, salary comparison, quality indicator
- [ ] Frontend: Admin job quality review page
- [ ] Worker jobs: parse_job_posting, reparse_all_jobs, staleness_checker
- [ ] Unit tests for parser, fraud detector, and deep matching
- [ ] Jobs with `is_likely_fraudulent = true` excluded from all candidate-facing results

Return code changes only.
