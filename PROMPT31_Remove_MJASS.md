# PROMPT31 — Remove MJASS Draft System (Disable, Don't Delete)

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

The MJASS (Match Job Application Submission System) draft workflow is not ready for users. It creates "draft applications" that the user can approve/reject/request changes on, but approving a draft doesn't actually submit anything to an employer — the user still has to apply manually. This creates confusion without adding value.

**This prompt disables MJASS from the user-facing experience while preserving the backend code for future use.** We're commenting out and removing references, not deleting files. When we're ready to build a proper auto-apply or guided-apply feature, the backend plumbing will still be there.

---

## Triggers — When to Use This Prompt

- Removing the "Create Draft" button from the Matches page.
- Removing the MJASS review page from the frontend.
- Cleaning up navigation or references to MJASS drafts.
- Simplifying the Matches page to focus on Prepare Materials + Application Status tracking.

---

## What Exists Today (the pieces to disable)

### Backend (KEEP — just disconnect from frontend)
1. **MJASS router:** `services/api/app/routers/mjass.py` — API endpoints for drafts (list, create, get, decide). **DO NOT DELETE this file.** Leave the backend routes registered — they're harmless and will be needed later.
2. **MJASS model:** `services/api/app/models/` — the `mjass_application_drafts` database table. **DO NOT DELETE or migrate away.** Leave the table in place.
3. **MJASS schemas:** `services/api/app/schemas/` — `DraftCreate`, `DraftDecision` schemas. **Leave as-is.**

### Frontend (REMOVE user-facing references)
1. **"Create Draft" button** on the Matches page: `apps/web/app/matches/page.tsx` — there's a button that calls `POST /api/mjass/drafts`. **REMOVE this button.**
2. **MJASS review page:** `apps/web/app/mjass/review/page.tsx` — a page where users review and decide on drafts. **DELETE this file** (or the entire `apps/web/app/mjass/` directory if nothing else is in it).
3. **Any navigation links** to `/mjass/review` or `/mjass` — remove from nav menus, sidebars, or dashboard links.
4. **Any imports** of MJASS-related components in other pages.

---

## What to Do — Step by Step

### Part 1: Remove the "Create Draft" Button from Matches Page

**File to edit in Cursor:**
```
apps/web/app/matches/page.tsx
```

**Step 1.1 — Find the "Create Draft" button.** Search the file for any of these strings:
- `"Create Draft"`
- `"create draft"`
- `/api/mjass/drafts`
- `mjass`
- `draft`

You're looking for a button or function that calls `POST /api/mjass/drafts`. It will be inside or near each match card.

**Step 1.2 — Remove the button entirely.** Delete the button element and any associated handler function. For example, you might find:

```tsx
// Something like this — DELETE IT:
<button onClick={() => handleCreateDraft(match.id)}>
  Create Draft
</button>
```

And a handler function like:

```tsx
// Something like this — DELETE IT:
const handleCreateDraft = async (matchId: number) => {
  const res = await fetch(`${API_BASE}/api/mjass/drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ match_id: matchId, ... }),
  });
  // ...
};
```

**Delete both the button JSX and the handler function.**

**Step 1.3 — Clean up imports.** After removing the button, check the top of the file for any imports that are now unused (e.g., a `DraftModal` component, or a router import only used for navigation to `/mjass/review`). Remove unused imports.

**Step 1.4 — Verify the "Prepare Materials" button is still there.** The Matches page should still have the "Prepare Materials" button that calls `POST /api/tailor/{job_id}`. This is the useful one — it generates tailored resumes and cover letters. Make sure you only removed the draft button, not the tailoring button.

---

### Part 2: Delete the MJASS Review Page

**Step 2.1 — Check what's in the mjass directory.** In Cursor's file explorer, look at:

```
apps/web/app/mjass/
```

You should see something like:
```
apps/web/app/mjass/
  └── review/
      └── page.tsx
