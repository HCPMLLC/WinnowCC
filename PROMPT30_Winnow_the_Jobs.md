# PROMPT30 — Winnow the Jobs: Match Score Threshold, Freshness Filter & Dashboard Alignment

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

The dashboard "Qualified Jobs" count currently reports ALL match records in the database (e.g., 251), but the Matches page shows far fewer because it applies recency filtering. This is confusing and misleading. Additionally, the matching pipeline creates match records for every job regardless of fit quality — a job with a match_score of 12 is not a "qualified" match.

This prompt introduces two filters at the **match creation** level to "winnow" the results:

1. **Minimum match score threshold: 50** — Don't store matches below 50. A score under 50 means the job is a poor fit and wastes the candidate's attention.
2. **Job freshness filter: 15 days** — Only match against jobs posted within the last 15 days. Stale postings clutter the list and lower the interview rate.

It also aligns the dashboard `qualified_jobs_count` to use the same filtered count, and updates Sieve's system prompt to explain the winnowing philosophy when users ask why their match count is low.

---

## Triggers — When to Use This Prompt

- Dashboard count doesn't match what the Matches page shows.
- Users see hundreds of matches but most are irrelevant or stale.
- Product wants to focus on quality over quantity in matches.
- Someone asks "why do I only have X matches?"

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Matching pipeline:** `services/api/app/services/matching.py` — computes `match_score` (0–100) using a 6-dimension weighted composite (skills 30%, experience 25%, certs 10%, location 15%, compensation 10%, title 10%). Optionally blended with semantic similarity (65% deterministic + 35% semantic).

2. **Match refresh endpoints:** `POST /api/matches/refresh` and `POST /api/match/run` in `services/api/app/routers/matches.py` — trigger the matching pipeline. Loops over active jobs and creates Match records.

3. **Match model:** `services/api/app/models/match.py` — stores `match_score`, `interview_probability`, `reasons` JSON, `application_status`, `created_at`, etc.

4. **Dashboard metrics endpoint:** `GET /api/dashboard/metrics` in `services/api/app/routers/dashboard.py` — returns `qualified_jobs_count` (currently counts ALL matches for the user, no filtering).

5. **Matches list endpoints:**
   - `GET /api/matches` — returns recent matches with recency filtering and deduplication.
   - `GET /api/matches/all` — returns ALL matches without filtering.

6. **Job model:** `services/api/app/models/job.py` — has `posted_at`, `ingested_at`, `first_seen_at`, `last_seen_at`, `is_active` fields.

7. **Sieve system prompt:** In `services/api/app/services/sieve.py` — the `SIEVE_SYSTEM_PROMPT` string that defines Sieve's personality, capabilities, and response guidelines. Context includes `matches.total_count` and `profile.completeness_score`.

8. **Staleness detection:** PROMPT10 specifies jobs older than 90 days with `last_seen_at > 30 days ago` are marked `is_active = false`.

---

## What to Build

### Part 1: Add Winnowing Constants

**File to edit in Cursor:**
```
services/api/app/services/matching.py
```

**Step 1.1 — Add constants near the top of the file,** after the existing imports. Look for where other constants are defined (like `W_DETERMINISTIC`, `W_SEMANTIC`, or dimension weights) and add these nearby:

```python
# ── Winnowing thresholds ────────────────────────────────────────
# Matches below this score are not stored — they waste candidate attention.
MIN_MATCH_SCORE = 50

# Only match against jobs posted within this many days.
# Stale postings lower interview rates and clutter the matches page.
JOB_FRESHNESS_DAYS = 15
```

---

### Part 2: Filter Jobs by Freshness BEFORE Scoring

The matching pipeline loops over active jobs and scores each one against the candidate's profile. We need to add a freshness filter so that only jobs posted within the last 15 days are even considered for matching.

**File to edit in Cursor:**
```
services/api/app/services/matching.py
```

**Step 2.1 — Find the function that queries jobs for matching.** It will look something like one of these patterns:

```python
# Pattern A: Direct query
jobs = db.query(Job).filter(Job.is_active == True).all()

# Pattern B: Query with existing filters
jobs = db.query(Job).filter(
    Job.is_active == True,
    Job.is_likely_fraudulent != True,
).all()
```

**Step 2.2 — Add the freshness filter to that query.** You need to add a filter for the job's posting date. Add this import at the top of the file if not already present:

```python
from datetime import datetime, timedelta, timezone
```

Then modify the job query to add:

```python
from datetime import datetime, timedelta, timezone

# Calculate the freshness cutoff
freshness_cutoff = datetime.now(timezone.utc) - timedelta(days=JOB_FRESHNESS_DAYS)

# Add to the job query — use posted_at if available, fall back to ingested_at
jobs = db.query(Job).filter(
    Job.is_active == True,
    # ... keep any existing filters (fraud, dedup, etc.) ...
    # Add freshness filter: use posted_at when available, otherwise ingested_at
    db.func.coalesce(Job.posted_at, Job.ingested_at, Job.created_at) >= freshness_cutoff,
).all()
```

**Important:** The freshness filter uses `COALESCE(posted_at, ingested_at, created_at)` because:
- `posted_at` is the actual date the job was posted (best signal, but not always available from all sources).
- `ingested_at` is when Winnow first saw the job (reliable fallback).
- `created_at` is the database record creation timestamp (last resort).

If the existing query uses a different ORM style (e.g., `select()` instead of `db.query()`), adapt accordingly — the key is adding the date filter.

---

### Part 3: Filter Matches by Minimum Score AFTER Scoring

After the match score is computed for a candidate-job pair, check if it meets the threshold before saving.

**File to edit in Cursor:**
```
services/api/app/services/matching.py
```

**Step 3.1 — Find where match records are created and stored.** Look for the place where a new Match object is created and added to the database. It will look something like:

```python
match = Match(
    user_id=user.id,
    job_id=job.id,
    match_score=computed_score,
    reasons=reasons_json,
    # ... other fields ...
)
db.add(match)
```

**Step 3.2 — Wrap it in a score check.** Add the threshold check BEFORE creating the Match record:

```python
# Winnow: only store matches that meet the minimum quality threshold
if computed_score >= MIN_MATCH_SCORE:
    match = Match(
        user_id=user.id,
        job_id=job.id,
        match_score=computed_score,
        reasons=reasons_json,
        # ... other fields ...
    )
    db.add(match)
# else: score too low — skip this job silently, don't waste the candidate's attention
```

**Step 3.3 — If the pipeline uses a loop,** the pattern should look like:

```python
matches_created = 0
matches_skipped = 0

for job in jobs:
    computed_score = compute_match_score(profile, job, db)
    
    # Winnow: skip low-quality matches
    if computed_score < MIN_MATCH_SCORE:
        matches_skipped += 1
        continue
    
    match = Match(
        user_id=user.id,
        job_id=job.id,
        match_score=computed_score,
        # ... other fields ...
    )
    db.add(match)
    matches_created += 1

# Log the winnowing result
logger.info(
    f"Match refresh for user {user.id}: "
    f"{matches_created} matches created, {matches_skipped} below threshold (MIN_MATCH_SCORE={MIN_MATCH_SCORE})"
)
```

---

### Part 4: Clean Up Old Stale Matches

Before this change takes effect going forward, there are existing match records in the database that would fail the new filters. Add a one-time cleanup step to the match refresh process.

**File to edit in Cursor:**
```
services/api/app/services/matching.py
```

**Step 4.1 — Find the match refresh function** (the function called by `POST /api/matches/refresh`). It probably deletes old matches before creating new ones. Look for something like:

```python
# Delete existing matches for this user before recomputing
db.query(Match).filter(Match.user_id == user.id).delete()
```

**Step 4.2 — If the pipeline already deletes and recreates matches,** the new thresholds automatically clean up old data on the next refresh. No extra work needed.

**Step 4.3 — If the pipeline does NOT delete old matches** (it only adds new ones), add a cleanup step at the beginning of the refresh:

```python
# Clean up: remove matches below the quality threshold
# This catches matches created before the threshold was introduced
deleted_count = db.query(Match).filter(
    Match.user_id == user.id,
    Match.match_score < MIN_MATCH_SCORE,
    # Don't delete matches the user has actively tracked (saved, applied, etc.)
    Match.application_status.is_(None),
).delete(synchronize_session=False)

if deleted_count > 0:
    logger.info(f"Cleaned up {deleted_count} sub-threshold matches for user {user.id}")
```

**Important:** Do NOT delete matches where the user has set an `application_status` (saved, applied, interviewing, etc.) — even if the score is low, the user explicitly engaged with that job and losing their tracking data would be harmful.

---

### Part 5: Align the Dashboard Metrics Count

The dashboard `qualified_jobs_count` must use the same filters as the matching pipeline.

**File to edit in Cursor:**
```
services/api/app/routers/dashboard.py
```

**Step 5.1 — Find the `qualified_jobs_count` calculation.** It will look something like:

```python
qualified_jobs_count = db.query(Match).filter(
    Match.user_id == user.id
).count()
```

**Step 5.2 — Add the match score threshold filter:**

