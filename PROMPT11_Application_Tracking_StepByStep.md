# Winnow — Step-by-Step: Complete Application Tracking (Flow D)

## What You Already Have (Good News!)

After reviewing your OpenAPI specs (`openapi2.json`), your Match model, and `tmp_matches.json`, here's what **already exists**:

- ✅ `application_status` field on the **Match model** (currently nullable, stores `null` for all matches)
- ✅ `PATCH /api/matches/{match_id}/status` endpoint (in `services/api/app/routers/matches.py`)
- ✅ `ApplicationStatusUpdateRequest` and `ApplicationStatusUpdateResponse` schemas (in `services/api/app/schemas/matches.py`)

**What's still missing** and what we'll build:

- ❌ **Frontend UI** — status dropdown/buttons on the matches page so users can actually set statuses
- ❌ **Dashboard metrics endpoint** — `GET /api/dashboard/metrics` to count statuses for the 5 KPI cards
- ❌ **Dashboard frontend** — show the 5 KPI cards on `apps/web/app/dashboard/page.tsx`
- ❌ **Notes field** — SPEC says "Notes + links (minimal)" per tracked job

---

## PHASE 1: Add a Notes Field to Matches (Backend)

The SPEC says tracking should support "Notes + links (minimal)." The `application_status` field exists but there's no notes column yet.

### Step 1.1 — Create an Alembic migration to add a `notes` column

**Where to run this command:**
Open your terminal (PowerShell), navigate to the API folder, activate your virtual environment, then run the command.

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add notes to matches"
```

This creates a new file inside:
```
services/api/alembic/versions/xxxx_add_notes_to_matches.py
```
(The `xxxx` will be a random hash like `a1b2c3d4e5f6`)

### Step 1.2 — Edit the Match model to add the notes column

**File to open in Cursor:**
```
services/api/app/models/match.py
```

**What to do:** Find the class that defines the Match table (it will look something like `class Match(Base):`). Look for the existing columns. Add this new line **after the `application_status` column**:

```python
notes = Column(Text, nullable=True)
```

Make sure `Text` is imported at the top of the file. Look for the existing import line like:
```python
from sqlalchemy import Column, Integer, String, ...
```
and add `Text` to that list if it's not already there.

### Step 1.3 — Run the migration

**Where:** Same terminal (PowerShell, inside `services/api` with venv activated)

```powershell
alembic upgrade head
```

**What this does:** Applies the migration to your local Postgres database, adding the `notes` column to the `matches` table.

**If you get an error** like "Target database is not up to date": run `alembic upgrade head` first, then try the autogenerate again.

### Step 1.4 — Add notes to the match schemas

**File to open in Cursor:**
```
services/api/app/schemas/matches.py
```

**What to do:** Find the `ApplicationStatusUpdateRequest` schema class. It currently accepts a `status` field. Add `notes` as an optional field:

```python
notes: str | None = None
```

Also find whichever response schema returns match data (e.g., `MatchResponse` or similar) and make sure `notes` is included:

```python
notes: str | None = None
```

### Step 1.5 — Update the status endpoint to save notes

**File to open in Cursor:**
```
services/api/app/routers/matches.py
```

**What to do:** Find the function that handles `PATCH /api/matches/{match_id}/status`. Inside, where it updates `match.application_status`, add a line to also save notes:

```python
if payload.notes is not None:
    match.notes = payload.notes
