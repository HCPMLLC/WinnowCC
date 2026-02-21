# PROMPT8: Dashboard — Quantified Metrics

## Purpose

Update the Winnow Dashboard to display five quantified metrics that give the candidate a clear, at-a-glance view of their job-search health: profile completeness, qualified job matches, submitted applications, interviews requested by employers, and offers received.

---

## Triggers — When to Use This Prompt

- Adding or refining the main Dashboard metrics view.
- Implementing SPEC Flow D (Tracking: saved / applied / interviewing / rejected / offer) with counts.
- Exposing profile completeness, match counts, and pipeline metrics on the Dashboard.
- Product asks for "quantified metrics" or "dashboard KPIs" for job seekers.

---

## The Five Metrics

1. **Profile completeness** — A single score (0–100%) showing how complete the candidate’s profile is (basics, experience, education, skills, preferences). Already implemented: `GET /api/profile/completeness` returns `{ score, deficiencies, recommendations }`.

2. **Qualified jobs matching candidate profile** — Count of jobs that match the candidate’s profile (e.g. current matches from the matches pipeline). Source: count of matches for the user (e.g. from `GET /api/matches` or a dedicated dashboard endpoint that returns this count).

3. **Submitted applications** — Count of applications the candidate has submitted (jobs they marked as “applied” or drafts with status “submitted”). Requires tracking data: per-job or per-match application status (e.g. saved / applied / interviewing / rejected / offer).

4. **Interviews requested by employers** — Count of jobs where the employer has requested an interview (e.g. user marked status “interviewing” or “interview_requested”). Same tracking model as above; filter by status.

5. **Offers of employment received** — Count of jobs where the candidate received an offer (e.g. user marked status “offer”). Same tracking model; filter by status.

---

## Backend Requirements

### Already available

- **Profile completeness:** `GET /api/profile/completeness` (see `services/api/app/routers/profile.py`) returns `ProfileCompletenessResponse`: `score` (0–100), `deficiencies`, `recommendations`. Use this for the Profile completeness metric.
- **Matches list:** `GET /api/matches` returns the user’s matches. The number of items (or a `total_count` if the API supports it) is the “qualified jobs matching candidate profile” count. If the API is paginated without a total, add a lightweight `GET /api/matches/summary` or include `total_count` in the list response so the Dashboard can show the count without loading all matches.

### To add or clarify

- **Application/interview/offer tracking:** SPEC Flow D describes marking jobs as saved / applied / interviewing / rejected / offer. Implement or reuse a tracking store so that:
  - Each user can set a **status** per job (or per match): e.g. `saved` | `applied` | `interviewing` | `rejected` | `offer`.
  - Status is persisted (e.g. `job_application` or `match_status` table, or reuse `mjass_application_drafts` status where it means “submitted” for applications).
- **Dashboard metrics endpoint (recommended):** Add `GET /api/dashboard/metrics` (or equivalent) that returns:
  - `profile_completeness_score`: int (0–100)
  - `qualified_jobs_count`: int (number of matches)
  - `submitted_applications_count`: int (count where status = applied or submitted)
  - `interviews_requested_count`: int (count where status = interviewing / interview_requested)
  - `offers_received_count`: int (count where status = offer)
  - All counts are for the current user. Implement by calling existing profile completeness and match/tracking queries and aggregating counts. This keeps the Dashboard to one request and a single contract.

### Data model (if not present)

- If there is no per-job/per-match status table, add one, e.g.:
  - Table: `application_tracking` (or extend Match with `application_status`).
  - Fields: `user_id`, `match_id` (or `job_id`), `status` (enum: saved | applied | interviewing | rejected | offer), `updated_at`.
  - API: PATCH or PUT to set status for a match/job; GET dashboard metrics to return the five counts.

---

## Frontend Requirements

### Location

- **Dashboard page:** `apps/web/app/dashboard/page.tsx`. Replace or extend the current placeholder content with a metrics section.

### Layout and content

1. **Metrics section**
   - Display the five metrics clearly and in a scannable layout (e.g. cards or a compact grid).
   - Label each metric in plain language:
     - “Profile completeness” — show score as a percentage (e.g. “78%”) and optionally a progress bar or ring. Link or short CTA to profile/edit if completeness is low.
     - “Qualified jobs” — show count (e.g. “24 jobs match your profile”). Link to matches list.
     - “Applications submitted” — show count (e.g. “12 applications”).
     - “Interviews requested” — show count (e.g. “3 interviews”).
     - “Offers received” — show count (e.g. “1 offer”).