```python
from app.services.matching import MIN_MATCH_SCORE, JOB_FRESHNESS_DAYS

qualified_jobs_count = db.query(Match).filter(
    Match.user_id == user.id,
    Match.match_score >= MIN_MATCH_SCORE,
).count()
```

**Note:** We don't also filter by job freshness here because the matching pipeline (Part 2) already prevents stale-job matches from being created. The `MIN_MATCH_SCORE` filter here is a safety net for any old records that haven't been cleaned up yet.

---

### Part 6: Update the Matches List Endpoints

Both `GET /api/matches` and `GET /api/matches/all` should also respect the minimum score threshold so the frontend never shows sub-threshold matches.

**File to edit in Cursor:**
```
services/api/app/routers/matches.py
```

**Step 6.1 — Find the `GET /api/matches` handler.** It queries matches for the current user. Add the score filter:

```python
from app.services.matching import MIN_MATCH_SCORE

# Add to the existing query:
.filter(Match.match_score >= MIN_MATCH_SCORE)
```

**Step 6.2 — Find the `GET /api/matches/all` handler.** Same change — add the score filter:

```python
.filter(Match.match_score >= MIN_MATCH_SCORE)
```

---

### Part 7: Update Sieve's System Prompt

Sieve needs to understand the winnowing philosophy so it can explain it when users ask "why do I only have X matches?" or "why are my matches so low?"

**File to edit in Cursor:**
```
services/api/app/services/sieve.py
```

**Step 7.1 — Find the `SIEVE_SYSTEM_PROMPT` string.** It's a long multi-line f-string that defines Sieve's personality and rules.

**Step 7.2 — Find the "CAPABILITIES" or "RESPONSE GUIDELINES" section** inside the system prompt. Add a new section about the winnowing philosophy. Look for where the prompt describes how Sieve should discuss matches, and add this block nearby:

```python
## Winnowing Philosophy — How Winnow Filters Matches
Winnow intentionally shows FEWER, HIGHER-QUALITY matches rather than flooding users with hundreds of poor fits. Here's how:
- Only jobs posted within the last 15 days are matched — stale postings waste time and lower interview rates.
- Only matches with a score of 50 or higher are shown — below that threshold, the fit isn't strong enough to be worth the candidate's effort.
- This is BY DESIGN. The name "Winnow" literally means to separate the wheat from the chaff.

When a user asks "why do I only have X matches?" or "why is my match count low?":
1. Reassure them: quality over quantity is the strategy. Applying to fewer, better-fit jobs leads to more interviews than carpet-bombing hundreds of poor-fit postings.
2. Explain: Winnow only shows recently posted jobs (last 15 days) with a match score of 50% or higher.
3. Suggest concrete actions to INCREASE their match count:
   - Complete their profile (more skills + experience = higher scores on more jobs)
   - Add certifications, target titles, and salary preferences
   - Broaden location or remote preferences if they're too restrictive
   - Check back regularly — new jobs are ingested daily
4. Reference their profile completeness score if it's below 80%: "Your profile is {X}% complete — filling in the gaps will likely surface more matches."
5. NEVER apologize for the low count. Frame it positively: "Winnow found X jobs that are genuinely a strong fit for you right now."
```

**Step 7.3 — Also update the user context section.** Find where `total_count` is referenced in the system prompt (the part that tells Sieve how many matches the user has). Make sure it now reflects the winnowed count, not the raw database count. The context loader should already be pulling from the filtered queries (since Part 5 changed the dashboard metrics), but verify.

In the `_build_user_context` function (or `load_user_context`), find where matches are counted:

```python
# Before (counts all):
context["matches"]["total_count"] = db.query(Match).filter(
    Match.user_id == user.id
).count()

# After (counts only qualified):
from app.services.matching import MIN_MATCH_SCORE

context["matches"]["total_count"] = db.query(Match).filter(
    Match.user_id == user.id,
    Match.match_score >= MIN_MATCH_SCORE,
).count()
```

---

### Part 8: Database Cleanup Migration (One-Time)

After deploying the code changes, run a cleanup to remove existing sub-threshold matches. This is optional — the next match refresh will clean them up automatically — but doing it proactively prevents confusion.

**Step 8.1 — Connect to the database.** In PowerShell:

```powershell
cd infra
docker compose exec postgres psql -U resumematch -d resumematch
```

**Step 8.2 — Check how many matches are below threshold (preview):**

```sql
-- Preview: how many will be affected?
SELECT
  COUNT(*) AS total_matches,
  COUNT(*) FILTER (WHERE match_score < 50) AS below_threshold,
  COUNT(*) FILTER (WHERE match_score >= 50) AS above_threshold
FROM matches;

-- Breakdown by score range
SELECT
  CASE
    WHEN match_score >= 80 THEN '80-100 (Strong)'
    WHEN match_score >= 50 THEN '50-79  (Reasonable)'
    WHEN match_score >= 30 THEN '30-49  (Weak)'
    ELSE                        '0-29   (Poor)'
  END AS score_range,
  COUNT(*) AS match_count
FROM matches
GROUP BY score_range
ORDER BY score_range;
```

