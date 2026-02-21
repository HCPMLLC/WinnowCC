# PROMPT 51: Career Management Features — PRO Tier Retention Engine

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPTs 1–55 before making changes.

---

## Purpose

Transform Winnow from a "job search tool you cancel after you land a job" into a **career growth platform candidates keep for years**. These six PRO-only features give subscribers continuous value even when they're not actively job hunting — dramatically reducing churn and increasing lifetime value.

**Strategic Insight:** LinkedIn retains users because it's a career identity platform, not just a job board. Winnow's Career Management features create the same stickiness but with *actionable intelligence* LinkedIn doesn't provide.

---

## What Already Exists (DO NOT Recreate)

1. **Profile versioning:** `candidate_profiles.profile_version` increments on update (PROMPT2, PROMPT14)
2. **Profile JSON:** Full structured profile with skills, experience, certifications (PROMPT14)
3. **Skill gap analysis:** Per-match skill gap display in matching service (PROMPT14)
4. **Job ingestion pipeline:** Multi-source job ingestion with embeddings (PROMPT28)
5. **Matching engine:** Semantic + keyword matching with `match_score` and `interview_probability` (PROMPT7, PROMPT14)
6. **Billing/subscription system:** Stripe integration with `check_and_increment_usage()` and `get_user_plan()` (PROMPT20/PROMPT39)
7. **Salary data in jobs:** `salary_min`, `salary_max` fields on ingested jobs (PROMPT10, PROMPT33)
8. **Sieve AI chatbot:** Context-aware assistant with proactive triggers (PROMPT18, PROMPT24)
9. **Market intelligence service:** `services/api/app/services/market_intelligence.py` for employer-side salary benchmarks (PROMPT54)
10. **Notification service:** `services/api/app/services/candidate_notifications.py` (PROMPT48)

---

## Implementation Sequence

Build these features **in this exact order** — each builds on the previous:

| Phase | Feature | Depends On | Estimated Effort |
|-------|---------|------------|-----------------|
| 1 | Resume Version Manager | Existing profile versioning | Medium |
| 2 | Skill Gap Analysis Dashboard | Phase 1 + existing matching | Medium |
| 3 | Salary Benchmarking (Candidate) | Existing job salary data + PROMPT54 service | Medium |
| 4 | Market Monitoring & Passive Alerts | Phase 2 + existing job ingestion | Large |
| 5 | Annual Review Prep Generator | Phases 1–3 | Medium |
| 6 | Career Dashboard Hub (Frontend) | Phases 1–5 | Large |

---

## Phase 1: Resume Version Manager

### What It Does
Candidates can maintain **named resume versions** (not just auto-incremented profile versions). Think "General", "Leadership Focus", "Technical Focus", "Government", etc. Each version tracks what changed and when, with the ability to compare versions side-by-side and revert.

### Why It Retains Subscribers
Even employed people periodically update their resume. Winnow becomes their resume management system — like Google Docs for career documents.

### Database Migration

**File to create:** `services/api/alembic/versions/xxxx_add_resume_versions.py`

```sql
-- New table: named resume versions
CREATE TABLE resume_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version_name VARCHAR(100) NOT NULL,          -- "General", "Tech Lead", etc.
    version_number INTEGER NOT NULL DEFAULT 1,   -- Auto-increments per user
    profile_snapshot JSONB NOT NULL,             -- Full profile_json at time of save
    change_summary TEXT,                         -- AI-generated "what changed" description
    change_details JSONB,                        -- Structured diff from previous version
    is_primary BOOLEAN NOT NULL DEFAULT false,   -- Which version is the "active" one
    tags VARCHAR(50)[],                          -- User-defined tags: "tech", "leadership"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id, version_name)
);

CREATE INDEX idx_resume_versions_user ON resume_versions(user_id);
CREATE INDEX idx_resume_versions_primary ON resume_versions(user_id, is_primary) WHERE is_primary = true;
```

### Backend Service

**File to create:** `services/api/app/services/career_management.py`

This is the **main service file** for all Career Management features. Start with resume versioning functions:

```python
"""
Career Management Service — PRO feature set
Handles: resume versions, skill analysis, salary benchmarks, 
         market monitoring, annual review prep
"""

from uuid import UUID
from sqlalchemy.orm import Session
from app.services.billing import get_user_plan
from fastapi import HTTPException

# --- Resume Version Manager ---

async def create_resume_version(
    user_id: UUID, 
    version_name: str, 
    profile_json: dict, 
    db: Session
) -> dict:
    """
    Save current profile as a named version.
    - PRO only (check plan first)
    - Auto-generates change_summary by diffing against previous version
    - Sets as primary if it's the first version
    """

async def list_resume_versions(user_id: UUID, db: Session) -> list[dict]:
    """Return all saved versions for this user, newest first."""

async def compare_versions(
    user_id: UUID, 
    version_id_a: UUID, 
    version_id_b: UUID, 
    db: Session
) -> dict:
    """
    Side-by-side diff of two resume versions.
    Returns: {added_skills: [], removed_skills: [], 
              added_experience: [], modified_sections: []}
    """

async def set_primary_version(user_id: UUID, version_id: UUID, db: Session) -> dict:
    """Set which version is used for matching."""

async def revert_to_version(user_id: UUID, version_id: UUID, db: Session) -> dict:
    """
    Copy a previous version's profile_json back to the active profile.
    Creates a new version entry (so history is preserved).
    """
```

### Backend Router

**File to create:** `services/api/app/routers/career.py`

```python
# All endpoints require PRO subscription
# Register in main.py: app.include_router(career_router, prefix="/api/career")

GET  /api/career/versions                    — list all resume versions
POST /api/career/versions                    — save current profile as named version
GET  /api/career/versions/{id}               — get a specific version
GET  /api/career/versions/compare?a={id}&b={id} — diff two versions
PUT  /api/career/versions/{id}/primary       — set as primary version
POST /api/career/versions/{id}/revert        — revert profile to this version
DELETE /api/career/versions/{id}             — delete a version (not the primary)
```

**PRO Gate:** At the top of every endpoint handler, add:
```python
plan = get_user_plan(user.id, db)
if plan == "free":
    raise HTTPException(status_code=403, detail="Resume versioning requires Winnow Pro. Upgrade in Settings.")
```

### Frontend Page

**File to create:** `apps/web/app/career/versions/page.tsx`

Route: `/career/versions`

UI elements:
1. **Version list** — Cards showing: version name, created date, tag pills, "Primary" badge
2. **"Save Current Profile"** button — Opens modal to name the version and add tags
3. **Compare button** — Select two versions → shows side-by-side diff with green (added) / red (removed) highlighting
4. **Revert button** — Confirmation modal: "This will update your active profile to match this version. Your current profile will be auto-saved first."
5. **PRO gate** — If free user visits this page, show feature preview with upgrade CTA

---

## Phase 2: Skill Gap Analysis Dashboard

### What It Does
Aggregates skill gap data across ALL of a candidate's matches into a **single career intelligence view**: "These are the 10 skills that appear most often in jobs you're qualified for but don't have yet." Includes learning resource suggestions.

### Why It Retains Subscribers
Gives candidates a continuous improvement roadmap. Even when not job hunting, they can track their professional development against market demand.

### Database Migration

**File to create:** `services/api/alembic/versions/xxxx_add_skill_gap_tracking.py`

```sql
-- Aggregated skill demand tracking per user
CREATE TABLE skill_gap_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    
    -- Aggregated from all matches at snapshot time
    top_missing_skills JSONB NOT NULL,    -- [{skill, frequency, avg_match_boost, category}]
    top_matched_skills JSONB NOT NULL,    -- [{skill, frequency, match_count}]
    skill_trend JSONB,                    -- Comparison vs previous snapshot
    total_matches_analyzed INTEGER NOT NULL,
    avg_match_score NUMERIC(5,2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id, snapshot_date)
);

CREATE INDEX idx_skill_gaps_user_date ON skill_gap_snapshots(user_id, snapshot_date DESC);
```

### Backend Service

**Add to:** `services/api/app/services/career_management.py`

```python
# --- Skill Gap Analysis ---

async def generate_skill_gap_snapshot(user_id: UUID, db: Session) -> dict:
    """
    Analyze all current matches (last 15 days, score 50+) and aggregate:
    - Top 15 missing skills (ranked by frequency across job postings)
    - For each: how many jobs require it, estimated match score boost if acquired
    - Trend vs. last snapshot (new gaps, closed gaps, persistent gaps)
    
    PRO only. Runs on-demand or via weekly scheduled job.
    """

async def get_skill_gap_history(user_id: UUID, months: int, db: Session) -> list[dict]:
    """Return skill gap snapshots for the last N months — shows career growth over time."""

async def get_learning_recommendations(skill_name: str, category: str) -> list[dict]:
    """
    For a given missing skill, suggest learning resources.
    Returns: [{source, title, url, type, estimated_hours}]
    Sources: Coursera, Udemy, YouTube, official docs, certification programs.
    
    NOTE: Static/curated list initially. Can integrate APIs later.
    """
```