```

---

## PHASE 2: Create the Dashboard Metrics Endpoint (Backend)

This adds a single API endpoint that returns all 5 KPI values the dashboard needs.

### Step 2.1 — Create a new router file

**Create this new file in Cursor:**
```
services/api/app/routers/dashboard.py
```

**Paste this content:**

```python
"""Dashboard metrics router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.match import Match
from app.models.candidate_profile import CandidateProfile
from app.services.auth import get_current_user
from app.services.profile_scoring import compute_profile_completeness

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardMetricsResponse(BaseModel):
    profile_completeness_score: int
    qualified_jobs_count: int
    submitted_applications_count: int
    interviews_requested_count: int
    offers_received_count: int


@router.get("/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the 5 dashboard KPIs for the current user."""

    user_id = user.id

    # 1) Profile completeness
    profile_score = 0
    profile_result = await db.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    profile = profile_result.scalar_one_or_none()
    if profile and profile.profile_json:
        completeness = compute_profile_completeness(profile.profile_json)
        profile_score = completeness.get("score", 0) if isinstance(completeness, dict) else getattr(completeness, "score", 0)

    # 2) Qualified jobs count (total matches for this user)
    matches_count_result = await db.execute(
        select(func.count(Match.id)).where(Match.user_id == user_id)
    )
    qualified_jobs_count = matches_count_result.scalar() or 0

    # 3) Submitted applications
    applied_result = await db.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user_id,
            Match.application_status == "applied",
        )
    )
    submitted_applications_count = applied_result.scalar() or 0

    # 4) Interviews requested
    interviews_result = await db.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user_id,
            Match.application_status == "interviewing",
        )
    )
    interviews_requested_count = interviews_result.scalar() or 0

    # 5) Offers received
    offers_result = await db.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user_id,
            Match.application_status == "offer",
        )
    )
    offers_received_count = offers_result.scalar() or 0

    return DashboardMetricsResponse(
        profile_completeness_score=profile_score,
        qualified_jobs_count=qualified_jobs_count,
        submitted_applications_count=submitted_applications_count,
        interviews_requested_count=interviews_requested_count,
        offers_received_count=offers_received_count,
    )
```

> **IMPORTANT NOTE:** The code above is a starting template. Your project may use **sync** SQLAlchemy (not async). If so, you'll need to adjust — replace `AsyncSession` with `Session`, remove `await` keywords, and use `from app.db.session import get_db` matching your existing pattern. **Look at an existing router** like `services/api/app/routers/matches.py` to see the exact pattern your project uses, and follow that same style.

### Step 2.2 — Register the new router in main.py

**File to open in Cursor:**
```
services/api/app/main.py
```

**What to do:** Find the section where other routers are registered. It will look like a series of lines like:

```python
from app.routers import auth, resume, profile, matches, ...

app.include_router(auth.router)
app.include_router(resume.router)
...
```

**Add these two lines** (at the end of the imports and registrations):

At the top with the other imports:
```python
from app.routers import dashboard
```

Where the other routers are registered:
```python
app.include_router(dashboard.router)
```

### Step 2.3 — Test the endpoint

**Where:** PowerShell terminal

1. Make sure Docker is running (Postgres + Redis):
   ```powershell
   cd infra
   docker compose up -d
   ```

2. Start the API:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. Open your browser and go to:
   ```
   http://127.0.0.1:8000/docs
   ```

4. Find the new `GET /api/dashboard/metrics` endpoint in the Swagger docs. You'll need to be logged in (have a valid session cookie) to test it.

---

## PHASE 3: Add Status Buttons to the Matches Page (Frontend)

### Step 3.1 — Open the matches page

**File to open in Cursor:**
```
apps/web/app/matches/page.tsx
```

### Step 3.2 — Add a status dropdown component

You need to add a dropdown or set of buttons next to each match card that lets the user set the status. Here's what to add.

**Find where each match card is rendered** (look for something like `matches.map(` or a loop that renders individual job match cards).

**Inside each match card**, add a status selector. Here's a React component you can add as a **new file**:

**Create this new file in Cursor:**
```
apps/web/app/components/ApplicationStatusSelect.tsx
```

**Paste this content:**

```tsx
"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const STATUSES = [
  { value: "", label: "— No status —", color: "bg-gray-100 text-gray-600" },
  { value: "saved", label: "💾 Saved", color: "bg-blue-100 text-blue-800" },
  { value: "applied", label: "📨 Applied", color: "bg-yellow-100 text-yellow-800" },
  { value: "interviewing", label: "🎤 Interviewing", color: "bg-purple-100 text-purple-800" },
  { value: "rejected", label: "❌ Rejected", color: "bg-red-100 text-red-800" },
  { value: "offer", label: "🎉 Offer", color: "bg-green-100 text-green-800" },
];

