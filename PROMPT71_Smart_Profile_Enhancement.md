# PROMPT71_Smart_Profile_Enhancement.md

Read CLAUDE.md, ARCHITECTURE.md, and tasks/lessons.md before making changes.

## Purpose

Add **Smart Profile Enhancement Suggestions** — an LLM-powered career-coach analysis that reviews a candidate's parsed profile and generates specific, actionable improvement suggestions. Unlike the existing `profile_scoring.py` completeness checker (which flags structural gaps like "phone number missing"), this feature analyzes *content quality* ("your PM experience mentions Agile but lacks specific metrics").

**Why it matters:**

- Profile quality directly impacts match scores — better profiles get better matches
- Acts as an embedded career coach that helps candidates self-improve
- Increases platform engagement (candidates return to refine their profiles)
- Differentiates from competitors that only show a completeness percentage

**Cost:** ~$0.02-0.04 per profile analysis (Sonnet). One-time cost per profile version. All tiers get this.

---

## Triggers — When to Use This Prompt

- You are implementing the Smart Profile Enhancement feature
- You are modifying the enhancement suggestions UI or API
- You are extending the post-parse pipeline with new analysis

---

## What Already Exists (DO NOT recreate)

1. **Profile completeness scoring** (`services/api/app/services/profile_scoring.py`):
   - `compute_profile_completeness(profile_json)` — structural gap checker (0-100 score)
   - Returns deficiencies and recommendations
   - Pure function, no LLM calls

2. **Career Intelligence** (`services/api/app/services/career_intelligence.py`):
   - Singleton Anthropic client pattern, `_extract_json()`, `_get_client()`
   - Model: `claude-sonnet-4-5-20250929`

3. **Resume parse job** (`services/api/app/services/resume_parse_job.py`):
   - Post-parse pipeline: embed → refresh → ingest → match
   - Enhancement suggestions enqueue added at end of pipeline

4. **Profile router** (`services/api/app/routers/profile.py`):
   - `GET /api/profile` — latest profile version
   - `PUT /api/profile` — save with new version
   - `GET /api/profile/completeness` — structural scoring

5. **Queue system** (`services/api/app/services/queue.py`):
   - `get_queue("low")` — low-priority queue for non-critical jobs

---

## Implementation Summary

### Backend

**New file: `services/api/app/services/profile_enhancement.py`**
- Singleton Anthropic client (same pattern as `career_intelligence.py`)
- `generate_enhancement_suggestions(user_id, version)` — RQ worker job
- Loads profile, builds context prompt, calls Claude Sonnet (temp 0.3)
- Writes results to `profile_json.enhancement_suggestions` on the same row
- Handles empty profiles (skip LLM), LLM failures (status: "failed")
- JSON schema in `enhancement_suggestions`:
  ```json
  {
    "status": "generating|completed|failed",
    "suggestions": [{ "category", "section_ref", "priority", "current_issue", "suggestion", "example", "impact" }],
    "overall_assessment": { "strengths", "biggest_opportunity", "estimated_improvement" },
    "generated_at": "ISO 8601"
  }
  ```

**Modified: `services/api/app/services/resume_parse_job.py`**
- After existing post-parse jobs, enqueues `generate_enhancement_suggestions` on `"low"` queue

**Modified: `services/api/app/routers/profile.py`**
- `GET /api/profile/enhancement-suggestions` — returns current suggestions
- `POST /api/profile/enhancement-suggestions/regenerate` — triggers re-generation
- `PUT /api/profile` — clears stale `enhancement_suggestions` on manual save

### Frontend

**New file: `apps/web/app/components/EnhancementSuggestions.tsx`**
- States: generating (spinner), completed (cards), failed (retry), not_generated (hidden)
- Overall assessment banner (strengths + biggest opportunity)
- Expandable suggestion cards with priority badges (high=red, medium=amber, low=blue)
- Each card: suggestion, section reference, current issue, example, impact

**Modified: `apps/web/app/profile/page.tsx`**
- Fetches enhancement suggestions on mount
- Polls every 3s when status is "generating"
- Renders `<EnhancementSuggestions>` between recommendations and save button
- Clears suggestions on manual save, triggers polling after parse

### No Schema Changes

- Enhancement suggestions live inside the existing `profile_json` JSONB column
- No new database table, no Alembic migration
- Suggestions version naturally with the profile

---

## Key Files

| File | Action |
|------|--------|
| `services/api/app/services/profile_enhancement.py` | **New** — core service |
| `services/api/app/services/resume_parse_job.py` | **Modified** — enqueue enhancement job |
| `services/api/app/routers/profile.py` | **Modified** — 2 new endpoints + clear on save |
| `apps/web/app/components/EnhancementSuggestions.tsx` | **New** — frontend component |
| `apps/web/app/profile/page.tsx` | **Modified** — integrate component |
| `services/api/tests/test_profile_enhancement.py` | **New** — tests |

---

## Verification

1. Start infra + API + worker
2. Upload a resume with work experience
3. Verify `profile_json.enhancement_suggestions` transitions: `generating` -> `completed`
4. Verify `GET /api/profile/enhancement-suggestions` returns suggestions
5. Verify profile page shows "Improve Your Profile" section with expandable cards
6. Click Refresh, verify regeneration works
7. Edit profile manually and save, verify suggestions are cleared
8. Run `pytest services/api/tests/test_profile_enhancement.py`