### Backend Router

**Add to:** `services/api/app/routers/career.py`

```python
POST /api/career/skill-gaps/refresh         — generate new skill gap snapshot
GET  /api/career/skill-gaps/current         — latest snapshot
GET  /api/career/skill-gaps/history?months=6 — historical trend
GET  /api/career/skill-gaps/recommendations/{skill} — learning resources for a skill
```

### Frontend Page

**File to create:** `apps/web/app/career/skills/page.tsx`

Route: `/career/skills`

UI elements:
1. **Missing Skills chart** — Horizontal bar chart: skill name → frequency (how many jobs need it). Color-coded by category (technical, methodology, soft skill)
2. **Matched Skills summary** — "You match on these skills across X jobs" (confidence booster)
3. **Trend indicators** — ↑ New gap, ↓ Gap closed (you learned it!), → Persistent gap
4. **Learning resources** — Click a missing skill → expandable panel with Coursera/Udemy/YouTube links
5. **Historical timeline** — Line chart showing avg match score over time (motivates continuous improvement)
6. **"Refresh Analysis"** button — Triggers new snapshot generation

### Background Job

**Add to:** `services/api/app/worker.py`

```python
# Weekly skill gap snapshot for all PRO users
# Schedule: Every Sunday at 2:00 AM UTC
def scheduled_skill_gap_snapshots():
    """Generate fresh skill gap snapshots for all active PRO subscribers."""
```

---

## Phase 3: Salary Benchmarking (Candidate-Facing)

### What It Does
Shows candidates where their target salary falls relative to the market for their role and location. Leverages the same `market_intelligence.py` service built for employers in PROMPT54, but with a candidate-optimized view.

### Why It Retains Subscribers
Salary data is **the #1 reason** people search job boards even when employed. If Winnow provides ongoing salary intelligence, candidates keep their subscription to stay informed.

### Backend Service

**Add to:** `services/api/app/services/career_management.py`

```python
# --- Salary Benchmarking ---

async def get_candidate_salary_benchmark(user_id: UUID, db: Session) -> dict:
    """
    Based on candidate's target titles and locations (from profile preferences):
    - 25th, 50th, 75th percentile salaries from Winnow's job database
    - Where their current salary expectation falls (if provided)
    - Trend vs. 90 days ago (market moving up/down?)
    - Sample size for confidence indicator
    - Breakdown by remote vs. on-site vs. hybrid
    
    Reuses get_salary_benchmarks() from market_intelligence.py but
    runs it for each of the candidate's target title/location combos.
    """

async def get_salary_by_skill_premium(user_id: UUID, db: Session) -> dict:
    """
    Which of the candidate's skills command the highest salary premiums?
    E.g., "Jobs requiring Kubernetes pay 12% more than similar roles without it."
    
    Calculated by comparing median salaries of jobs with vs. without each skill.
    """
```

### Backend Router

**Add to:** `services/api/app/routers/career.py`

```python
GET /api/career/salary/benchmark         — salary ranges for candidate's target roles
GET /api/career/salary/skill-premiums    — which skills boost pay the most
```

### Frontend Page

**File to create:** `apps/web/app/career/salary/page.tsx`

Route: `/career/salary`

UI elements:
1. **Salary range visualization** — For each target title: box-and-whisker plot showing 25th/50th/75th percentile. Candidate's target salary marked with an arrow
2. **Market trend indicator** — "Software Engineer salaries in Austin are ↑ 3.2% vs. 90 days ago"
3. **Remote vs. On-site comparison** — Side-by-side salary ranges
4. **Skill premium table** — "Your top 5 highest-value skills": skill → average salary premium %
5. **Confidence indicator** — "Based on 247 job postings" (low sample = caveat shown)
6. **Location comparison** — If candidate has multiple target locations, compare salaries across them

---

## Phase 4: Market Monitoring & Passive Job Alerts