interface Props {
  matchId: number;
  currentStatus: string | null;
  onStatusChange?: (newStatus: string) => void;
}

export default function ApplicationStatusSelect({ matchId, currentStatus, onStatusChange }: Props) {
  const [status, setStatus] = useState(currentStatus || "");
  const [saving, setSaving] = useState(false);

  const handleChange = async (newStatus: string) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/matches/${matchId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ status: newStatus || null }),
      });
      if (res.ok) {
        setStatus(newStatus);
        onStatusChange?.(newStatus);
      } else {
        console.error("Failed to update status");
      }
    } catch (err) {
      console.error("Error updating status:", err);
    } finally {
      setSaving(false);
    }
  };

  const current = STATUSES.find((s) => s.value === status) || STATUSES[0];

  return (
    <div className="flex items-center gap-2">
      <select
        value={status}
        onChange={(e) => handleChange(e.target.value)}
        disabled={saving}
        className={`text-sm font-medium rounded-md px-3 py-1.5 border border-gray-300 
                     focus:outline-none focus:ring-2 focus:ring-green-500 ${current.color}
                     ${saving ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
      >
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
      {saving && <span className="text-xs text-gray-400">Saving...</span>}
    </div>
  );
}
```

### Step 3.3 — Use the component in the matches page

**File to edit in Cursor:**
```
apps/web/app/matches/page.tsx
```

**At the top of the file**, add this import:
```tsx
import ApplicationStatusSelect from "../components/ApplicationStatusSelect";
```

**Inside each match card** (find where match data like title, score, etc. is rendered), add:

```tsx
<ApplicationStatusSelect
  matchId={match.id}
  currentStatus={match.application_status}
/>
```

Place it wherever makes sense visually — typically near the bottom of each match card, or next to the job title.

---

## PHASE 4: Build the Dashboard Metrics Cards (Frontend)

### Step 4.1 — Open the dashboard page

**File to open in Cursor:**
```
apps/web/app/dashboard/page.tsx
```

### Step 4.2 — Add metrics fetching and display

**What to do:** Find the main dashboard component. Add a state variable and fetch call for the metrics, then render 5 cards.

Add this code **inside the dashboard component** (adapt to match your existing code style):

**Near the top of the component function**, add state and effect:

```tsx
const [metrics, setMetrics] = useState<{
  profile_completeness_score: number;
  qualified_jobs_count: number;
  submitted_applications_count: number;
  interviews_requested_count: number;
  offers_received_count: number;
} | null>(null);

useEffect(() => {
  const fetchMetrics = async () => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/dashboard/metrics`,
        { credentials: "include" }
      );
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard metrics:", err);
    }
  };
  fetchMetrics();
}, []);
```

Make sure `useState` and `useEffect` are imported at the top:
```tsx
import { useState, useEffect } from "react";
```

**In the JSX/return section**, add the 5 metric cards:

```tsx
{/* Dashboard Metrics */}
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
  {/* Profile Completeness */}
  <div className="bg-white rounded-xl shadow p-5 border-l-4 border-emerald-500">
    <p className="text-sm text-gray-500 mb-1">Profile Completeness</p>
    <p className="text-3xl font-bold text-emerald-700">
      {metrics ? `${metrics.profile_completeness_score}%` : "—"}
    </p>
  </div>

  {/* Qualified Jobs */}
  <div className="bg-white rounded-xl shadow p-5 border-l-4 border-blue-500">
    <p className="text-sm text-gray-500 mb-1">Qualified Jobs</p>
    <p className="text-3xl font-bold text-blue-700">
      {metrics ? metrics.qualified_jobs_count : "—"}
    </p>
  </div>

  {/* Applications Submitted */}
  <div className="bg-white rounded-xl shadow p-5 border-l-4 border-yellow-500">
    <p className="text-sm text-gray-500 mb-1">Applications Submitted</p>
    <p className="text-3xl font-bold text-yellow-700">
      {metrics ? metrics.submitted_applications_count : "—"}
    </p>
  </div>

  {/* Interviews Requested */}
  <div className="bg-white rounded-xl shadow p-5 border-l-4 border-purple-500">
    <p className="text-sm text-gray-500 mb-1">Interviews Requested</p>
    <p className="text-3xl font-bold text-purple-700">
      {metrics ? metrics.interviews_requested_count : "—"}
    </p>
  </div>

  {/* Offers Received */}
  <div className="bg-white rounded-xl shadow p-5 border-l-4 border-green-500">
    <p className="text-sm text-gray-500 mb-1">Offers Received</p>
    <p className="text-3xl font-bold text-green-700">
      {metrics ? metrics.offers_received_count : "—"}
    </p>
  </div>
