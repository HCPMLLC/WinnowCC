# PROMPT68_Interview_Prep_Coach.md

Read CLAUDE.md, ARCHITECTURE.md, and tasks/lessons.md before making changes.

## Purpose

Add an **Interview Prep Coach** feature that generates personalized interview preparation when a candidate moves a job match to the "Interviewing" status. Using the candidate's actual resume bullets, the matched/missing skills from scoring, and the job description, an LLM produces:

1. **Likely interview questions** (behavioral, technical, situational) tailored to the specific role
2. **STAR-format answer suggestions** grounded in the candidate's real experience bullets
3. **Company culture insights** synthesized from the job description and company context
4. **Gap mitigation strategies** for missing skills the interviewer may probe

This is a low-cost, high-retention feature. Competitors stop at matching; Winnow coaches candidates through to the offer.

---

## Triggers — When to Use This Prompt

- You are implementing the Interview Prep Coach feature
- A candidate's match `application_status` transitions to `"interviewing"`
- You are adding LLM-powered coaching to the match detail view

---

## What Already Exists (DO NOT recreate)

1. **Match model** (`services/api/app/models/match.py`):
   - `application_status` field with values: `"saved"`, `"applied"`, `"interviewing"`, `"rejected"`, `"offer"` (line 45)
   - `reasons` JSONB column containing `matched_skills`, `missing_skills`, `title_alignment`, `location_fit`, `salary_fit`, `evidence_refs` (line 27)
   - `match_score`, `interview_readiness_score`, `offer_probability`, `resume_score`, `interview_probability` fields

2. **Matching service** (`services/api/app/services/matching.py`):
   - `_evidence_refs()` function already extracts resume bullets mentioning matched skills (line 496)
   - `generate_ips_coaching()` provides rule-based coaching tips (no LLM) — the new feature complements this with LLM-generated, interview-specific prep

3. **Profile data** (`candidate_profiles.profile_json`):
   - `skills[]` — candidate's skill list
   - `experience[].title`, `experience[].company`, `experience[].bullets[]` — work history
   - `education[]`, `certifications[]`

4. **Job data** (`jobs` table):
   - `title`, `company`, `description_text`, `location`, `salary_min`, `salary_max`

5. **LLM infrastructure** (`services/api/app/services/`):
   - Anthropic singleton client pattern used in `sieve_chat.py`, `career_intelligence.py`, `cover_letter_generator.py`, `llm_parser.py`
   - `_extract_json()` helper for parsing structured LLM responses
   - `messages.create()` with system/user message pattern

6. **Billing** (`services/api/app/services/billing.py`):
   - `CANDIDATE_PLAN_LIMITS` dict with per-tier limits (lines 62-105)
   - `check_daily_limit()` / `increment_daily_counter()` for daily usage tracking
   - `check_feature_access()` for boolean feature gates

7. **Matches router** (`services/api/app/routers/matches.py`):
   - PATCH endpoint for updating `application_status`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     INTERVIEW PREP COACH FLOW                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  CANDIDATE (Frontend)              BACKEND                             │
│  ────────────────────              ───────                             │
│                                                                        │
│  1. Changes match status   ──────► PATCH /api/matches/{id}/status      │
│     to "Interviewing"              application_status = "interviewing" │
│                                           │                            │
│                                           ▼                            │
│                                    Check billing tier:                  │
│                                    - Free: ✗ (no access)               │
│                                    - Starter: 3/month                  │
│                                    - Pro: unlimited                    │
│                                           │                            │
│                                           ▼                            │
│                                    Enqueue RQ job:                      │
│                                    generate_interview_prep              │
│                                           │                            │
│  WORKER                                   │                            │
│  ──────                                   │                            │
│                                           ▼                            │
│                                    Load match.reasons                   │
│                                    Load profile_json                    │
│                                    Load job description                 │
│                                           │                            │
│                                           ▼                            │
│                                    LLM call (Claude):                   │
│                                    - System: interview coach persona    │
│                                    - User: job + profile + match data   │
│                                           │                            │
│                                           ▼                            │
│                                    Parse JSON response                  │
│                                    Store in interview_prep_results      │
│                                           │                            │
│  2. Poll or view prep      ◄──────  GET /api/matches/{id}/prep         │
│     on match detail page                                               │
│                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Add Billing Limits

