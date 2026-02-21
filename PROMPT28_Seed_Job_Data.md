# PROMPT28_Seed_Job_Data.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and AGENTS.md before making changes.

## Purpose

Populate Winnow's database with real job postings from legal API sources, then systematically validate that the matching pipeline produces accurate, useful results across multiple resume profiles and industries. This is the "does it actually work?" gate before putting the product in front of real users.

**Three parts, one prompt:**
- **Part 1 — Job Seeding:** Ingest 200+ real jobs from Remotive, The Muse, and Greenhouse/Lever public boards across multiple categories. Schedule automated daily refresh.
- **Part 2 — Match Quality Validation:** Run matching against 5–10 diverse test resumes spanning different industries, seniority levels, and work preferences. Measure and report match quality metrics.
- **Part 3 — Tuning & Guardrails:** Adjust match score weights, semantic blend ratio, and fraud/staleness thresholds based on validation results. Add data quality monitoring.

---

## Triggers — When to Use This Prompt

- The app is feature-complete and you're preparing for soft launch.
- The jobs table is empty or contains only test/mock data.
- Match quality feels poor or untested with real-world data.
- You need to validate the full pipeline: ingest → parse → deduplicate → embed → match → tailor.
- Product asks for "real jobs," "seed data," "match quality check," or "validate matching."

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Job model:** `services/api/app/models/job.py` — stores job postings with `source`, `source_job_id`, `title`, `company`, `description`, `requirements`, `location`, `salary_min/max`, `remote_ok`, `content_hash`, `embedding`, `is_active`.
2. **Job ingestion adapters:** `services/api/app/services/job_sources/` — provider adapter interface with implementations for Remotive, The Muse, and potentially Greenhouse/Lever public boards. Configured via `JOB_SOURCES` env var.
3. **Job parser:** `services/api/app/services/job_parser.py` — title normalization, type extraction, location parsing, salary extraction, requirements extraction, quality scoring. Stores parsed details in `job_parsed_details` table.
4. **Job fraud detector:** `services/api/app/services/job_fraud_detector.py` — fraud scoring, 4-layer duplicate detection, staleness detection.
5. **Matching service:** `services/api/app/services/matching.py` — 6-dimension composite scoring (skills 0.30, experience 0.25, certs 0.10, location 0.15, compensation 0.10, title 0.10) with blended semantic similarity (65% deterministic / 35% semantic).
6. **Embedding service:** `services/api/app/services/embedding.py` — generates embeddings for jobs and candidate profiles using Anthropic Voyager (or configured model). Stored in `embedding` column via pgvector.
7. **Queue/Worker:** `services/api/app/services/queue.py` + `services/api/app/worker.py` — RQ-based background job processing. Existing worker jobs include `ingest_jobs`, `parse_job_posting`, `generate_embedding`.
8. **Tailor service:** `services/api/app/services/tailor.py` — generates ATS-safe tailored resumes with grounding validation. Used in Part 2 to validate end-to-end.
9. **Admin endpoints:** `POST /api/admin/ingest` triggers job ingestion. `POST /api/admin/jobs/reparse-all` re-parses all active jobs. Protected by `ADMIN_TOKEN`.
10. **Candidate profiles:** `services/api/app/models/candidate_profile.py` — stores `profile_json` (JSONB) with structured experience, skills, preferences, and `embedding` vector.

---

# PART 1 — JOB SEEDING

## 1.1 Bulk Ingestion Script

**File to create:** `services/api/scripts/seed_jobs.py`

Create a standalone script that triggers bulk job ingestion across all configured sources. This script calls the existing ingestion adapters directly (not through the API) so it can run from the command line during setup.

```python
"""
Bulk job seeder for Winnow.
Usage: python scripts/seed_jobs.py [--categories all|tech|business|marketing|healthcare|finance]
                                    [--max-per-source 100]
                                    [--dry-run]
"""
import argparse
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
```

### Categories to ingest

Define search categories that cover the industries Winnow targets. Each category maps to API-specific query parameters:

```python
SEED_CATEGORIES = {
    "tech": {
        "remotive": {"category": "software-dev", "limit": 50},
        "themuse": {"category": "Engineering", "level": "Senior Level,Mid Level", "page_size": 50},
    },
    "project_management": {
        "remotive": {"category": "project-management", "limit": 30},
        "themuse": {"category": "Project & Program Management", "level": "Senior Level,Mid Level", "page_size": 30},
    },
    "business": {
        "themuse": {"category": "Business & Strategy", "level": "Senior Level,Mid Level", "page_size": 40},
    },
    "marketing": {
        "remotive": {"category": "marketing", "limit": 30},
        "themuse": {"category": "Marketing & PR", "page_size": 30},
    },
    "data": {
        "remotive": {"category": "data", "limit": 30},
        "themuse": {"category": "Data Science", "page_size": 30},
    },
    "design": {
        "remotive": {"category": "design", "limit": 20},
        "themuse": {"category": "Design & UX", "page_size": 20},
    },
    "finance": {
        "themuse": {"category": "Finance", "page_size": 30},
    },
    "healthcare": {
        "themuse": {"category": "Healthcare", "page_size": 20},
    },
}
```

### Script behavior

