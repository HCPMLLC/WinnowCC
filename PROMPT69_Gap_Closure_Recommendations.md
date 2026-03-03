# PROMPT69_Gap_Closure_Recommendations.md

Read CLAUDE.md, ARCHITECTURE.md, and tasks/lessons.md before making changes.

## Purpose

Add a **Gap Closure Recommendations** feature that turns skills gaps identified in match scoring into actionable learning plans. For each missing skill in a match, an LLM suggests specific free/low-cost courses, certifications, or portfolio projects the candidate can complete to close the gap — with estimated time investment and difficulty level.

**Why it matters:**

- Turns rejection into action ("You're missing X, here's how to get it in 2 weeks")
- Increases perceived value of low-match jobs (a 60% match becomes a growth opportunity)
- Builds long-term loyalty (Winnow helped me grow, not just search)
- Differentiates from every competitor that stops at "you don't match"

**Cost:** ~$0.005-0.01 per recommendation set (~500 input + ~800 output tokens with Haiku). Can batch with match computation to amortize latency.

---

## Triggers — When to Use This Prompt

- You are implementing the Gap Closure Recommendations feature
- You are extending match detail responses with learning recommendations
- You are adding skill gap actionability to the matching pipeline

---

## What Already Exists (DO NOT recreate)

1. **Match model** (`services/api/app/models/match.py`):
   - `reasons` JSONB column containing `matched_skills`, `missing_skills`, `title_alignment`, `location_fit`, `salary_fit`, `evidence_refs`
   - `match_score`, `interview_readiness_score`, `offer_probability` fields

2. **Matching service** (`services/api/app/services/matching.py`):
   - `missing_skills` computed as top 7 job keywords not in candidate's skill set (line ~209-211)
   - `matched_skills` computed as skills present in both candidate and job (line ~208)
   - `_evidence_refs()` extracts resume bullets mentioning matched skills

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
   - `GET /api/matches/{match_id}` — single match detail (already returns coaching_tips for Pro)
   - `GET /api/matches` — list matches
   - `POST /api/matches/refresh` — triggers match recomputation via RQ

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   GAP CLOSURE RECOMMENDATIONS FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER A: On-Demand (match detail view)                                   │
│  ─────────────────────────────────────────                                  │
│                                                                             │
│  1. Candidate views match     ──────► GET /api/matches/{id}                 │
│     detail page                       │                                     │
│                                       ▼                                     │
│                                 Check: gap_recommendations exist?            │
│                                 No ──► Check billing tier:                   │
│                                        - Free: 3 per day                    │
│                                        - Starter: 15 per day               │
│                                        - Pro: unlimited                     │
│                                        │                                    │
│                                        ▼                                    │
│                                 Enqueue RQ job:                              │
│                                 generate_gap_recommendations                 │
│                                        │                                    │
│  WORKER                                │                                    │
│  ──────                                │                                    │
│                                        ▼                                    │
│                                 Load match.reasons (missing_skills)          │
│                                 Load profile_json (existing skills)          │
│                                 Load job details (title, level cues)         │
│                                        │                                    │
│                                        ▼                                    │
│                                 LLM call (Claude Haiku):                    │
│                                 - System: career advisor persona             │
│                                 - User: gaps + skills + job context          │
│                                        │                                    │
│                                        ▼                                    │
│                                 Parse JSON response                          │
│                                 Store in gap_recommendations table            │
│                                        │                                    │
│  2. Frontend polls / re-fetch  ◄────── GET /api/matches/{id}/gap-recs       │
│     match detail shows recs                                                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TRIGGER B: Batch (during match refresh) — OPTIONAL OPTIMIZATION            │
│  ──────────────────────────────────────────────────────────────              │
│                                                                             │
│  After compute_matches() completes, enqueue a batch job that generates      │
│  gap recommendations for the top N matches (e.g., top 10). This pre-warms   │
│  recommendations so candidates see them instantly on first view.             │
│  Only run for Starter+ tiers. Deferred to v2 if desired.                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Add Billing Limits

**File:** `services/api/app/services/billing.py`