**Step 8.3 — Delete sub-threshold matches that the user hasn't interacted with:**

```sql
-- Delete only untracked sub-threshold matches (safe)
DELETE FROM matches
WHERE match_score < 50
  AND application_status IS NULL;
```

**Step 8.4 — Verify the result:**

```sql
SELECT COUNT(*) FROM matches;
-- Should be noticeably lower than before
```

**Step 8.5 — Exit psql:**
```
\q
```

---

### Part 9: Test Everything

**Step 9.1 — Start all services.** In PowerShell:

```powershell
.\start-dev.ps1
```

Or manually:

```powershell
# Terminal 1: Docker
cd infra
docker compose up -d

# Terminal 2: API
cd services/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Frontend
cd apps/web
npm run dev
```

**Step 9.2 — Trigger a match refresh.** In Swagger UI (`http://127.0.0.1:8000/docs`), call `POST /api/matches/refresh`. Check the API server logs — you should see output like:

```
Match refresh for user 1: 14 matches created, 87 below threshold (MIN_MATCH_SCORE=50)
```

**Step 9.3 — Check the dashboard.**

1. Open browser: `http://localhost:3000/dashboard`
2. The "Qualified Jobs" count should now be a smaller, realistic number (matching what the Matches page shows)

**Step 9.4 — Check the matches page.**

1. Navigate to: `http://localhost:3000/matches`
2. Verify: every match shown has a score ≥ 50
3. Verify: all jobs shown were posted within the last 15 days
4. The count here should match (or be very close to) the dashboard count

**Step 9.5 — Test Sieve.**

1. Open the Sieve chatbot (floating button, bottom-right)
2. Ask: "Why do I only have a few matches?"
3. Verify Sieve responds with the winnowing philosophy:
   - Mentions quality over quantity
   - Mentions the 15-day freshness window and 50+ score threshold
   - Suggests completing their profile to increase matches
   - References their profile completeness score
   - Does NOT apologize or treat the low count as a problem

**Step 9.6 — Test edge cases.**

- [ ] User with 100% complete profile still gets reasonable matches
- [ ] User with 0 matches gets helpful guidance from Sieve (not an error)
- [ ] Matches with `application_status` set (saved, applied, etc.) are preserved even if score < 50
- [ ] `GET /api/matches/all` also respects the threshold

---

### Part 10: Lint and Format

**In PowerShell:**

```powershell
# Backend
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .

# Frontend (if any changes were made)
cd apps/web
npx next lint
```

---

## Summary Checklist

### Backend — Matching Pipeline
- [ ] `MIN_MATCH_SCORE = 50` constant added to `matching.py`
- [ ] `JOB_FRESHNESS_DAYS = 15` constant added to `matching.py`
- [ ] Job query in matching pipeline filters by `COALESCE(posted_at, ingested_at, created_at) >= cutoff`
- [ ] Match records only created when `computed_score >= MIN_MATCH_SCORE`
- [ ] Matches with `application_status` set are never auto-deleted (user tracked them)
- [ ] Logging added: "X matches created, Y below threshold"

### Backend — Dashboard Alignment
- [ ] `qualified_jobs_count` in `dashboard.py` filters by `match_score >= MIN_MATCH_SCORE`
- [ ] Dashboard count now matches what the Matches page shows

### Backend — Matches Endpoints
- [ ] `GET /api/matches` filters by `match_score >= MIN_MATCH_SCORE`
- [ ] `GET /api/matches/all` filters by `match_score >= MIN_MATCH_SCORE`

### Backend — Sieve
- [ ] Winnowing philosophy section added to `SIEVE_SYSTEM_PROMPT`
- [ ] Sieve explains quality-over-quantity when asked about low match counts
- [ ] Sieve suggests profile completion to increase matches
- [ ] Sieve's context loader counts only qualified matches (`match_score >= 50`)

### Database
- [ ] Old sub-threshold matches cleaned up (where `application_status IS NULL`)

### Verification
- [ ] Dashboard count matches Matches page count
- [ ] All displayed matches have score ≥ 50
- [ ] All displayed matches are for jobs posted within last 15 days
- [ ] Sieve answers "why so few matches?" correctly
- [ ] Match refresh logs show winnowing stats
- [ ] Tracked matches (saved/applied/interviewing) are never deleted regardless of score

Return code changes only.