1. Parse CLI arguments (`--categories`, `--max-per-source`, `--dry-run`).
2. Initialize the database session (reuse `services/api/app/db.py` session factory).
3. For each selected category, call the corresponding source adapter's `fetch_jobs()` method.
4. For each fetched job:
   - Compute `content_hash` (SHA-256 of `title + company + location + description`).
   - Skip if `content_hash` already exists in DB (dedup).
   - Insert into `jobs` table.
   - Enqueue `parse_job_posting` worker job.
   - Enqueue `generate_embedding` worker job.
5. Log summary: total fetched, new inserted, duplicates skipped, errors.
6. In `--dry-run` mode, fetch and validate but do not insert.

### Expected output

```
2026-02-09 10:00:00 INFO Starting bulk ingestion...
2026-02-09 10:00:00 INFO Category: tech
2026-02-09 10:00:02 INFO   Remotive: fetched 47 jobs, 42 new, 5 duplicates
2026-02-09 10:00:05 INFO   The Muse: fetched 50 jobs, 48 new, 2 duplicates
2026-02-09 10:00:05 INFO Category: project_management
...
2026-02-09 10:01:30 INFO ════════════════════════════════════════
2026-02-09 10:01:30 INFO SEED COMPLETE
2026-02-09 10:01:30 INFO   Total fetched:    287
2026-02-09 10:01:30 INFO   New inserted:     251
2026-02-09 10:01:30 INFO   Duplicates:        31
2026-02-09 10:01:30 INFO   Errors:             5
2026-02-09 10:01:30 INFO   Worker jobs queued: 502 (251 parse + 251 embed)
2026-02-09 10:01:30 INFO ════════════════════════════════════════
```

---

## 1.2 Greenhouse & Lever Public Board Adapters

If not already implemented, create adapters for Greenhouse and Lever public job boards. These are legal, public JSON APIs that many companies use.

**File to create (if missing):** `services/api/app/services/job_sources/greenhouse.py`

```python
"""
Greenhouse public board adapter.
Fetches jobs from company public boards: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
No API key required. Legal and public.
"""
```

### Greenhouse adapter behavior

1. Accept a list of `board_tokens` (company identifiers) via config or argument.
2. Call `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` for each board.
3. Normalize each job to the Winnow `Job` schema:
   - `source`: `"greenhouse"`
   - `source_job_id`: `str(job["id"])`
   - `title`: `job["title"]`
   - `company`: Derive from board metadata or `job["departments"]`
   - `description`: `job["content"]` (HTML — strip tags)
   - `location`: `job["location"]["name"]`
   - `url`: `job["absolute_url"]`
   - `remote_ok`: Infer from location containing "Remote"
4. Return list of normalized jobs.

### Starter board tokens (real companies with active public boards)

```python
DEFAULT_GREENHOUSE_BOARDS = [
    "gitlab",           # GitLab — large remote-first company
    "figma",            # Figma — design tool company
    "hashicorp",        # HashiCorp — infrastructure software
    "watershed",        # Watershed — climate tech
    "airbnb",           # Airbnb — marketplace
    "duolingo",         # Duolingo — education
    "notion",           # Notion — productivity
    "plaid",            # Plaid — fintech
    "coinbase",         # Coinbase — crypto
    "stripe",           # Stripe — payments
]
```

**File to create (if missing):** `services/api/app/services/job_sources/lever.py`

```python
"""
Lever public postings adapter.
Fetches jobs from: https://api.lever.co/v0/postings/{company}?mode=json
No API key required. Legal and public.
"""
```

### Lever adapter behavior

1. Accept a list of company slugs via config or argument.
2. Call `GET https://api.lever.co/v0/postings/{company}?mode=json` for each company.
3. Normalize to Winnow `Job` schema:
   - `source`: `"lever"`
   - `source_job_id`: `posting["id"]`
   - `title`: `posting["text"]`
   - `company`: `posting["categories"]["team"]` or derive from slug
   - `description`: `posting["descriptionPlain"]` or strip HTML from `posting["description"]`
   - `location`: `posting["categories"]["location"]`
   - `url`: `posting["hostedUrl"]`
   - `remote_ok`: Infer from `posting["categories"]["commitment"]` or location
4. Return list of normalized jobs.

### Starter Lever companies

```python
DEFAULT_LEVER_COMPANIES = [
    "netflix",          # Netflix — entertainment
    "twitch",           # Twitch — streaming
    "netlify",          # Netlify — web platform
    "cloudflare",       # Cloudflare — security/CDN
    "databricks",       # Databricks — data/AI
]
```

---

## 1.3 Register New Sources in Configuration

**File to modify:** `services/api/app/services/job_sources/__init__.py` (or wherever source registry lives)

Add Greenhouse and Lever to the source registry so they respond to `JOB_SOURCES` env var:

```python
SOURCE_REGISTRY = {
    "remotive": RemotiveSource,
    "themuse": TheMuseSource,
    "greenhouse": GreenhouseSource,  # Add
    "lever": LeverSource,            # Add
}
```

**File to modify:** `services/api/.env`

Update `JOB_SOURCES` to include all sources:

```
JOB_SOURCES=remotive,themuse,greenhouse,lever
```

Add board/company config:

```
GREENHOUSE_BOARDS=gitlab,figma,hashicorp,watershed,airbnb,duolingo,notion,plaid,coinbase,stripe
LEVER_COMPANIES=netflix,twitch,netlify,cloudflare,databricks
```

---

## 1.4 Scheduled Daily Refresh

**File to modify:** `services/api/app/worker.py` (or create `services/api/app/jobs/scheduled.py`)

Add a scheduled ingestion job that runs daily to fetch new postings and mark stale ones:

```python
def daily_job_refresh():
    """
    Scheduled job: runs daily via Cloud Scheduler or cron.
    1. Fetch new jobs from all configured sources.
    2. Run fraud/duplicate detection on new jobs.
    3. Mark stale jobs as inactive (>90 days, not re-seen in 30 days).
    4. Log summary stats.
    """
```

**Cloud Scheduler (if deployed to GCP):**

This should already be configured from PROMPT16. Verify the Cloud Scheduler job hits:
```
POST https://your-api-url/api/admin/ingest
Authorization: Bearer {ADMIN_TOKEN}
```

Schedule: `0 6 * * *` (daily at 6 AM UTC)

If not yet configured, add this to the deployment checklist.

---

## 1.5 Ingestion Health Dashboard Endpoint

**File to create:** `services/api/app/routers/admin_jobs.py` (or add to existing admin router)

Add an admin endpoint that reports on the state of the jobs database:

```
GET /api/admin/jobs/stats
Authorization: Bearer {ADMIN_TOKEN}
```

Response:

```json
{
  "total_jobs": 287,
  "active_jobs": 251,
  "inactive_jobs": 36,
  "by_source": {
    "remotive": 77,
    "themuse": 98,
    "greenhouse": 52,
    "lever": 24
  },
  "by_category": {
    "tech": 92,
    "project_management": 41,
    "business": 38,
    "marketing": 30,
    "data": 28,
    "design": 18,
    "finance": 22,
    "healthcare": 18
  },
  "with_embeddings": 245,
  "without_embeddings": 6,
  "with_parsed_details": 249,
  "flagged_fraudulent": 4,
  "duplicate_clusters": 12,
  "oldest_active_job": "2026-01-15T00:00:00Z",
  "newest_job": "2026-02-09T06:00:00Z",
  "last_ingestion": "2026-02-09T06:00:00Z"
}
```

Register the router in `services/api/app/main.py`.

---

# PART 2 — MATCH QUALITY VALIDATION

## 2.1 Test Resume Profiles

**File to create:** `services/api/scripts/test_profiles/`

Create 5–10 synthetic but realistic test profiles as JSON files. Each profile represents a different industry, seniority level, and work preference. These are used to validate that the matching pipeline produces sensible results.

### Profile 1: Senior Software Engineer (Remote)

**File:** `services/api/scripts/test_profiles/01_senior_swe_remote.json`

```json
{
  "name": "Test Profile — Senior SWE",
  "basics": {
    "name": "Alex Chen",
    "email": "test-alex@example.com",
    "location": "Austin, TX",
    "years_of_experience": 8
  },
  "experience": [
    {
      "company": "TechCorp Inc.",
      "title": "Senior Software Engineer",
      "start_date": "2021-03",
      "end_date": null,
      "bullets": [
        "Led migration of monolithic Java application to microservices architecture using Spring Boot and Kubernetes, reducing deployment time by 70%",
        "Designed and implemented real-time data pipeline processing 2M events/day using Apache Kafka and Flink",
        "Mentored team of 4 junior engineers through code reviews and pair programming sessions"
      ]
    },
    {
      "company": "StartupXYZ",
      "title": "Software Engineer",
      "start_date": "2018-06",
      "end_date": "2021-02",
      "bullets": [
        "Built full-stack web application using React, Node.js, and PostgreSQL serving 50K monthly active users",
        "Implemented CI/CD pipeline with GitHub Actions reducing release cycle from 2 weeks to daily deploys",
        "Optimized database queries reducing API response times from 800ms to 120ms average"
      ]
    }
  ],
  "education": [
    {"institution": "University of Texas at Austin", "degree": "BS Computer Science", "year": 2018}
  ],
  "skills": ["Python", "Java", "TypeScript", "React", "Node.js", "PostgreSQL", "Kubernetes", "Docker", "AWS", "Kafka", "Spring Boot", "CI/CD", "Git"],
  "certifications": ["AWS Solutions Architect Associate"],
  "preferences": {
    "desired_titles": ["Senior Software Engineer", "Staff Engineer", "Tech Lead"],
    "remote_preference": "remote_only",
    "desired_salary_min": 150000,
    "desired_salary_max": 200000,
    "desired_locations": ["Austin, TX", "Remote"]
  }
}
```

### Profile 2: Project Manager / PMP (Hybrid)

**File:** `services/api/scripts/test_profiles/02_project_manager_pmp.json`