Add `gap_recommendations_per_day` to each candidate tier in `CANDIDATE_PLAN_LIMITS`:

```python
# In "free" dict:
"gap_recommendations_per_day": 3,        # Light access to demonstrate value

# In "starter" dict:
"gap_recommendations_per_day": 15,       # Generous for active job seekers

# In "pro" dict:
"gap_recommendations_per_day": 9999,     # Unlimited
```

**Rationale:** Unlike interview prep (expensive, infrequent), gap recs are cheap (~$0.005-0.01) and drive engagement. Give free users a taste to convert them.

---

### Step 2: Create Database Model

**File:** `services/api/app/models/gap_recommendation.py` (new file)

```python
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class GapRecommendation(Base):
    __tablename__ = "gap_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status values: pending, processing, completed, failed

    # LLM-generated content (stored as structured JSON)
    recommendations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Structure of recommendations:
    # {
    #   "gaps": [
    #     {
    #       "skill": "Kubernetes",
    #       "priority": "high" | "medium" | "low",
    #       "why_needed": "Required for the container orchestration responsibilities in this role",
    #       "resources": [
    #         {
    #           "type": "course" | "certification" | "project" | "tutorial",
    #           "name": "Kubernetes for Developers (LFS258)",
    #           "provider": "Linux Foundation / edX",
    #           "url_hint": "edx.org or linuxfoundation.org",
    #           "cost": "free" | "$49" | ...,
    #           "time_estimate": "2 weeks (10-15 hours)",
    #           "difficulty": "beginner" | "intermediate" | "advanced",
    #           "why_recommended": "Covers core K8s concepts and your Docker experience transfers directly"
    #         }
    #       ],
    #       "transferable_skills": ["Docker", "AWS ECS"],
    #       "quick_win": "Add a personal project deploying your existing app to a K8s cluster on Minikube — 1 weekend project"
    #     }
    #   ],
    #   "overall_plan": {
    #     "estimated_total_time": "3-4 weeks part-time",
    #     "priority_order": ["Kubernetes", "Terraform", "GraphQL"],
    #     "encouragement": "You already have 80% of what this role needs. Closing these gaps would make you a strong candidate."
    #   }
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
alembic revision --autogenerate -m "add gap_recommendations table"
alembic upgrade head
```

---

### Step 4: Create Gap Recommendations Service

**File:** `services/api/app/services/gap_recommendations.py` (new file)

**Core function: `generate_gap_recommendations(match_id, user_id)`**

1. Load the match (with `reasons` JSONB), the job, and the candidate's `profile_json`
2. Extract context:
   - `missing_skills` from `match.reasons["missing_skills"]`
   - `matched_skills` from `match.reasons["matched_skills"]`
   - Candidate's existing `skills[]`, `experience[]`, `certifications[]`, `education[]`
   - Job title, company, description (for level/seniority cues)
3. Build the LLM prompt (see below)
4. Call `anthropic_client.messages.create()` with `model="claude-haiku-4-5-20251001"` (fast, cheapest)
5. Parse response with `_extract_json()` into the `recommendations` structure
6. Update the `GapRecommendation` row: set `status="completed"`, `recommendations=parsed`, `completed_at=now()`
7. On failure: set `status="failed"`, `error_message=str(e)`

**LLM prompt structure:**