### What It Does
Even when candidates aren't actively searching, Winnow quietly monitors the market and sends **weekly digest emails** or **push notifications** when something noteworthy happens: a dream company posts a role, their target salary range shifts, a surge in demand for their skills, etc.

### Why It Retains Subscribers
This is the **#1 retention feature**. Passive candidates (the majority of employed professionals) stay subscribed because Winnow watches the market for them. When they're ready to move, Winnow already knows the landscape.

### Database Migration

**File to create:** `services/api/alembic/versions/xxxx_add_market_monitoring.py`

```sql
-- User's monitoring preferences
CREATE TABLE market_watch_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- What to watch
    watch_companies VARCHAR(200)[],           -- Dream companies: ["Google", "Stripe", "Anthropic"]
    watch_titles VARCHAR(200)[],              -- Specific titles beyond profile preferences
    watch_skills VARCHAR(100)[],              -- Emerging skills to track demand for
    watch_salary_threshold NUMERIC(10,2),     -- Alert if jobs exceed this salary
    watch_remote_only BOOLEAN DEFAULT false,  -- Only alert for remote roles
    
    -- How to notify
    digest_frequency VARCHAR(20) NOT NULL DEFAULT 'weekly',  -- 'daily', 'weekly', 'monthly', 'off'
    digest_day INTEGER DEFAULT 1,             -- Day of week (1=Mon) for weekly, day of month for monthly
    push_enabled BOOLEAN DEFAULT true,        -- Mobile/browser push notifications
    email_enabled BOOLEAN DEFAULT true,       -- Email digests
    
    -- Thresholds
    min_match_score INTEGER DEFAULT 70,       -- Only alert for matches above this score
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- Market alert history (what we've sent)
CREATE TABLE market_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,           -- 'dream_company', 'salary_surge', 'skill_demand', 'high_match'
    alert_data JSONB NOT NULL,                 -- Type-specific payload
    job_id INTEGER REFERENCES jobs(id),        -- If triggered by a specific job
    sent_via VARCHAR(20) NOT NULL,             -- 'email', 'push', 'in_app'
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,                       -- When user opened/clicked
    dismissed_at TIMESTAMPTZ
);

CREATE INDEX idx_market_alerts_user ON market_alerts(user_id, sent_at DESC);
CREATE INDEX idx_market_watch_user ON market_watch_config(user_id);
```

### Backend Service

**Add to:** `services/api/app/services/career_management.py`

```python
# --- Market Monitoring ---

async def scan_market_for_user(user_id: UUID, db: Session) -> list[dict]:
    """
    Run during digest generation. Checks:
    1. New jobs from watch_companies matching candidate's skills
    2. Jobs exceeding salary_threshold
    3. Significant demand increase for candidate's skills (20%+ vs. last period)
    4. High-scoring matches (above min_match_score) posted since last scan
    5. New remote opportunities in candidate's target titles
    
    Returns list of alert objects to be sent.
    """

async def generate_weekly_digest(user_id: UUID, db: Session) -> dict:
    """
    Compile all alerts since last digest into an email-ready summary.
    Returns: {highlights: [], new_matches_count, salary_trend, skill_demand_changes}
    """

async def update_watch_config(user_id: UUID, config: dict, db: Session) -> dict:
    """Update the user's monitoring preferences."""

async def get_alert_history(user_id: UUID, limit: int, db: Session) -> list[dict]:
    """Recent alerts with read/dismissed status."""
```

### Backend Router

**Add to:** `services/api/app/routers/career.py`

```python
GET  /api/career/monitoring/config           — get current watch configuration
PUT  /api/career/monitoring/config           — update watch preferences
GET  /api/career/monitoring/alerts?limit=20  — recent alerts
POST /api/career/monitoring/alerts/{id}/read — mark alert as read
GET  /api/career/monitoring/preview          — preview: what would trigger right now?
```

### Background Jobs

**Add to:** `services/api/app/worker.py`

```python
# Daily market scan for all PRO users with monitoring enabled
# Schedule: Every day at 6:00 AM UTC
def scheduled_market_scan():
    """
    For each PRO user with monitoring enabled:
    1. Run scan_market_for_user()
    2. Store alerts in market_alerts table
    3. If digest_frequency matches today, generate and send digest email
    """
```

### Email Template

**File to create:** `services/api/app/templates/market_digest.html`

