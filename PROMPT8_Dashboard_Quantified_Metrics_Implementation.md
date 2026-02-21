# PROMPT8_Dashboard_Quantified_Metrics_Implementation.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Complete the Winnow Dashboard so it displays five quantified metrics that give the candidate a clear, at-a-glance view of their job-search health. The backend endpoint already exists; this prompt focuses on wiring the frontend, adding a pipeline visualization, and polishing the full dashboard experience.

---

## Triggers — When to Use This Prompt

- Completing the Dashboard metrics cards UI.
- Wiring the existing `GET /api/dashboard/metrics` endpoint to the frontend.
- Adding a visual application pipeline (funnel) to the dashboard.
- Product asks for "dashboard KPIs," "quantified metrics," or "job-search health."

---

## What Already Exists (DO NOT recreate)

Read the codebase carefully. These are already implemented:

1. **Backend endpoint:** `GET /api/dashboard/metrics` — registered in `services/api/app/main.py`, defined in `services/api/app/routers/dashboard.py`. Returns `DashboardMetricsResponse` with fields:
   - `profile_completeness_score` (int, 0–100)
   - `qualified_jobs_count` (int)
   - `submitted_applications_count` (int)
   - `interviews_requested_count` (int)
   - `offers_received_count` (int)

2. **Profile completeness API:** `GET /api/profile/completeness` in `services/api/app/routers/profile.py` returns `ProfileCompletenessResponse` with `score`, `deficiencies`, `recommendations`.

3. **Application status tracking:** `PATCH /api/matches/{match_id}/status` in `services/api/app/routers/matches.py` accepts `ApplicationStatusUpdateRequest` with status enum: `saved | applied | interviewing | rejected | offer`. The `application_status` column exists on the Match model.

4. **Match listing:** `GET /api/matches` returns the user's job matches with scores, reasons, and `application_status`.

5. **Dashboard page shell:** `apps/web/app/dashboard/page.tsx` exists with auth/onboarding guard and placeholder content.

6. **Sieve widget:** Already integrated in `apps/web/app/layout.tsx`. Do not modify.

---

## What to Build

### Part 1: Dashboard Metrics Cards (frontend only)

**File to modify:** `apps/web/app/dashboard/page.tsx`

Replace or extend the existing placeholder content in the Dashboard page with a metrics section. Keep the existing auth/onboarding guard logic exactly as-is.

#### 1.1 Fetch metrics on load

- On component mount, call `GET /api/dashboard/metrics` with `credentials: "include"`.
- Use `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`) as the API base.
- Store the response in component state.
- Handle loading state (show skeleton cards or spinner while fetching).
- Handle error state (show a subtle error message, not a crash).

#### 1.2 Render five metric cards

Display the five metrics in a responsive grid: 5 columns on desktop (lg), 2–3 on tablet (sm/md), 1 on mobile.

Each card must include:
- **Icon** (emoji or Lucide icon) — visually distinct per metric.
- **Label** — plain language, consistent with SPEC:
  - "Profile Completeness"
  - "Qualified Jobs"
  - "Applications Submitted"
  - "Interviews Requested"
  - "Offers Received"
- **Value** — large, bold number. For profile completeness, show as percentage (e.g. "78%"). For others, show as integer count.
- **Accent color** — each card has a unique left border or accent:
  - Profile Completeness → emerald/green
  - Qualified Jobs → blue
  - Applications Submitted → amber/yellow
  - Interviews Requested → purple
  - Offers Received → green (darker than profile)
- **Link** — Profile Completeness links to `/profile`. Qualified Jobs links to `/matches`.
- **Tooltip or subtitle** — short help text below the label:
  - Profile Completeness: "How complete your profile is"
  - Qualified Jobs: "Jobs matching your profile and preferences"
  - Applications Submitted: "Jobs you've marked as applied"
  - Interviews Requested: "Jobs where you're interviewing"
  - Offers Received: "Jobs where you received an offer"

#### 1.3 Profile completeness — progress ring (optional but recommended)

For the Profile Completeness card, add a small circular progress ring or horizontal progress bar showing the percentage visually, not just as a number. Use SVG or CSS-only approach. If completeness is below 60%, show a subtle CTA: "Complete your profile →" linking to `/profile`.

---

### Part 2: Application Pipeline Visualization

**File:** `apps/web/app/dashboard/page.tsx` (same file, below the metrics cards)

Add a horizontal funnel/pipeline section showing the flow from matches → saved → applied → interviewing → offer. This gives the user a visual sense of their job-search pipeline.

#### 2.1 Data source