```json
{
  "name": "Test Profile — PM/PMP",
  "basics": {
    "name": "Maria Santos",
    "email": "test-maria@example.com",
    "location": "San Antonio, TX",
    "years_of_experience": 12
  },
  "experience": [
    {
      "company": "Global Consulting Group",
      "title": "Senior Program Manager",
      "start_date": "2019-01",
      "end_date": null,
      "bullets": [
        "Managed portfolio of 8 concurrent projects worth $12M total budget using Agile and Waterfall methodologies",
        "Reduced project delivery timelines by 25% through implementation of standardized risk management framework",
        "Led cross-functional team of 35 across 3 time zones to deliver enterprise ERP migration on schedule"
      ]
    },
    {
      "company": "Defense Contractor Corp",
      "title": "Project Manager",
      "start_date": "2014-06",
      "end_date": "2018-12",
      "bullets": [
        "Delivered 15+ DoD projects meeting CMMI Level 3 compliance requirements with zero audit findings",
        "Managed $5M annual budget with 98% forecast accuracy using Earned Value Management",
        "Implemented MS Project Server improving resource utilization from 72% to 89%"
      ]
    }
  ],
  "education": [
    {"institution": "UTSA", "degree": "MBA", "year": 2014},
    {"institution": "Texas State University", "degree": "BS Business Administration", "year": 2012}
  ],
  "skills": ["Project Management", "Agile", "Scrum", "Waterfall", "MS Project", "Jira", "Risk Management", "Budgeting", "Stakeholder Management", "EVM", "SAFe", "Kanban"],
  "certifications": ["PMP", "CSM", "SAFe Agilist"],
  "preferences": {
    "desired_titles": ["Program Manager", "Senior Project Manager", "PMO Director"],
    "remote_preference": "hybrid",
    "desired_salary_min": 130000,
    "desired_salary_max": 170000,
    "desired_locations": ["San Antonio, TX", "Austin, TX", "Remote"]
  }
}
```

### Profile 3: Marketing Manager (On-site)

**File:** `services/api/scripts/test_profiles/03_marketing_manager.json`

```json
{
  "name": "Test Profile — Marketing Manager",
  "basics": {
    "name": "Jordan Rivera",
    "email": "test-jordan@example.com",
    "location": "New York, NY",
    "years_of_experience": 6
  },
  "experience": [
    {
      "company": "BrandCo Media",
      "title": "Marketing Manager",
      "start_date": "2022-01",
      "end_date": null,
      "bullets": [
        "Grew organic traffic by 180% YoY through SEO content strategy and technical optimizations",
        "Managed $500K annual paid media budget across Google Ads, Meta, and LinkedIn generating 3.2x ROAS",
        "Led rebranding initiative including brand guidelines, website redesign, and launch campaign reaching 2M impressions"
      ]
    },
    {
      "company": "E-Commerce Startup",
      "title": "Digital Marketing Specialist",
      "start_date": "2019-08",
      "end_date": "2021-12",
      "bullets": [
        "Built and managed email marketing program growing subscriber list from 5K to 45K with 28% open rates",
        "Created social media content calendar producing 200+ posts/month across 4 platforms",
        "Implemented marketing automation workflows in HubSpot reducing lead response time from 24hrs to 2hrs"
      ]
    }
  ],
  "education": [
    {"institution": "NYU", "degree": "BA Marketing", "year": 2019}
  ],
  "skills": ["SEO", "SEM", "Google Ads", "Meta Ads", "HubSpot", "Content Marketing", "Email Marketing", "Social Media", "Google Analytics", "A/B Testing", "Copywriting", "Brand Strategy"],
  "certifications": ["Google Ads Certified", "HubSpot Inbound Marketing"],
  "preferences": {
    "desired_titles": ["Senior Marketing Manager", "Head of Marketing", "Director of Digital Marketing"],
    "remote_preference": "onsite",
    "desired_salary_min": 100000,
    "desired_salary_max": 140000,
    "desired_locations": ["New York, NY", "Brooklyn, NY"]
  }
}
```

### Profile 4: Data Analyst (Remote)

**File:** `services/api/scripts/test_profiles/04_data_analyst_remote.json`

```json
{
  "name": "Test Profile — Data Analyst",
  "basics": {
    "name": "Priya Patel",
    "email": "test-priya@example.com",
    "location": "Chicago, IL",
    "years_of_experience": 4
  },
  "experience": [
    {
      "company": "FinanceData LLC",
      "title": "Data Analyst",
      "start_date": "2022-05",
      "end_date": null,
      "bullets": [
        "Built automated reporting dashboards in Tableau serving 200+ stakeholders across 5 business units",
        "Developed Python ETL pipelines processing 10GB daily from 12 data sources into Snowflake data warehouse",
        "Conducted A/B test analysis for product team resulting in 15% improvement in user conversion rates"
      ]
    },
    {
      "company": "Retail Analytics Co",
      "title": "Junior Data Analyst",
      "start_date": "2021-01",
      "end_date": "2022-04",
      "bullets": [
        "Created SQL-based inventory forecasting model reducing stockout rate by 22%",
        "Automated weekly KPI reports using Python and pandas, saving 8 hours per week of manual work",
        "Collaborated with merchandising team to design customer segmentation model driving targeted campaigns"
      ]
    }
  ],
  "education": [
    {"institution": "University of Chicago", "degree": "BS Statistics", "year": 2020}
  ],
  "skills": ["Python", "SQL", "Tableau", "Excel", "Snowflake", "pandas", "R", "A/B Testing", "ETL", "Statistics", "Data Visualization", "Git"],
  "certifications": ["Tableau Desktop Certified"],
  "preferences": {
    "desired_titles": ["Senior Data Analyst", "Data Scientist", "Analytics Engineer"],
    "remote_preference": "remote_only",
    "desired_salary_min": 90000,
    "desired_salary_max": 130000,
    "desired_locations": ["Remote", "Chicago, IL"]
  }
}
```