2. **Data loading**
   - Prefer a single `GET /api/dashboard/metrics` (or equivalent) that returns all five values. If that endpoint does not exist, the prompt implementation should add it and have the Dashboard call it.
   - If the backend only exposes existing endpoints, the Dashboard may call `GET /api/profile/completeness` and `GET /api/matches` (and, when available, a tracking or summary endpoint) and compute counts on the client until a dedicated metrics API exists.
   - Handle loading and error states (skeleton, error message).

3. **Style**
   - Clean, modern, consistent with the rest of the app (e.g. Tailwind). Use typography and spacing so the numbers are easy to read and the purpose of each metric is clear to an average IT job seeker.

4. **Optional**
   - Short tooltip or help text for each metric (e.g. “Jobs that match your profile and preferences” for qualified jobs).
   - Secondary link from each metric to the relevant page (Profile, Matches, or a future Applications/Tracking page).

---

## Implementation Steps

### Step 1: Backend — Dashboard metrics API

- Add `GET /api/dashboard/metrics` (or mount under an existing router, e.g. `/api/profile/dashboard-metrics`).
- Response schema, e.g.:
  - `profile_completeness_score: int`
  - `qualified_jobs_count: int`
  - `submitted_applications_count: int`
  - `interviews_requested_count: int`
  - `offers_received_count: int`
- Implementation:
  - Profile completeness: reuse `compute_profile_completeness(profile_json)` and return `completeness.score`.
  - Qualified jobs: count of matches for the user (from Match table or existing matches list query).
  - Submitted / interviews / offers: if a tracking table or match status exists, count rows by status; otherwise return 0 for these until tracking is implemented.
- Document in OpenAPI/schema. Add tests if the project has API tests.

### Step 2: Backend — Tracking (if missing)

- If there is no way to store “applied” / “interviewing” / “offer” per job or match:
  - Add a migration for `application_tracking` (or add `application_status` to Match).
  - Add endpoints to set and get status per match/job.
  - In the dashboard metrics endpoint, aggregate counts by status and return them in the five fields above.

### Step 3: Frontend — Dashboard page

- In `apps/web/app/dashboard/page.tsx`:
  - Keep existing auth/onboarding guard.
  - Add a section that fetches dashboard metrics (from `GET /api/dashboard/metrics` or from existing APIs as a fallback).
  - Render the five metrics with labels and values. Use clear, non-technical copy.
  - Add loading and error handling. Link “Profile completeness” to profile edit and “Qualified jobs” to matches where appropriate.
  - Remove or replace the placeholder text (“Add candidate comparisons…”) with the new metrics (and any future pipeline/comparison content as needed).

### Step 4: Consistency and copy

- Ensure metric labels and any tooltips are consistent with this prompt and SPEC (e.g. “Submitted applications” = applications the candidate has submitted; “Interviews requested by employers” = employer-requested interviews; “Offers of employment received” = offers received).
- Use the same definitions in any API docs or in-app help.

---

## File and Component Reference

- **Dashboard page:** `apps/web/app/dashboard/page.tsx`
- **Profile completeness API:** `services/api/app/routers/profile.py` (`GET /completeness`)
- **Profile completeness service:** `services/api/app/services/profile_scoring.py`
- **Profile completeness schema:** `services/api/app/schemas/profile.py` (`ProfileCompletenessResponse`)
- **Matches API:** `services/api/app/routers/matches.py` (`GET /api/matches`)
- **Match model:** `services/api/app/models/match.py`
- **SPEC (Flow D — Tracking):** `SPEC.md` (saved / applied / interviewing / rejected / offer)
- **New dashboard metrics endpoint:** add under `services/api/app/routers/` (e.g. `dashboard.py` or under `profile.py`)

---

## Summary Checklist

- [ ] Backend: `GET /api/dashboard/metrics` (or equivalent) returns all five metrics.
- [ ] Backend: Tracking for applied / interviewing / offer exists and is used for counts (or stub with 0 until implemented).
- [ ] Frontend: Dashboard shows profile completeness (0–100%), qualified jobs count, submitted applications, interviews requested, offers received.
- [ ] Frontend: Clear labels, loading/error states, and links to Profile and Matches where appropriate.
- [ ] Copy and definitions align with this prompt and SPEC.