```
System: You are a career development advisor. Given a candidate's skills gaps for a specific
job, recommend specific, actionable resources to close each gap. Focus on free and low-cost
options. Be practical and realistic about time estimates. Only recommend well-known, reputable
resources. Return valid JSON only.

User:
## Job Context
Title: {job.title}
Company: {job.company}
Description excerpt: {job.description_text[:1500]}

## Candidate's Existing Skills
{skills list}

## Candidate's Experience Level
{inferred from experience titles and years}

## Skills Gaps to Close
{missing_skills list}

## Instructions
For each missing skill, provide:
1. Priority level (high/medium/low) based on how prominently it appears in the job description
2. A brief explanation of why the skill is needed for this specific role
3. 2-3 specific learning resources:
   - Prefer free resources (YouTube channels, official docs, freeCodeCamp, Coursera audit, edX audit)
   - Include one certification option if relevant
   - Include one portfolio project idea they could build
   - Estimate realistic time to reach "job-ready" level
4. Which of the candidate's existing skills transfer to learning this faster
5. A "quick win" — the fastest thing they could do this weekend to start

Also provide an overall learning plan with:
- Recommended priority order for closing gaps
- Total estimated time investment
- An encouraging note about what they already bring to the table

Return JSON matching this structure:
{
  "gaps": [
    {
      "skill": "...",
      "priority": "high|medium|low",
      "why_needed": "...",
      "resources": [
        {
          "type": "course|certification|project|tutorial",
          "name": "...",
          "provider": "...",
          "url_hint": "platform or search term to find it",
          "cost": "free|$XX",
          "time_estimate": "X weeks (Y hours)",
          "difficulty": "beginner|intermediate|advanced",
          "why_recommended": "..."
        }
      ],
      "transferable_skills": ["..."],
      "quick_win": "..."
    }
  ],
  "overall_plan": {
    "estimated_total_time": "...",
    "priority_order": ["..."],
    "encouragement": "..."
  }
}
```

**Why Haiku instead of Sonnet:** Gap recommendations are structured knowledge retrieval (courses, certs, projects) — not creative reasoning. Haiku handles this well at 10-20x lower cost than Sonnet. If quality is insufficient, upgrade to Sonnet later.

**Cost estimate:** ~500 input tokens + ~800 output tokens per request ≈ $0.005-0.01 per generation with Haiku.

---

### Step 5: Add GET Endpoint for Gap Recommendations

**File:** `services/api/app/routers/matches.py`

**`GET /api/matches/{match_id}/gap-recs`**

1. Auth: `get_current_user` dependency
2. Load `GapRecommendation` by `match_id` and `user_id`
3. If not found: check billing limit, create `GapRecommendation` row with `status="pending"`, enqueue RQ job, return `{"status": "pending"}`
4. If `status == "pending"` or `"processing"`: return `{"status": "pending"}` (frontend shows loading)
5. If `status == "completed"`: return full `recommendations` JSON
6. If `status == "failed"`: return error with retry option

**Why lazy generation (on-demand) instead of batch:** Generating recs for every match wastes LLM spend on matches the candidate never views. Lazy generation means we only pay for matches the candidate actually cares about. Pre-warming (Trigger B in architecture diagram) can be added later as an optimization.

**Response schema:**