</div>
```

---

## PHASE 5: Verify Everything Works

### Step 5.1 — Start all services

Open 3 separate PowerShell terminals:

**Terminal 1 — Infrastructure (Docker):**
```powershell
cd infra
docker compose up -d
```

**Terminal 2 — API:**
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 — Web:**
```powershell
cd apps/web
npm run dev
```

Or use the one-command script:
```powershell
.\start-dev.ps1
```

### Step 5.2 — Test the full flow

1. Open **http://localhost:3000** in your browser
2. Log in with your test account
3. Go to the **Matches** page
4. On any match card, use the new **status dropdown** to set it to "Applied"
5. Go to the **Dashboard** page
6. Verify the "Applications Submitted" card now shows **1**
7. Go back to Matches, set another job to "Interviewing"
8. Go back to Dashboard — "Interviews Requested" should show **1**

### Step 5.3 — Run linting (optional but recommended)

**PowerShell — API linting:**
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .
```

**PowerShell — Web linting:**
```powershell
cd apps/web
npm run lint
```

---

## Summary — All Files You'll Touch

| # | Action | File Path | What You Do |
|---|--------|-----------|-------------|
| 1 | EDIT | `services/api/app/models/match.py` | Add `notes = Column(Text, nullable=True)` |
| 2 | RUN | Terminal in `services/api/` | `alembic revision --autogenerate -m "add notes to matches"` |
| 3 | RUN | Terminal in `services/api/` | `alembic upgrade head` |
| 4 | EDIT | `services/api/app/schemas/matches.py` | Add `notes: str \| None = None` to request + response schemas |
| 5 | EDIT | `services/api/app/routers/matches.py` | Save `payload.notes` in the status PATCH handler |
| 6 | CREATE | `services/api/app/routers/dashboard.py` | New file — dashboard metrics endpoint |
| 7 | EDIT | `services/api/app/main.py` | Import and register `dashboard.router` |
| 8 | CREATE | `apps/web/app/components/ApplicationStatusSelect.tsx` | New file — status dropdown component |
| 9 | EDIT | `apps/web/app/matches/page.tsx` | Import + use `ApplicationStatusSelect` in match cards |
| 10 | EDIT | `apps/web/app/dashboard/page.tsx` | Add metrics fetch + 5 KPI cards |

---

## Troubleshooting

**"Module not found" when importing dashboard router:**
- Make sure the file is saved at exactly `services/api/app/routers/dashboard.py`
- Make sure the import in `main.py` matches: `from app.routers import dashboard`

**"Column 'notes' does not exist" errors:**
- You need to run `alembic upgrade head` after creating the migration
- Make sure Docker/Postgres is running first: `cd infra && docker compose up -d`

**Status dropdown doesn't save:**
- Open browser DevTools (F12) → Network tab → look for the PATCH request
- Check if you're logged in (cookie `rm_session` should be present)
- Check the API terminal for error messages

**Dashboard shows all zeros:**
- You need to set statuses on some matches first (go to Matches page, use the dropdown)
- Check browser DevTools → Network → look for the `GET /api/dashboard/metrics` call

**"sync vs async" errors in dashboard.py:**
- Look at another working router (like `matches.py`) and copy its exact pattern for database session usage
- If your project uses sync SQLAlchemy, remove `await` and use `Session` instead of `AsyncSession`