Weekly digest email with:
- "Your Market Pulse" header with Winnow branding
- Highlight cards for dream company postings and high-scoring matches
- Salary trend summary for target roles
- Skill demand changes (rising/falling)
- CTA: "View Full Details in Winnow"

### Frontend Page

**File to create:** `apps/web/app/career/monitoring/page.tsx`

Route: `/career/monitoring`

UI elements:
1. **Watch configuration form** — Add/remove companies, titles, skills to monitor. Set salary threshold. Toggle digest frequency
2. **Recent alerts feed** — Timeline of alerts with type icons, timestamps, and job links
3. **"Preview Alerts"** button — Shows what would trigger right now (helps users tune their config)
4. **Digest preview** — Shows what the next email digest would look like

---

## Phase 5: Annual Review Prep Generator

### What It Does
Uses the candidate's resume versions, skill gap history, and job market data to generate a **structured annual review document** — accomplishments summary, market positioning statement, skill growth evidence, and talking points for salary negotiation.

### Why It Retains Subscribers
Annual reviews happen once a year — but candidates start thinking about them months in advance. This feature creates a natural annual renewal cycle and directly ties to salary benchmarking data.

### Backend Service

**Add to:** `services/api/app/services/career_management.py`

```python
# --- Annual Review Prep ---

async def generate_review_prep(user_id: UUID, period_months: int, db: Session) -> dict:
    """
    Compile career data from the last N months into a review prep document.
    
    Uses Claude (Anthropic API) to generate:
    
    1. ACCOMPLISHMENTS SUMMARY
       - Extracted from profile changes (new roles, promotions, skills added)
       - Bullet points formatted for performance review conversations
    
    2. MARKET POSITIONING
       - "Your target roles pay [range] in [location]"
       - "Your salary is at the Xth percentile for your experience level"
       - Based on salary benchmarking data
    
    3. SKILL GROWTH EVIDENCE
       - Skills added since last review period (from version history)
       - Certifications earned
       - Skill gaps closed (from skill gap snapshots)
    
    4. SALARY NEGOTIATION TALKING POINTS
       - Market rate data for their title + location
       - Skill premiums they can cite
       - Industry trend context
    
    5. CAREER DEVELOPMENT PLAN
       - Top 3 skills to develop next (from current gaps)
       - Suggested learning resources
       - Projected match score improvement
    
    Returns structured JSON. Frontend renders it. Also generates DOCX export.
    
    GROUNDING RULES (same as resume tailoring):
    - ONLY reference accomplishments from the candidate's actual profile
    - NEVER fabricate metrics, results, or achievements
    - Market data must cite sample sizes
    - Salary claims must include confidence ranges
    """
```

### Backend Router

**Add to:** `services/api/app/routers/career.py`

```python
POST /api/career/review-prep/generate?months=12  — generate review prep document
GET  /api/career/review-prep/latest               — get most recent review prep
GET  /api/career/review-prep/export/{id}          — download as DOCX
```

### Frontend Page

**File to create:** `apps/web/app/career/review/page.tsx`

Route: `/career/review`

UI elements:
1. **Period selector** — "Generate review prep for last: 6 months | 12 months | 18 months"
2. **Five-section document viewer** — Renders each section with professional formatting
3. **"Export as Word"** button — Downloads DOCX using existing tailored resume DOCX generation pattern
4. **"Share with Manager"** option — Generates a shareable (redacted) version without salary data
5. **Edit capability** — User can tweak bullet points before exporting

---

## Phase 6: Career Dashboard Hub (Frontend)

### What It Does
A single `/career` landing page that ties all five features together into a cohesive career management experience with a navigation sidebar.

### Frontend Page

**File to create:** `apps/web/app/career/page.tsx`