```

**Step 2.2 — Delete the entire `mjass` directory:**

```
apps/web/app/mjass/        ← DELETE this entire folder
```

In Cursor: right-click the `mjass` folder in the file explorer → Delete.

If you prefer the command line (PowerShell):
```powershell
Remove-Item -Recurse -Force apps/web/app/mjass
```

---

### Part 3: Remove Any Navigation Links to MJASS

**Step 3.1 — Search the entire `apps/web/` directory** for references to MJASS or the review page. In Cursor, use **Ctrl+Shift+F** (global search) and search for each of these terms:

- `mjass`
- `/mjass`
- `review/page`
- `draft` (check context — don't remove unrelated uses of the word "draft")

**Step 3.2 — For each result found,** evaluate whether it's an MJASS reference:

- **Navigation links** like `<Link href="/mjass/review">` → **DELETE the link**
- **Nav menu items** like `{ label: "Drafts", href: "/mjass/review" }` → **DELETE the menu item**
- **Dashboard cards** linking to draft review → **DELETE the card or link**
- **Import statements** for MJASS components → **DELETE the import**

**Files most likely to contain references:**
```
apps/web/app/layout.tsx              ← root layout, may have nav links
apps/web/app/components/Navbar.tsx   ← navigation component (if it exists)
apps/web/app/dashboard/page.tsx      ← dashboard may link to drafts
apps/web/app/matches/page.tsx        ← already handled in Part 1
```

**Step 3.3 — Check the Navbar** (if PROMPT29 was already implemented). If there's a navigation component at `apps/web/app/components/Navbar.tsx`, search it for any "Drafts" or "MJASS" links and remove them.

---

### Part 4: Leave the Backend Alone

**DO NOT modify any of these files:**

```
services/api/app/routers/mjass.py       ← KEEP (backend router)
services/api/app/models/                ← KEEP (database model)
services/api/app/schemas/               ← KEEP (DraftCreate, DraftDecision)
services/api/app/main.py                ← KEEP the mjass router registered
services/api/alembic/versions/          ← DO NOT create a migration to drop the table
```

The backend stays intact. The MJASS API endpoints will still work if called directly (e.g., via Swagger), but no user-facing UI will trigger them. This makes it easy to re-enable later.

---

### Part 5: Add a Comment Explaining the Removal

**File to edit in Cursor:**
```
apps/web/app/matches/page.tsx
```

**Step 5.1 — Where the "Create Draft" button used to be,** add a comment so future developers understand:

```tsx
{/* 
  MJASS "Create Draft" button removed (PROMPT31). 
  The draft system is preserved in the backend (services/api/app/routers/mjass.py)
  but disabled from the UI until a proper guided-apply or auto-apply feature is built.
  To re-enable: restore the Create Draft button and the /mjass/review page.
  See: PROMPT31_Remove_MJASS.md for context.
*/}
```

---

### Part 6: Test

**Step 6.1 — Start the frontend:**

```powershell
cd apps/web
npm run dev
```

**Step 6.2 — Open the Matches page:** `http://localhost:3000/matches`

- [ ] **No "Create Draft" button visible** on any match card
- [ ] **"Prepare Materials" button still works** (calls `POST /api/tailor/{job_id}`)
- [ ] **Application Status dropdown still works** (saved/applied/interviewing/rejected/offer)
- [ ] **No console errors** related to missing MJASS imports or components

**Step 6.3 — Try to navigate to the old review page:** `http://localhost:3000/mjass/review`

- [ ] Should show a **404 page** (since the directory was deleted)

**Step 6.4 — Check navigation menus:**

- [ ] No "Drafts" or "MJASS" or "Review" links in any nav bar, sidebar, or dashboard

**Step 6.5 — Verify backend is untouched.** Open Swagger: `http://127.0.0.1:8000/docs`

- [ ] MJASS endpoints still appear under the "mjass" tag (`/api/mjass/drafts`, etc.)
- [ ] They still work if you call them manually (this confirms we didn't break the backend)

---

### Part 7: Lint

**In PowerShell:**

```powershell
# Frontend
cd apps/web
npx next lint

# Backend (shouldn't have changes, but good to verify)
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .
```

---

## Summary Checklist

### Frontend — Removed
- [ ] "Create Draft" button removed from `apps/web/app/matches/page.tsx`
- [ ] Handler function for creating drafts removed
- [ ] `apps/web/app/mjass/` directory deleted entirely
- [ ] All navigation links to `/mjass/review` removed (layout, navbar, dashboard)
- [ ] All unused MJASS-related imports removed
- [ ] Comment added explaining the removal and how to re-enable

### Frontend — Preserved (NOT touched)
- [ ] "Prepare Materials" button still works (tailored resume/cover letter generation)
- [ ] Application Status dropdown still works (saved/applied/interviewing/rejected/offer)
- [ ] Referral toggle still works (if implemented)

### Backend — Preserved (NOT touched)
- [ ] `services/api/app/routers/mjass.py` — still registered, still functional
- [ ] `mjass_application_drafts` database table — still exists, no migration
- [ ] `DraftCreate` / `DraftDecision` schemas — still in place
- [ ] MJASS endpoints visible in Swagger and callable

### Verification
- [ ] Matches page renders without errors
- [ ] No "Create Draft" button visible anywhere
- [ ] `/mjass/review` returns 404
- [ ] No MJASS links in navigation
- [ ] Backend MJASS endpoints still functional in Swagger
- [ ] Linted and clean

Return code changes only.