**File:** `services/api/app/services/billing.py`

Add `interview_prep_per_month` to each candidate tier in `CANDIDATE_PLAN_LIMITS`:

```python
# In "free" dict:
"interview_prep_per_month": 0,        # No access

# In "starter" dict:
"interview_prep_per_month": 3,        # 3 preps/month

# In "pro" dict:
"interview_prep_per_month": 9999,     # Unlimited
```

---

### Step 2: Create Database Model

**File:** `services/api/app/models/interview_prep.py` (new file)

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class InterviewPrep(Base):
    __tablename__ = "interview_prep_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status values: pending, processing, completed, failed

    # LLM-generated content (stored as structured JSON)
    prep_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structure of prep_content:
    # {
    #   "likely_questions": [
    #     {"category": "behavioral"|"technical"|"situational",
    #      "question": "...",
    #      "why_likely": "...",
    #      "star_suggestion": {"situation": "...", "task": "...", "action": "...", "result": "..."},
    #      "source_bullet": "..." }
    #   ],
    #   "company_insights": {
    #     "culture_signals": ["..."],
    #     "values_to_emphasize": ["..."],
    #     "potential_concerns": ["..."]
    #   },
    #   "gap_strategies": [
    #     {"missing_skill": "...", "mitigation": "...", "transferable_experience": "..."}
    #   ],
    #   "closing_questions": ["..."]  -- smart questions candidate can ask
    # }

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Register the model in `services/api/app/models/__init__.py`.

---

### Step 3: Create Alembic Migration

```bash
cd services/api
alembic revision --autogenerate -m "add interview_prep_results table"
alembic upgrade head
```

---

### Step 4: Create Interview Prep Service

**File:** `services/api/app/services/interview_prep.py` (new file)

**Core function: `generate_interview_prep(match_id, user_id)`**

1. Load the match (with `reasons` JSONB), the job, and the candidate's `profile_json`
2. Build the LLM prompt with:
   - **System message**: "You are an expert interview coach. Generate personalized interview prep based on the candidate's actual experience and the specific job requirements."
   - **User message** containing:
     - Job title, company, description (truncated to ~3000 chars)
     - Matched skills from `match.reasons["matched_skills"]`
     - Missing skills from `match.reasons["missing_skills"]`
     - Evidence refs (resume bullets) from `match.reasons["evidence_refs"]`
     - Full experience section from `profile_json["experience"]`
     - Match score and interview readiness score for calibration
3. Call `anthropic_client.messages.create()` with `model="claude-sonnet-4-20250514"` (fast, cheap)
4. Parse response with `_extract_json()` into the `prep_content` structure
5. Update the `InterviewPrep` row: set `status="completed"`, `prep_content=parsed`, `completed_at=now()`
6. On failure: set `status="failed"`, `error_message=str(e)`

**LLM prompt structure:**

```
Generate interview preparation for this candidate applying to this role.

## Job
Title: {job.title}
Company: {job.company}
Description: {job.description_text[:3000]}

## Candidate Strengths (matched skills)
{matched_skills}

## Gaps (missing skills)
{missing_skills}

## Candidate Experience Highlights
{evidence_refs + additional experience bullets}

## Instructions
Return JSON with:
1. "likely_questions": 8-12 questions across behavioral/technical/situational categories.
   For each, include a STAR-format answer suggestion using ONLY the candidate's actual experience bullets.
   Include "why_likely" explaining why this question is probable for this role.
   Include "source_bullet" with the resume bullet used.
2. "company_insights": culture signals, values to emphasize, potential concerns.
3. "gap_strategies": for each missing skill, suggest mitigation using transferable experience.
4. "closing_questions": 3-5 thoughtful questions the candidate can ask the interviewer.
```