```json
{
  "status": "completed",
  "recommendations": {
    "gaps": [
      {
        "skill": "Kubernetes",
        "priority": "high",
        "why_needed": "The role involves managing container orchestration for 50+ microservices. K8s is listed as a core requirement.",
        "resources": [
          {
            "type": "course",
            "name": "Kubernetes for the Absolute Beginners",
            "provider": "KodeKloud / Udemy",
            "url_hint": "kodekloud.com or udemy.com search 'kubernetes beginners'",
            "cost": "free (KodeKloud playground) / $14 (Udemy sale)",
            "time_estimate": "1 week (8-10 hours)",
            "difficulty": "beginner",
            "why_recommended": "Hands-on labs match your learn-by-doing style from your Docker experience"
          },
          {
            "type": "certification",
            "name": "Certified Kubernetes Application Developer (CKAD)",
            "provider": "Linux Foundation / CNCF",
            "url_hint": "training.linuxfoundation.org",
            "cost": "$395",
            "time_estimate": "3-4 weeks (20-30 hours)",
            "difficulty": "intermediate",
            "why_recommended": "Industry-recognized cert that would make your resume stand out for this role"
          },
          {
            "type": "project",
            "name": "Deploy your portfolio app to a K8s cluster",
            "provider": "Self-directed",
            "url_hint": "Use Minikube locally or free GKE tier",
            "cost": "free",
            "time_estimate": "1 weekend (6-8 hours)",
            "difficulty": "intermediate",
            "why_recommended": "Gives you a real talking point in interviews and demonstrates hands-on K8s experience"
          }
        ],
        "transferable_skills": ["Docker", "AWS ECS", "CI/CD pipelines"],
        "quick_win": "Install Minikube, deploy a simple nginx container, and practice kubectl commands — you can do this Saturday morning."
      },
      {
        "skill": "Terraform",
        "priority": "medium",
        "why_needed": "Job mentions 'infrastructure as code' — Terraform is the most likely tool given the AWS stack.",
        "resources": [
          {
            "type": "tutorial",
            "name": "HashiCorp Learn — Terraform AWS Track",
            "provider": "HashiCorp",
            "url_hint": "developer.hashicorp.com/terraform/tutorials",
            "cost": "free",
            "time_estimate": "1 week (6-8 hours)",
            "difficulty": "beginner",
            "why_recommended": "Official tutorials with your existing AWS knowledge as a foundation"
          },
          {
            "type": "project",
            "name": "Terraform your existing AWS infrastructure",
            "provider": "Self-directed",
            "url_hint": "Import existing resources with terraform import",
            "cost": "free",
            "time_estimate": "1 weekend (4-6 hours)",
            "difficulty": "intermediate",
            "why_recommended": "Use your real AWS setup as a learning project — practical and portfolio-worthy"
          }
        ],
        "transferable_skills": ["AWS CloudFormation", "YAML/JSON configs", "AWS CLI"],
        "quick_win": "Complete the first 3 HashiCorp tutorials to provision an EC2 instance with Terraform — takes about 2 hours."
      }
    ],
    "overall_plan": {
      "estimated_total_time": "3-4 weeks part-time",
      "priority_order": ["Kubernetes", "Terraform"],
      "encouragement": "You already match 75% of this role's requirements. Your strong Docker and AWS foundation means Kubernetes will click quickly — most of the concepts transfer directly. Closing these 2 gaps would make you a very competitive candidate."
    }
  },
  "generated_at": "2026-03-02T14:30:00Z"
}
```

---

### Step 6: Add Retry Endpoint

**File:** `services/api/app/routers/matches.py`

**`POST /api/matches/{match_id}/gap-recs/retry`**

1. Auth: `get_current_user` dependency
2. Load `GapRecommendation` by `match_id` and `user_id`
3. If not found or `status != "failed"`: 404 or 400
4. Reset `status="pending"`, clear `error_message`
5. Re-enqueue RQ job
6. Does NOT re-check billing limit (original generation already counted)

---

### Step 7: Wire Into Match Detail Response

**File:** `services/api/app/routers/matches.py`

In the `GET /api/matches/{match_id}` endpoint, add a `gap_recs_status` field to the response indicating whether gap recommendations are available:

```python
# After loading the match, check for existing gap recommendations
gap_rec = session.query(GapRecommendation).filter_by(
    match_id=match.id, user_id=user.id
).first()

# Add to response
response["gap_recs_status"] = gap_rec.status if gap_rec else "available"
# "available" = not yet generated, frontend can trigger via GET /gap-recs
# "pending" = generating
# "completed" = ready to view
# "failed" = error, can retry
```

**File:** `services/api/app/schemas/matches.py`

Add to `MatchResponse`:

```python
gap_recs_status: str | None = None  # "available", "pending", "completed", "failed"
```

---

### Step 8: Frontend — Gap Recommendations Card on Match Detail

**File:** `apps/web/app/components/matches/GapRecommendationsCard.tsx` (new file)

Create a card/section that displays on the match detail view when `missing_skills` exist:

1. **Available state** (gap_recs_status = "available"):
   - CTA button: "Get personalized learning plan for this role"
   - Subtitle: "We'll suggest free courses and projects to close your skills gaps"
   - Click triggers `GET /api/matches/{id}/gap-recs` which auto-generates

2. **Loading state** (gap_recs_status = "pending"):
   - Spinner with "Creating your personalized learning plan..."
   - Poll every 3 seconds until completed

3. **Completed state** (gap_recs_status = "completed"):
   - **Overall plan banner** at top: encouragement message, total time estimate, priority order
   - **Gap cards**: One expandable card per skill gap, ordered by priority
     - Priority badge (high = red, medium = amber, low = green)
     - "Why you need this" explanation
     - Transferable skills chips: "You already know: Docker, AWS ECS"
     - Resource list with type icon, name, provider, cost badge, time estimate
     - "Quick win" callout box: weekend action item
   - **Upgrade CTA** for free tier: "Upgrade to Starter for more learning plans"