### Profile 5: UX Designer (Hybrid)

**File:** `services/api/scripts/test_profiles/05_ux_designer_hybrid.json`

```json
{
  "name": "Test Profile — UX Designer",
  "basics": {
    "name": "Sam Williams",
    "email": "test-sam@example.com",
    "location": "San Francisco, CA",
    "years_of_experience": 5
  },
  "experience": [
    {
      "company": "ProductStudio Inc",
      "title": "Senior UX Designer",
      "start_date": "2023-03",
      "end_date": null,
      "bullets": [
        "Led UX redesign of core SaaS product improving task completion rate by 35% and reducing support tickets by 40%",
        "Conducted 50+ user research interviews and usability tests to validate design decisions",
        "Created and maintained design system with 120+ components in Figma used by 3 product teams"
      ]
    },
    {
      "company": "Digital Agency XYZ",
      "title": "UX/UI Designer",
      "start_date": "2020-06",
      "end_date": "2023-02",
      "bullets": [
        "Designed mobile and web experiences for 12+ client projects across fintech, healthcare, and e-commerce",
        "Built interactive prototypes in Figma and Framer reducing stakeholder review cycles from 3 rounds to 1",
        "Established user research practice including persona development, journey mapping, and heuristic evaluation"
      ]
    }
  ],
  "education": [
    {"institution": "California College of the Arts", "degree": "BFA Interaction Design", "year": 2020}
  ],
  "skills": ["Figma", "Sketch", "Adobe XD", "Framer", "User Research", "Usability Testing", "Wireframing", "Prototyping", "Design Systems", "Information Architecture", "HTML", "CSS"],
  "certifications": ["Google UX Design Certificate"],
  "preferences": {
    "desired_titles": ["Senior UX Designer", "Lead Product Designer", "UX Research Manager"],
    "remote_preference": "hybrid",
    "desired_salary_min": 120000,
    "desired_salary_max": 160000,
    "desired_locations": ["San Francisco, CA", "Remote"]
  }
}
```

---

## 2.2 Match Quality Validation Script

**File to create:** `services/api/scripts/validate_matching.py`

```python
"""
Match quality validation script.
Loads test profiles, runs matching against seeded jobs, and produces a quality report.

Usage: python scripts/validate_matching.py [--profiles all|01|02|03|04|05]
                                            [--min-matches 10]
                                            [--output-dir reports/]
"""
```

### Validation logic

For each test profile:

1. **Create a temporary user** and `candidate_profile` record with the test profile JSON.
2. **Generate embedding** for the profile.
3. **Run the match pipeline** (same logic as `POST /api/matches/refresh`).
4. **Collect top 20 matches** sorted by `match_score` descending.
5. **Evaluate match quality** using the criteria below.
6. **Output a quality report** (JSON + human-readable).
7. **Clean up** the temporary user and profile (rollback or delete).

### Quality criteria (per profile)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Match count** | ≥ 10 per profile | Count of matches with `match_score ≥ 40` |
| **Title relevance** | ≥ 70% of top 10 | Does the job title relate to the candidate's desired titles? (fuzzy match or keyword overlap) |
| **Skill overlap** | ≥ 3 skills per match | Count of matched skills in `reasons.skills.matched` |
| **No hallucination** | 0 fabricated skills | Verify `reasons.skills.matched` are all in the candidate's skill list |
| **Score distribution** | Not all same score | Std deviation of top 20 scores > 5 (scores should vary, not cluster) |
| **Location respect** | ≥ 80% comply | If candidate prefers remote, ≥80% of top 10 should be remote-eligible |
| **Fraud filtering** | 0 fraudulent jobs | No matches where `job.is_likely_fraudulent = true` |
| **Embedding coverage** | ≥ 90% of matched jobs | Matched jobs should have embeddings (semantic score available) |
| **Score range** | Top match ≥ 60 | At least one strong match per profile |
| **Staleness** | 0 expired jobs | No matches where `job.is_active = false` |

### Report output

**File:** `reports/match_quality_report_{timestamp}.json`

```json
{
  "timestamp": "2026-02-09T10:30:00Z",
  "total_active_jobs": 251,
  "profiles_tested": 5,
  "results": [
    {
      "profile": "01_senior_swe_remote",
      "profile_name": "Senior SWE (Remote)",
      "total_matches": 47,
      "matches_above_40": 32,
      "top_match_score": 88,
      "avg_top_10_score": 72.4,
      "score_std_dev": 14.2,
      "title_relevance_pct": 80.0,
      "avg_skill_overlap": 5.2,
      "hallucinated_skills": 0,
      "location_compliance_pct": 100.0,
      "fraudulent_matches": 0,
      "stale_matches": 0,
      "embedding_coverage_pct": 96.0,
      "pass": true,
      "issues": [],
      "top_5_matches": [
        {
          "job_title": "Senior Backend Engineer",
          "company": "GitLab",
          "match_score": 88,
          "semantic_similarity": 0.87,
          "matched_skills": ["Python", "Kubernetes", "Docker", "PostgreSQL", "CI/CD"],
          "missing_skills": ["Terraform"],
          "location_fit": "remote_match"
        }
      ]
    }
  ],
  "summary": {
    "profiles_passed": 5,
    "profiles_failed": 0,
    "avg_match_score": 68.3,
    "avg_title_relevance": 78.0,
    "avg_skill_overlap": 4.8,
    "total_hallucinations": 0,
    "total_fraud_matches": 0,
    "overall_pass": true
  }
}
```