**Cost estimate:** ~2K input tokens + ~3K output tokens per prep ≈ $0.02 per generation with Sonnet.

---

### Step 5: Wire Into Match Status Update

**File:** `services/api/app/routers/matches.py`

In the PATCH endpoint that updates `application_status`:

1. When `new_status == "interviewing"` and the old status was not already `"interviewing"`:
   - Check billing: `check_daily_limit(candidate, "interview_prep_per_month")` (monthly counter, not daily — use the same `DailyUsageCounter` pattern but with a monthly key like `interview_prep:{year}-{month}`)
   - If allowed, increment the counter
   - Create an `InterviewPrep` row with `status="pending"`
   - Enqueue RQ job: `queue.enqueue(generate_interview_prep, match_id=match.id, user_id=user.id)`
2. Return the updated match with `interview_prep_status: "pending"` in the response

---

### Step 6: Add GET Endpoint for Prep Results

**File:** `services/api/app/routers/matches.py` (or new `interview_prep.py` router)

**`GET /api/matches/{match_id}/interview-prep`**

1. Auth: `get_current_user` dependency
2. Load `InterviewPrep` by `match_id` and `user_id`
3. If not found: 404
4. If `status == "pending"` or `"processing"`: return `{"status": "pending"}` (frontend shows loading)
5. If `status == "completed"`: return full `prep_content` JSON
6. If `status == "failed"`: return error with retry option

**Response schema:**

```json
{
  "status": "completed",
  "prep": {
    "likely_questions": [
      {
        "category": "behavioral",
        "question": "Tell me about a time you led a cross-functional project.",
        "why_likely": "Job description emphasizes cross-team collaboration and the role is senior-level.",
        "star_suggestion": {
          "situation": "At Acme Corp, our product launch required coordination between engineering, marketing, and sales teams.",
          "task": "I was asked to lead the cross-functional initiative to ship v2.0 on time.",
          "action": "I set up weekly syncs, created a shared Notion tracker, and resolved a critical blocker between eng and design.",
          "result": "We launched 2 weeks ahead of schedule with 95% feature completeness."
        },
        "source_bullet": "Led cross-functional team of 12 to deliver v2.0 product launch 2 weeks ahead of schedule"
      }
    ],
    "company_insights": {
      "culture_signals": ["Remote-first", "Fast-paced startup", "Values ownership"],
      "values_to_emphasize": ["Self-direction", "Bias for action", "Data-driven decisions"],
      "potential_concerns": ["Role requires on-call rotation", "Rapid scaling phase"]
    },
    "gap_strategies": [
      {
        "missing_skill": "Kubernetes",
        "mitigation": "Emphasize your Docker and AWS ECS experience as transferable container orchestration knowledge.",
        "transferable_experience": "Managed containerized microservices on AWS ECS for 2 years"
      }
    ],
    "closing_questions": [
      "What does the first 90 days look like for someone in this role?",
      "How does the team measure success for this position?",
      "What's the biggest technical challenge the team is currently tackling?"
    ]
  },
  "generated_at": "2026-03-02T14:30:00Z"
}
```

---

### Step 7: Frontend — Interview Prep Tab on Match Detail

**File:** `apps/web/app/components/matches/InterviewPrepPanel.tsx` (new file)

Create a panel/tab that displays on the match detail view when `application_status === "interviewing"`:

1. **Loading state**: Spinner with "Preparing your personalized interview coaching..." while `status === "pending"`
2. **Likely Questions section**: Accordion/expandable cards grouped by category (Behavioral, Technical, Situational)
   - Each card shows the question, "Why this is likely" hint, and expandable STAR answer
   - STAR answer formatted with S/T/A/R labels and the source resume bullet highlighted