Use the same `GET /api/dashboard/metrics` response. Additionally, to get the `saved` count, either:
- Add `saved_count` to the `DashboardMetricsResponse` (preferred — see Part 4 below), OR
- Count matches with `application_status === "saved"` client-side from `GET /api/matches` if that data is available.

#### 2.2 Layout

A horizontal bar or funnel with 5 stages:
```
Qualified Jobs (24) → Saved (8) → Applied (5) → Interviewing (2) → Offers (1)
```

Use colored segments or connected cards. Each stage's width or prominence should reflect relative count. Show the numbers prominently.

Style: Tailwind, clean, modern. Use the same accent colors from the metric cards for consistency.

---

### Part 3: Recent Activity Section (optional but recommended)

**File:** `apps/web/app/dashboard/page.tsx` (same file, below the pipeline)

Show the user's 5 most recently updated matches (by status change or by match creation date). Display:
- Job title + company
- Current status badge (colored: saved=blue, applied=yellow, interviewing=purple, rejected=red, offer=green)
- Match score
- Date of last status change

Data source: `GET /api/matches` — sort/filter client-side for the 5 most recent, or add a query parameter if the API supports it.

---

### Part 4: Backend Enhancement — Add `saved_count` and `rejected_count`

**File to modify:** `services/api/app/routers/dashboard.py`

Add two new fields to `DashboardMetricsResponse`:
- `saved_count`: count of matches where `application_status == "saved"`
- `rejected_count`: count of matches where `application_status == "rejected"`

**Steps:**

1. Open `services/api/app/routers/dashboard.py`
2. Find the `DashboardMetricsResponse` Pydantic model (or its definition in `services/api/app/schemas/`). Add:
   ```python
   saved_count: int
   rejected_count: int
   ```
3. In the `get_dashboard_metrics` function, add queries for these two counts following the exact same pattern used for `submitted_applications_count`, `interviews_requested_count`, and `offers_received_count` — just filter by `"saved"` and `"rejected"` respectively.
4. Return the new fields in the response.

**Migration:** Not needed — no database schema change, only a response schema change.

---

### Part 5: Dashboard Page — Full Layout Specification

The final `apps/web/app/dashboard/page.tsx` layout should be (top to bottom):