Also generate a human-readable Markdown summary:

**File:** `reports/match_quality_report_{timestamp}.md`

```markdown
# Winnow Match Quality Report
Generated: 2026-02-09 10:30 AM

## Overall: ✅ PASS (5/5 profiles passed)

| Profile | Matches ≥40 | Top Score | Avg Top 10 | Title Rel% | Skills Avg | Location% | Pass |
|---------|-------------|-----------|------------|------------|------------|-----------|------|
| Senior SWE | 32 | 88 | 72.4 | 80% | 5.2 | 100% | ✅ |
| PM/PMP | 28 | 82 | 68.1 | 90% | 4.8 | 85% | ✅ |
| Marketing Mgr | 19 | 75 | 61.3 | 70% | 4.1 | 90% | ✅ |
| Data Analyst | 24 | 79 | 66.7 | 75% | 5.5 | 100% | ✅ |
| UX Designer | 15 | 71 | 58.9 | 80% | 3.8 | 85% | ✅ |

## Issues Found
None

## Recommendations
- Consider adding more healthcare job sources for better coverage
- Marketing profile could benefit from broader keyword synonyms
```

---

## 2.3 End-to-End Tailoring Validation

**File to create:** `services/api/scripts/validate_tailoring.py`

For each test profile, pick the top match and run the tailoring pipeline. Validate:

1. **Tailored resume generated** — DOCX file exists and is non-empty.
2. **No hallucination** — Every employer, title, date, degree, and certification in the tailored resume exists in the source profile.
3. **Keyword integration** — At least 3 keywords from the job description appear in the tailored resume that were not in the original.
4. **Change log present** — `tailored_resumes.change_log` is populated with per-section changes.
5. **File downloadable** — `GET /api/tailor/files/{id}/resume` returns a valid DOCX.

### Grounding check implementation

```python
def validate_grounding(profile_json: dict, tailored_text: str) -> list[str]:
    """
    Check that every factual claim in the tailored resume
    exists in the source profile. Return list of violations.
    """
    violations = []
    
    # Check employers
    profile_companies = {exp["company"].lower() for exp in profile_json.get("experience", [])}
    # ... extract companies from tailored text and compare
    
    # Check titles
    profile_titles = {exp["title"].lower() for exp in profile_json.get("experience", [])}
    # ... extract titles from tailored text and compare
    
    # Check education
    profile_schools = {ed["institution"].lower() for ed in profile_json.get("education", [])}
    # ... extract schools from tailored text and compare
    
    # Check certifications
    profile_certs = {c.lower() for c in profile_json.get("certifications", [])}
    # ... extract certs from tailored text and compare
    
    return violations
```

---

# PART 3 — TUNING & GUARDRAILS

## 3.1 Match Score Weight Tuning

**File to modify:** `services/api/app/services/matching.py`

Based on validation results, you may need to adjust the dimension weights. The current defaults are:

```python
MATCH_WEIGHTS = {
    "skills": 0.30,
    "experience": 0.25,
    "certifications": 0.10,
    "location": 0.15,
    "compensation": 0.10,
    "title": 0.10,
}
```

### Tuning guidelines

- If **title relevance is low** (< 70%): Increase `title` weight to 0.15, decrease `certifications` to 0.05.
- If **location compliance is low** (< 80%): Increase `location` weight to 0.20, decrease `experience` to 0.20.
- If **skill overlap is low** (< 3 avg): Increase `skills` weight to 0.35, decrease `compensation` to 0.05.
- If **scores are too clustered** (std dev < 5): The weights are too balanced — increase the weight of the most differentiating dimension.
- If **all scores are too high** (avg > 80): Apply a penalty for missing must-have skills (e.g., each missing must-have reduces score by 5 points).
- If **all scores are too low** (avg < 40): The scoring may be too strict — check synonym matching and partial skill credit.

### Make weights configurable

Move weights to environment variables so they can be tuned without code changes:

```python
MATCH_WEIGHTS = {
    "skills": float(os.getenv("MATCH_W_SKILLS", "0.30")),
    "experience": float(os.getenv("MATCH_W_EXPERIENCE", "0.25")),
    "certifications": float(os.getenv("MATCH_W_CERTS", "0.10")),
    "location": float(os.getenv("MATCH_W_LOCATION", "0.15")),
    "compensation": float(os.getenv("MATCH_W_COMPENSATION", "0.10")),
    "title": float(os.getenv("MATCH_W_TITLE", "0.10")),
}
```

---

## 3.2 Semantic Blend Ratio Tuning

**File to modify:** `services/api/app/services/matching.py`

The current blend ratio is 65% deterministic / 35% semantic (from PROMPT15).

```python
W_DETERMINISTIC = float(os.getenv("MATCH_W_DETERMINISTIC", "0.65"))
W_SEMANTIC = float(os.getenv("MATCH_W_SEMANTIC", "0.35"))
```