3. **Company Insights section**: Cards showing culture signals, values to emphasize, potential red flags
4. **Gap Strategies section**: For each missing skill, show the skill, mitigation strategy, and transferable experience
5. **Questions to Ask section**: Bulleted list of smart closing questions
6. **Retry button** if `status === "failed"`

**File:** `apps/web/app/matches/[id]/page.tsx` (or equivalent match detail page)

Add an "Interview Prep" tab that appears when the match status is `"interviewing"` or later. The tab:
- Calls `GET /api/matches/{id}/interview-prep`
- Renders `<InterviewPrepPanel>` with the response data
- Shows an upgrade CTA for free-tier users

---

### Step 8: Add Monthly Usage Counter Logic

**File:** `services/api/app/services/billing.py`

The existing `check_daily_limit()` and `increment_daily_counter()` use date-based keys (e.g., `sieve:2026-03-02`). For monthly limits, use a month-based key pattern:

```python
# Key format for monthly counters: "interview_prep:2026-03"
# Reuse the same DailyUsageCounter table — the "day" column stores the first of the month
```

Add helper functions:
- `check_monthly_limit(candidate_id, feature, tier)` — similar to `check_daily_limit()` but groups by month
- `increment_monthly_counter(candidate_id, feature)` — similar to `increment_daily_counter()` but monthly

Or alternatively, just use the existing daily counter with a monthly date key — the simplest approach.

---

### Step 9: Register Model and Router

1. **Model registration**: Add `from app.models.interview_prep import InterviewPrep` to `services/api/app/models/__init__.py`
2. **Router registration**: If using a new router file, add to `services/api/app/main.py`:
   ```python
   from app.routers import interview_prep
   app.include_router(interview_prep.router, prefix="/api")
   ```
3. **Worker job**: Register `generate_interview_prep` in the worker's job map so RQ can dispatch it

---

### Step 10: Add Cascade Delete Support

**File:** `services/api/app/services/cascade_delete.py`

Add `interview_prep_results` to the cascade delete sequence so account deletion cleans up prep data:

```python
# In the deletion order list, add before matches:
"interview_prep_results",
```

---

## Tier Gating Summary

| Feature                    | Free | Starter ($9/mo) | Pro ($29/mo) |
|----------------------------|------|------------------|--------------|
| Interview Prep generation  | ✗    | 3/month          | Unlimited    |
| STAR answer suggestions    | ✗    | ✓                | ✓            |
| Company culture insights   | ✗    | ✓                | ✓            |
| Gap mitigation strategies  | ✗    | ✗                | ✓            |
| Closing questions to ask   | ✗    | ✓                | ✓            |

**Note:** Starter users get the core prep but not gap strategies (those require more nuanced LLM reasoning and are a Pro differentiator). Implement this by filtering `gap_strategies` out of the response for starter-tier users at the API layer.

---

## Testing Checklist

- [ ] Unit test: `generate_interview_prep()` with mocked Anthropic client returns valid JSON structure
- [ ] Unit test: billing enforcement — free tier blocked, starter limited to 3/month, pro unlimited
- [ ] Unit test: prep is only triggered on transition TO "interviewing" (not re-triggered if already interviewing)
- [ ] Unit test: cascade delete removes `interview_prep_results` rows
- [ ] Integration test: PATCH match status → RQ job enqueued → prep row created with "pending"
- [ ] Integration test: GET endpoint returns correct response for each status (pending, completed, failed)
- [ ] Frontend test: InterviewPrepPanel renders all sections correctly
- [ ] Frontend test: loading/error/empty states display properly
- [ ] Manual test: end-to-end flow — upload resume, get match, move to interviewing, view prep

---

## Cost & Performance

- **LLM cost**: ~$0.02 per prep (Sonnet, ~2K in + ~3K out tokens)
- **Latency**: 5-15 seconds (async via RQ worker, user sees loading state)
- **Storage**: ~5KB per prep (JSONB in Postgres)
- **Monthly cost at scale**: 1,000 preps/month ≈ $20/month in LLM costs