1. **Page header:** "Dashboard" title + welcome message (e.g. "Welcome back, {name}" if the user's name is available from auth/onboarding, otherwise just "Dashboard").
2. **Metrics cards row:** 5 cards in a responsive grid (Part 1).
3. **Application pipeline:** Horizontal funnel visualization (Part 2).
4. **Recent activity:** 5 most recent match/status updates (Part 3).
5. **Empty states:**
   - If `qualified_jobs_count === 0`: Show a CTA: "No matches yet. Upload your resume and run matching to get started." Link to `/upload`.
   - If all tracking counts are 0: Show a CTA: "Start tracking! Mark jobs as saved or applied from the Matches page." Link to `/matches`.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Dashboard page | `apps/web/app/dashboard/page.tsx` | MODIFY — add metrics cards, pipeline, recent activity |
| Dashboard metrics API | `services/api/app/routers/dashboard.py` | MODIFY — add `saved_count` and `rejected_count` |
| Dashboard response schema | `services/api/app/routers/dashboard.py` (or `services/api/app/schemas/dashboard.py` if separated) | MODIFY — add two fields |
| Profile completeness API | `services/api/app/routers/profile.py` | READ ONLY — already exists |
| Matches API | `services/api/app/routers/matches.py` | READ ONLY — already exists |
| Match model | `services/api/app/models/match.py` | READ ONLY — `application_status` column exists |
| Profile scoring service | `services/api/app/services/profile_scoring.py` | READ ONLY — `compute_profile_completeness` exists |
| SPEC (Flow D — Tracking) | `SPEC.md` | REFERENCE — status enum: saved / applied / interviewing / rejected / offer |
| SPEC (§3.6 — Dashboard) | `SPEC.md` | REFERENCE — tabs: Profile, Matches, Resumes, Tracking |

---

## Style and Copy Guidelines

- **Tailwind CSS** — use existing Tailwind setup in `apps/web`. No additional CSS libraries.
- **Colors** — use Winnow brand palette where possible (hunter green `#1B3025`, gold `#E8C84A`, teal `#B8E4EA`). Metric card accents can use Tailwind's built-in palette (emerald, blue, amber, purple, green).
- **Typography** — match existing app font. Numbers should be large (text-3xl or text-4xl) and bold. Labels should be text-sm and muted.
- **Responsiveness** — cards must work on mobile (stack to 1 column), tablet (2 columns), and desktop (5 columns).
- **Loading** — skeleton placeholders while fetching (gray pulsing rectangles), not a full-page spinner.
- **Accessibility** — metric cards should have `aria-label` or `role="status"` for screen readers. Links should be clearly focusable.

---

## Copy Definitions (use these exact labels and definitions)

| Metric | Label | Tooltip / Subtitle | Source |
|--------|-------|---------------------|--------|
| Profile Completeness | "Profile Completeness" | "How complete your profile is" | `profile_completeness_score` from API |
| Qualified Jobs | "Qualified Jobs" | "Jobs matching your profile and preferences" | `qualified_jobs_count` from API |
| Applications Submitted | "Applications Submitted" | "Jobs you've marked as applied" | `submitted_applications_count` from API |
| Interviews Requested | "Interviews Requested" | "Jobs where you're interviewing" | `interviews_requested_count` from API |
| Offers Received | "Offers Received" | "Jobs where you received an offer" | `offers_received_count` from API |

---

## Implementation Order (for a beginner following in Cursor)

Follow these steps in exact order:

### Step 1: Backend — Add saved_count and rejected_count

1. Open `services/api/app/routers/dashboard.py` in Cursor.
2. Find the `DashboardMetricsResponse` class. Add `saved_count: int` and `rejected_count: int`.
3. In the `get_dashboard_metrics` function, add two queries following the existing pattern:
   - Count matches where `application_status == "saved"` → `saved_count`
   - Count matches where `application_status == "rejected"` → `rejected_count`
4. Add these to the return statement.
5. Save the file.

### Step 2: Test the backend change

1. In PowerShell, navigate to API and restart:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
2. Open `http://127.0.0.1:8000/docs` and test `GET /api/dashboard/metrics`. Verify the response now includes `saved_count` and `rejected_count`.

### Step 3: Frontend — Build the dashboard page

1. Open `apps/web/app/dashboard/page.tsx` in Cursor.
2. Keep the existing auth/onboarding guard at the top of the component (do not remove or rewrite it).
3. Add state for metrics: `const [metrics, setMetrics] = useState(null)` and `const [loading, setLoading] = useState(true)`.
4. Add a `useEffect` that fetches `GET /api/dashboard/metrics` with `credentials: "include"` and sets the state.
5. In the JSX, add the metrics cards grid (5 cards, responsive).
6. Below the cards, add the pipeline visualization.
7. Optionally add the recent activity section.
8. Add empty states for zero-data scenarios.
9. Save the file.

### Step 4: Test the frontend

1. Make sure infra is running: `cd infra && docker compose up -d`
2. Start the web dev server: `cd apps/web && npm run dev`
3. Open `http://localhost:3000/dashboard` in your browser.
4. Verify:
   - [ ] 5 metric cards are visible with correct labels and values.
   - [ ] Profile Completeness shows a percentage.
   - [ ] Clicking "Profile Completeness" navigates to `/profile`.
   - [ ] Clicking "Qualified Jobs" navigates to `/matches`.
   - [ ] Pipeline visualization shows the funnel.
   - [ ] Loading state shows skeleton cards briefly.
   - [ ] If no matches exist, the empty state CTA is shown.

### Step 5: Lint and format

```powershell
# API
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .

# Web
cd apps/web
npm run lint
```

---

## Non-Goals (Do NOT implement in this prompt)

- Do not modify the `application_status` field on Match or the `PATCH /api/matches/{match_id}/status` endpoint — these already work.
- Do not add new database tables or migrations — the backend data model is sufficient.
- Do not modify the Sieve chatbot widget.
- Do not add subscription/billing logic to the dashboard.
- Do not add a Tracking tab or separate tracking page — that is a future task. The dashboard pipeline visualization serves as the MVP tracking view.

---

## Summary Checklist

- [ ] Backend: `saved_count` and `rejected_count` added to `GET /api/dashboard/metrics` response.
- [ ] Frontend: Dashboard page fetches `GET /api/dashboard/metrics` on load.
- [ ] Frontend: 5 metric cards displayed in responsive grid with icons, labels, values, accents, tooltips, and links.
- [ ] Frontend: Profile Completeness card shows progress ring/bar and links to `/profile`.
- [ ] Frontend: Qualified Jobs card links to `/matches`.
- [ ] Frontend: Application pipeline visualization (funnel) shown below cards.
- [ ] Frontend: Loading skeleton shown while fetching.
- [ ] Frontend: Empty states shown when no data exists.
- [ ] Frontend: Responsive on mobile, tablet, and desktop.
- [ ] Copy and definitions align with this prompt and SPEC.
- [ ] Linted and formatted (ruff for API, next lint for web).