### Tuning guidelines

- If semantic similarity scores are **consistently high** (> 0.85 for unrelated jobs): Reduce `W_SEMANTIC` to 0.25.
- If **related jobs have low semantic scores** (< 0.50): Check embedding quality — regenerate embeddings or switch embedding model.
- If **keyword matching misses obvious good fits**: Increase `W_SEMANTIC` to 0.40.
- The two weights must sum to 1.0.

---

## 3.3 Fraud & Staleness Threshold Tuning

**File to modify:** `services/api/app/services/job_fraud_detector.py`

Review and adjust thresholds based on real data:

```python
# Fraud scoring thresholds
FRAUD_SCORE_THRESHOLD = int(os.getenv("FRAUD_THRESHOLD", "70"))  # Score ≥ this → flagged

# Staleness thresholds
STALE_INACTIVE_DAYS = int(os.getenv("STALE_INACTIVE_DAYS", "90"))    # First seen > N days ago
STALE_NOT_SEEN_DAYS = int(os.getenv("STALE_NOT_SEEN_DAYS", "30"))    # Last seen > N days ago

# Duplicate detection thresholds
DEDUP_FUZZY_THRESHOLD = float(os.getenv("DEDUP_FUZZY_THRESHOLD", "0.85"))
DEDUP_DESCRIPTION_THRESHOLD = float(os.getenv("DEDUP_DESC_THRESHOLD", "0.80"))
```

### Validation checks

After tuning, re-run the validation script and verify:
- Fraudulent job count is < 5% of total (if higher, threshold is too low).
- No legitimate jobs are incorrectly flagged (spot check the flagged jobs).
- Duplicate clusters are correct (spot check 5 clusters).

---

## 3.4 Data Quality Monitoring Endpoint

**File to create or extend:** `services/api/app/routers/admin_jobs.py`

Add an endpoint that reports data quality metrics for ongoing monitoring:

```
GET /api/admin/jobs/quality
Authorization: Bearer {ADMIN_TOKEN}
```

Response:

```json
{
  "embedding_coverage": {
    "total_active": 251,
    "with_embeddings": 245,
    "coverage_pct": 97.6
  },
  "parsing_coverage": {
    "with_parsed_details": 249,
    "coverage_pct": 99.2
  },
  "fraud_stats": {
    "flagged": 4,
    "pct_of_total": 1.6
  },
  "duplicate_stats": {
    "clusters": 12,
    "total_duplicates": 31,
    "pct_of_total": 12.4
  },
  "staleness": {
    "active": 251,
    "stale_marked_inactive": 36,
    "oldest_active_days": 25
  },
  "source_health": {
    "remotive": {"last_fetch": "2026-02-09T06:00:00Z", "last_count": 47, "status": "healthy"},
    "themuse": {"last_fetch": "2026-02-09T06:00:00Z", "last_count": 50, "status": "healthy"},
    "greenhouse": {"last_fetch": "2026-02-09T06:00:00Z", "last_count": 52, "status": "healthy"},
    "lever": {"last_fetch": "2026-02-09T06:00:00Z", "last_count": 24, "status": "healthy"}
  }
}
```

---

## File and Component Reference

| File | Action | Purpose |
|------|--------|---------|
| `services/api/scripts/seed_jobs.py` | Create | Bulk job ingestion script |
| `services/api/scripts/validate_matching.py` | Create | Match quality validation with report output |
| `services/api/scripts/validate_tailoring.py` | Create | End-to-end tailoring validation |
| `services/api/scripts/test_profiles/01_senior_swe_remote.json` | Create | Test profile: Senior SWE |
| `services/api/scripts/test_profiles/02_project_manager_pmp.json` | Create | Test profile: PM/PMP |
| `services/api/scripts/test_profiles/03_marketing_manager.json` | Create | Test profile: Marketing Manager |
| `services/api/scripts/test_profiles/04_data_analyst_remote.json` | Create | Test profile: Data Analyst |
| `services/api/scripts/test_profiles/05_ux_designer_hybrid.json` | Create | Test profile: UX Designer |
| `services/api/app/services/job_sources/greenhouse.py` | Create (if missing) | Greenhouse public board adapter |
| `services/api/app/services/job_sources/lever.py` | Create (if missing) | Lever public postings adapter |
| `services/api/app/services/job_sources/__init__.py` | Modify | Register new source adapters |
| `services/api/app/routers/admin_jobs.py` | Create | Admin job stats + quality endpoints |
| `services/api/app/main.py` | Modify | Register admin_jobs router |
| `services/api/app/services/matching.py` | Modify | Make weights configurable via env vars |
| `services/api/app/services/job_fraud_detector.py` | Modify | Make thresholds configurable via env vars |
| `services/api/.env` | Modify | Add JOB_SOURCES, board tokens, weight overrides |
| `reports/` | Create (directory) | Match quality report output |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: New Source Adapters (Steps 1–3)

1. **Step 1:** Create `services/api/app/services/job_sources/greenhouse.py` (Part 1.2 — Greenhouse adapter).
2. **Step 2:** Create `services/api/app/services/job_sources/lever.py` (Part 1.2 — Lever adapter).
3. **Step 3:** Update `services/api/app/services/job_sources/__init__.py` to register new adapters (Part 1.3). Update `services/api/.env` with `JOB_SOURCES`, `GREENHOUSE_BOARDS`, `LEVER_COMPANIES`.