Route: `/career` (landing page with overview cards)

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  🎯 Career Management                          [PRO]    │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ Sidebar  │  Career Health Score: 78/100                 │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│ • Overview│  │ Resume   │ │ Skills   │ │ Salary   │     │
│ • Resumes│  │ Versions │ │ Gaps     │ │ Benchmark│     │
│ • Skills │  │   4 saved│ │ 3 closed │ │ 72nd %ile│     │
│ • Salary │  └──────────┘ └──────────┘ └──────────┘     │
│ • Monitor│                                              │
│ • Review │  ┌──────────┐ ┌──────────┐                   │
│          │  │ Market   │ │ Review   │                   │
│          │  │ Monitor  │ │ Prep     │                   │
│          │  │ 3 alerts │ │ Due Apr  │                   │
│          │  └──────────┘ └──────────┘                   │
│          │                                              │
│          │  Recent Activity                             │
│          │  • Skill gap: "Kubernetes" closed ✓          │
│          │  • New alert: Stripe posted Sr. PM role      │
│          │  • Salary trend: +2.1% in Austin market      │
│          │                                              │
└──────────┴──────────────────────────────────────────────┘
```

**Career Health Score** — Composite metric (0–100) based on:
- Profile completeness (20%)
- Resume versions saved (10%)
- Skill gap trend (improving?) (25%)
- Salary positioning (15%)
- Market monitoring active (10%)
- Review prep current (20%)

### Navigation Integration

**File to modify:** `apps/web/components/Navbar.tsx` (or wherever main nav lives)

Add "Career" to the main navigation for PRO users. Show a lock icon for free users with tooltip: "Upgrade to PRO to unlock Career Management."

---

## PRO Gating Strategy

### How Each Feature Is Gated

| Feature | Free Tier | PRO Tier |
|---------|-----------|----------|
| Resume Versions | Can view (read-only, max 1 auto-saved) | Unlimited named versions, compare, revert |
| Skill Gap Analysis | See top 3 missing skills per match | Full dashboard, history, learning resources |
| Salary Benchmarking | See "salary range" on individual matches | Full benchmark dashboard with trends |
| Market Monitoring | None | Full monitoring with custom alerts |
| Annual Review Prep | None | Full generation and DOCX export |
| Career Dashboard | Teaser with upgrade CTAs | Full access |

### Implementation Pattern

Every career endpoint should follow this pattern:

```python
from app.services.billing import get_user_plan

async def career_endpoint(user=Depends(get_current_user), db=Depends(get_db)):
    plan = get_user_plan(user.id, db)
    
    if plan == "free":
        # Option A: Block entirely
        raise HTTPException(
            status_code=403, 
            detail="This feature requires Winnow Pro. Upgrade in Settings to unlock Career Management."
        )
        
        # Option B: Return limited data (for teaser features)
        return {"limited": True, "data": limited_results, "upgrade_cta": True}
```

---

## Sieve AI Integration

### New Proactive Triggers

**File to modify:** `services/api/app/services/sieve_triggers.py` (or wherever triggers are defined)

Add three new trigger types:

```python
# Trigger 8: Skill gap opportunity
# Fires when: A new high-scoring match has a skill gap the user is close to closing
"You're 1 skill away from being a 90+ match for [Job Title] at [Company]. 
Consider learning [Skill] — here are some resources."

# Trigger 9: Market shift alert  
# Fires when: Salary benchmarks shift significantly for user's target roles
"Heads up — salaries for [Title] in [Location] have increased 5% this quarter. 
Check your salary benchmark for details."