4. **Failed state** (gap_recs_status = "failed"):
   - Error message with retry button

**File:** `apps/web/app/matches/[id]/page.tsx` (or equivalent match detail page)

Add the `<GapRecommendationsCard>` below the existing match detail content. Show it when the match has `missing_skills` in `reasons` (which is virtually every match).

---

### Step 9: Register Model and Router

1. **Model registration**: Add `from app.models.gap_recommendation import GapRecommendation` to `services/api/app/models/__init__.py`
2. **Router endpoints**: Add the new endpoints to the existing `matches.py` router (no new router file needed — keeps gap recs colocated with match endpoints)
3. **Worker job**: Register `generate_gap_recommendations` in the worker's job map so RQ can dispatch it

---

### Step 10: Add Cascade Delete Support

**File:** `services/api/app/services/cascade_delete.py`

Add `gap_recommendations` to the cascade delete sequence so account deletion cleans up recommendation data:

```python
# In the deletion order list, add before matches:
"gap_recommendations",
```

---

## Tier Gating Summary

| Feature                      | Free           | Starter ($9/mo) | Pro ($29/mo) |
|------------------------------|----------------|------------------|--------------|
| Gap recommendations/day      | 3              | 15               | Unlimited    |
| Resources per gap            | 2              | 3                | 3            |
| Quick win suggestions        | Yes            | Yes              | Yes          |
| Overall learning plan        | No             | Yes              | Yes          |
| Priority ordering            | No             | Yes              | Yes          |

**Note:** Free-tier users see a trimmed response: only 2 resources per gap, no overall plan or priority ordering. This gives them a taste of the value while incentivizing upgrade. Implement this by filtering the response at the API layer based on tier.

---

## Testing Checklist

- [ ] Unit test: `generate_gap_recommendations()` with mocked Anthropic client returns valid JSON structure
- [ ] Unit test: billing enforcement — free tier limited to 3/day, starter to 15/day, pro unlimited
- [ ] Unit test: on-demand generation — first GET creates pending row and enqueues job
- [ ] Unit test: duplicate prevention — second GET for same match returns existing row (no re-generation)
- [ ] Unit test: cascade delete removes `gap_recommendations` rows
- [ ] Unit test: free-tier response filtering (2 resources, no overall plan)
- [ ] Integration test: GET gap-recs → RQ job enqueued → row created with "pending" → completed after worker runs
- [ ] Integration test: retry endpoint resets failed row and re-enqueues
- [ ] Frontend test: GapRecommendationsCard renders all states (available, loading, completed, failed)
- [ ] Frontend test: priority badges, resource cards, quick win callout display correctly
- [ ] Frontend test: upgrade CTA shows for free tier only
- [ ] Manual test: end-to-end flow — upload resume, get match with gaps, view match detail, trigger gap recs, view learning plan

---

## Cost & Performance

- **LLM cost**: ~$0.005-0.01 per recommendation set (Haiku, ~500 in + ~800 out tokens)
- **Latency**: 2-5 seconds (async via RQ worker, user sees loading state)
- **Storage**: ~3KB per recommendation set (JSONB in Postgres)
- **Monthly cost at scale**: 10,000 recs/month ≈ $50-100/month in LLM costs
- **Comparison**: 10-20x cheaper than interview prep, can afford to be generous with free tier

---

## Future Enhancements (Out of Scope for v1)

1. **Progress tracking**: Let candidates mark resources as "completed" and track gap closure over time
2. **Re-recommendation on profile update**: When candidate adds a new skill/cert, regenerate recs for saved matches
3. **Batch pre-warming**: After match refresh, pre-generate recs for top 5-10 matches (Trigger B)
4. **Resource quality feedback**: Thumbs up/down on individual resources to improve LLM prompts over time
5. **Integration with career intelligence**: Link gap recs to salary impact ("closing this K8s gap could increase offers by ~$15K based on market data")