### Phase 2: Bulk Seeding (Steps 4–6)

4. **Step 4:** Create `services/api/scripts/seed_jobs.py` (Part 1.1).
5. **Step 5:** Run the seed script: 
    ```powershell
    cd services/api
    python scripts/seed_jobs.py --categories all --max-per-source 100
    ```
6. **Step 6:** Verify the worker processes all queued parse + embed jobs. Check the jobs table has 200+ records. Check that embeddings and parsed details are populated:
    ```powershell
    cd services/api
    python -c "from app.db import SessionLocal; db = SessionLocal(); print(db.execute('SELECT COUNT(*) FROM jobs WHERE is_active = true').scalar())"
    ```

### Phase 3: Admin Endpoints (Steps 7–8)

7. **Step 7:** Create `services/api/app/routers/admin_jobs.py` with `GET /api/admin/jobs/stats` and `GET /api/admin/jobs/quality` (Parts 1.5 + 3.4).
8. **Step 8:** Register the router in `services/api/app/main.py`.

### Phase 4: Test Profiles (Steps 9–10)

9. **Step 9:** Create the `services/api/scripts/test_profiles/` directory and all 5 JSON profile files (Part 2.1).
10. **Step 10:** Review each profile to ensure skills, titles, and preferences are realistic and internally consistent.

### Phase 5: Validation Scripts (Steps 11–13)

11. **Step 11:** Create `services/api/scripts/validate_matching.py` (Part 2.2).
12. **Step 12:** Create `services/api/scripts/validate_tailoring.py` (Part 2.3).
13. **Step 13:** Run the match validation script:
    ```powershell
    cd services/api
    python scripts/validate_matching.py --profiles all --output-dir reports/
    ```
    Review the generated report. If any profile fails, proceed to Phase 6 (tuning).

### Phase 6: Tuning (Steps 14–16)

14. **Step 14:** Make match weights configurable via env vars (Part 3.1). Update `services/api/app/services/matching.py`.
15. **Step 15:** Make semantic blend ratio configurable via env vars (Part 3.2). Update `services/api/app/services/matching.py`.
16. **Step 16:** Make fraud/staleness thresholds configurable via env vars (Part 3.3). Update `services/api/app/services/job_fraud_detector.py`.

### Phase 7: Re-validate + Tailoring Check (Steps 17–19)

17. **Step 17:** Re-run `validate_matching.py` after tuning. All 5 profiles should pass.
18. **Step 18:** Run `validate_tailoring.py` to verify end-to-end resume generation. Zero hallucinations required.
19. **Step 19:** Spot-check 3 tailored resumes manually: open the DOCX files, verify the content makes sense, and confirm no invented data.

### Phase 8: Lint + Commit (Step 20)

20. **Step 20:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- Scraping LinkedIn, Indeed, or Google Jobs (terms of service violation).
- Building a custom web scraper for arbitrary company career pages.
- Real-time salary data from external APIs (use job posting data only).
- ML model training for match quality (keep scoring deterministic and rule-based).
- User-facing job search/browse UI changes (this is backend seeding + validation).
- Automated re-tuning of weights (manual tuning only for v1).
- Multi-language job support (English only for v1).
- Job alerts or notifications based on new ingested jobs (future feature).

---

## Summary Checklist

### Part 1 — Job Seeding
- [ ] Greenhouse adapter created (`job_sources/greenhouse.py`) with 10 default board tokens
- [ ] Lever adapter created (`job_sources/lever.py`) with 5 default company slugs
- [ ] Source registry updated to include `greenhouse` and `lever`
- [ ] `.env` updated with `JOB_SOURCES`, `GREENHOUSE_BOARDS`, `LEVER_COMPANIES`
- [ ] Bulk seed script created (`scripts/seed_jobs.py`) with CLI args, dedup, logging
- [ ] Seed script run successfully — 200+ jobs in database
- [ ] Worker processed all parse + embed jobs — embeddings and parsed details populated
- [ ] Admin stats endpoint (`GET /api/admin/jobs/stats`) working

### Part 2 — Match Quality Validation
- [ ] 5 test profile JSON files created in `scripts/test_profiles/`
- [ ] Match validation script created (`scripts/validate_matching.py`)
- [ ] Tailoring validation script created (`scripts/validate_tailoring.py`)
- [ ] Match validation run — all 5 profiles pass quality criteria
- [ ] Tailoring validation run — zero hallucinations across all profiles
- [ ] Quality report generated in `reports/` (JSON + Markdown)

### Part 3 — Tuning & Guardrails
- [ ] Match weights configurable via env vars (`MATCH_W_SKILLS`, etc.)
- [ ] Semantic blend ratio configurable via env vars (`MATCH_W_DETERMINISTIC`, `MATCH_W_SEMANTIC`)
- [ ] Fraud/staleness thresholds configurable via env vars
- [ ] Data quality endpoint (`GET /api/admin/jobs/quality`) working
- [ ] Re-validation passes after tuning
- [ ] Linted and formatted

Return code changes only.