# Trigger 10: Review prep reminder
# Fires when: It's been 11+ months since last review prep generation
"Your annual review might be coming up. Want me to generate a fresh review 
prep document based on your career progress this year?"
```

---

## Testing Checklist

### Phase 1: Resume Versions
- [ ] Save current profile as named version
- [ ] List all versions with correct ordering
- [ ] Compare two versions — diff shows additions/removals correctly
- [ ] Set a version as primary
- [ ] Revert to a previous version (auto-saves current first)
- [ ] Delete a non-primary version
- [ ] Cannot delete the primary version
- [ ] Free user sees upgrade prompt, cannot save versions

### Phase 2: Skill Gap Dashboard
- [ ] Skill gap snapshot generates from current matches
- [ ] Top missing skills ranked by frequency
- [ ] Historical trend shows improvement over time
- [ ] Learning resources load for each missing skill
- [ ] Weekly background job runs for all PRO users
- [ ] Free user sees top 3 only with upgrade CTA

### Phase 3: Salary Benchmarking
- [ ] Benchmark loads for each target title/location combo
- [ ] Percentile visualization renders correctly
- [ ] Trend indicator shows direction vs. 90 days ago
- [ ] Skill premium table shows top 5 highest-value skills
- [ ] Remote vs. on-site comparison renders
- [ ] Low sample size shows confidence warning

### Phase 4: Market Monitoring
- [ ] Save watch configuration (companies, titles, skills, salary threshold)
- [ ] Market scan detects new jobs from watched companies
- [ ] Salary surge alerts trigger correctly
- [ ] Weekly digest email sends on correct day
- [ ] Alert read/dismiss tracking works
- [ ] Preview shows current triggers
- [ ] Background job runs daily for all configured PRO users

### Phase 5: Annual Review Prep
- [ ] Generate review prep for 6/12/18 month periods
- [ ] Accomplishments extracted from actual profile history (no hallucination)
- [ ] Market positioning uses real salary data
- [ ] Skill growth shows changes from version history
- [ ] DOCX export downloads correctly
- [ ] Salary data excluded from "Share with Manager" version

### Phase 6: Career Dashboard
- [ ] Career Health Score calculates correctly
- [ ] All six feature cards show accurate summary data
- [ ] Recent activity feed populates
- [ ] Sidebar navigation works to all sub-pages
- [ ] PRO gate shows upgrade CTA for free users
- [ ] "Career" appears in main nav for PRO users

---

## Files Summary

### New Files to Create
| # | File Path | Purpose |
|---|-----------|---------|
| 1 | `services/api/alembic/versions/xxxx_add_resume_versions.py` | Resume versions table migration |
| 2 | `services/api/alembic/versions/xxxx_add_skill_gap_tracking.py` | Skill gap snapshots table migration |
| 3 | `services/api/alembic/versions/xxxx_add_market_monitoring.py` | Market watch + alerts tables migration |
| 4 | `services/api/app/services/career_management.py` | All career management business logic |
| 5 | `services/api/app/models/career.py` | SQLAlchemy models for new tables |
| 6 | `services/api/app/routers/career.py` | All career management API endpoints |
| 7 | `services/api/app/schemas/career.py` | Pydantic request/response schemas |
| 8 | `services/api/app/templates/market_digest.html` | Weekly digest email template |
| 9 | `apps/web/app/career/page.tsx` | Career dashboard hub |
| 10 | `apps/web/app/career/versions/page.tsx` | Resume version manager UI |
| 11 | `apps/web/app/career/skills/page.tsx` | Skill gap dashboard UI |
| 12 | `apps/web/app/career/salary/page.tsx` | Salary benchmarking UI |
| 13 | `apps/web/app/career/monitoring/page.tsx` | Market monitoring config + alerts UI |
| 14 | `apps/web/app/career/review/page.tsx` | Annual review prep generator UI |
| 15 | `apps/web/app/career/layout.tsx` | Shared layout with sidebar nav |

### Existing Files to Modify
| # | File Path | What to Change |
|---|-----------|---------------|
| 1 | `services/api/app/main.py` | Register career router |
| 2 | `services/api/app/worker.py` | Add weekly skill gap + daily market scan scheduled jobs |
| 3 | `services/api/app/services/billing.py` | Add career feature limits to plan definitions |
| 4 | `apps/web/components/Navbar.tsx` | Add "Career" nav link (PRO badge) |
| 5 | `services/api/app/services/sieve_triggers.py` | Add triggers 8, 9, 10 |
| 6 | `services/api/app/services/market_intelligence.py` | Expose candidate-facing salary benchmark function |

---

## Step-by-Step Execution Order (for Cursor)

When you're ready to implement, paste each phase as a separate Cursor prompt **in order:**

1. **Phase 1 first** — Creates the `career_management.py` service file and `career.py` router that all later phases add to
2. **Phase 2 second** — Adds skill gap functions to the same service file
3. **Phase 3 third** — Adds salary functions, reuses PROMPT54's market intelligence
4. **Phase 4 fourth** — The largest phase; adds monitoring tables, background jobs, email templates
5. **Phase 5 fifth** — Depends on data from phases 1–3 (version history, skill gaps, salary data)
6. **Phase 6 last** — The frontend hub that ties everything together

After each phase, run:
```powershell
# Backend lint
cd services/api
python -m ruff check .
python -m ruff format .

# Frontend lint  
cd ../../apps/web
npm run lint
```

---

## Non-Goals (Do NOT Implement in This Prompt)

- LinkedIn profile sync (future integration)
- Automated skill assessment/quizzes
- Mentorship matching
- Career path prediction AI
- Integration with external learning platforms (Coursera API, etc.)
- Social features (comparing with peers)
- Resume design templates (different from content versioning)
