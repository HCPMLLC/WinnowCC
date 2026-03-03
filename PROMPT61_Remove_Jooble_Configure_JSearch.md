# PROMPT 61 — Remove Jooble, Verify JSearch Is Working

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making any changes.

## Purpose

Remove the Jooble job source (paid, low value, duplicates coverage from other sources) and confirm that JSearch (paid, high value — aggregates LinkedIn, Indeed, Glassdoor) is properly configured and working.

**No code changes are needed.** This prompt only edits the `.env` configuration file and verifies the result.

### Why remove Jooble?

- Jooble is a paid API that mostly returns the same jobs you already get from free sources (Remotive, Adzuna, USAJobs, etc.)
- JSearch is also paid, but it pulls from LinkedIn, Indeed, and Glassdoor — sources you can't get any other way
- Removing Jooble saves money and reduces noise in your job results

---

## Prerequisites

- ✅ `services/api/.env` file exists with `JOOBLE_API_KEY`, `RAPIDAPI_KEY`, and `JOB_SOURCES` already configured
- ✅ JSearch source code is already implemented in the codebase (no new code needed)
- ✅ You know how to open a file in Cursor (or any text editor)

---

## Step 1: Open the .env File

**What is the .env file?** It's a settings file that tells your backend which API keys to use and which job sources to pull from. Think of it as the "control panel" for your backend.

**How to open it in Cursor:**

1. Look at the left sidebar (the file tree)
2. Click the little arrow next to `services` to expand it
3. Click the little arrow next to `api` to expand it
4. You should now see a file called `.env` — click it to open it

**If you don't see `.env` in the sidebar:**
The file might be hidden. In Cursor, click **File** in the top menu → **Preferences** → **Settings**, then search for `files.exclude` and make sure `**/.env` is NOT in the list. Alternatively, just open the file directly: press **Ctrl+O**, then type `services/api/.env` and press Enter.

---

## Step 2: Delete the Jooble API Key Line

**What you're looking for:** A line that says:
```
JOOBLE_API_KEY=<your-jooble-api-key>
```

**How to delete it:**

1. Find this line in the file (it should be around line 7)
2. Click anywhere on that line so your cursor is on it
3. Press **Ctrl+Shift+K** — this deletes the entire line
   - Alternative: Click at the very beginning of the line, hold **Shift**, press the **Down Arrow** once, then press **Delete**
4. The line should now be completely gone — not commented out, not blank, just gone

**What it should look like BEFORE:**
```
USAJOBS_EMAIL=rlevi@hcpm.llc
JOOBLE_API_KEY=<your-jooble-api-key>
RAPIDAPI_KEY=<your-rapidapi-key>
```

**What it should look like AFTER:**
```
USAJOBS_EMAIL=rlevi@hcpm.llc
RAPIDAPI_KEY=<your-rapidapi-key>
```

---

## Step 3: Remove Jooble from the Job Sources List

**What you're looking for:** A line that starts with `JOB_SOURCES=` and lists all the job sources separated by commas. It currently looks like this:
```
JOB_SOURCES=remotive,themuse,greenhouse,lever,remoteok,adzuna,jooble,usajobs,jobicy,himalayas,manual,jsearch
```

**How to edit it:**

1. Find the `JOB_SOURCES=` line (it should now be around line 8, since you deleted the Jooble line above)
2. Find the word `,jooble` in that line — it comes right after `adzuna`
3. Select exactly `,jooble` (including the comma before it) and delete it
   - Tip: Press **Ctrl+H** to open Find and Replace. In the "Find" box, type `,jooble` — in the "Replace" box, leave it empty — then click the replace button (the single arrow icon). This is the safest way to do it.
4. Make sure there are no double commas (`,,`) left behind and no spaces anywhere in the list

**What the line should look like AFTER:**
```
JOB_SOURCES=remotive,themuse,greenhouse,lever,remoteok,adzuna,usajobs,jobicy,himalayas,manual,jsearch
```

**Double-check:** Count the sources. You should have exactly 11 sources listed (not 12). The word `jooble` should appear nowhere on this line.

---

## Step 4: Confirm the JSearch Key Is Present

**What you're checking:** That the `RAPIDAPI_KEY` line exists. This is the key that powers JSearch. It should already be in your file — you are NOT adding anything, just confirming it's there.

**Look for this line** (it should be right after the `USAJOBS_EMAIL` line):
```
RAPIDAPI_KEY=<your-rapidapi-key>
```

**Also confirm:** that `jsearch` appears at the end of your `JOB_SOURCES` line. Look at the line you edited in Step 3 — it should end with `...manual,jsearch`.

If both are present, you're good. Move on to Step 5.

---

## Step 5: Save the File

Press **Ctrl+S** to save.

That's it. If the file tab at the top shows a dot or circle next to the filename, it means there are unsaved changes — press Ctrl+S again until the dot disappears.

---

## Step 6: Restart the API Server

The backend needs to be restarted so it picks up the changes you made to `.env`.

**How to do this in the Cursor terminal:**

1. Click on the terminal panel at the bottom of Cursor (the black area). If you don't see it, go to **Terminal** in the top menu → **New Terminal**.
2. If the API server is already running (you see scrolling log messages), stop it by pressing **Ctrl+C**
3. Wait until you see the cursor blinking on a fresh line (this means the server has stopped)
4. Type these commands one at a time, pressing **Enter** after each:

```bash
cd services/api
```

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Wait a few seconds. You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

6. **Open a second terminal** (click the **+** button in the terminal panel) and start the worker:

```bash
cd services/api
```

```bash
.venv/Scripts/python.exe -m app.worker
```

You should see:
```
Worker started, listening on queues: default, high, low
```

**If you see red error text**, stop and read it. Common issues:
- `KeyError: 'JOOBLE_API_KEY'` → Something in the code still references Jooble. This should not happen, but if it does, check that you only deleted the `.env` line and the `JOB_SOURCES` entry — no code files should have been changed.

---

## Step 7: Verify JSearch Is Working

**What you're doing:** Running a test job ingestion to confirm JSearch pulls jobs successfully.

**Step 7.1 — Open Swagger UI:**

1. Open your web browser
2. Go to: `http://localhost:8000/docs`
3. You should see the Swagger UI page with a list of API endpoints

**Step 7.2 — Trigger a Job Ingestion:**

1. Scroll down and find the section labeled **"Admin"** or **"Jobs"**
2. Look for an endpoint like `POST /api/admin/ingest-jobs` or similar
3. Click on it to expand it
4. Click **"Try it out"**
5. If it asks for a body/payload, you can use:
   ```json
   {
     "keywords": ["software engineer"],
     "sources": ["jsearch"]
   }
   ```
6. Click **"Execute"**

**What to look for in the response:**
- A `200` status code means success
- The response should mention that a job ingestion task has been queued or started
- If it returns a `task_id`, that means it was sent to the worker for processing

**Step 7.3 — Check the Worker Terminal:**

1. Switch to the terminal where the worker is running (the second terminal from Step 6)
2. You should see log messages appearing as the worker processes the job ingestion
3. Look for lines mentioning `jsearch` — for example:
   ```
   [JSearch] Fetching jobs for query: software engineer
   [JSearch] Found 10 jobs
   ```
4. If you see errors like `403 Forbidden` or `Invalid API key`, your `RAPIDAPI_KEY` may be expired or incorrect — log in to rapidapi.com and check your JSearch subscription

**Step 7.4 — Confirm Jooble Is Gone:**

1. In the worker terminal output, you should NOT see any lines mentioning `jooble`
2. If you triggered a full ingestion (all sources), the worker should skip jooble entirely because it's no longer in the `JOB_SOURCES` list
3. This confirms the removal was successful

---

## Summary Checklist

Before marking this prompt complete, verify each item:

- [ ] The `JOOBLE_API_KEY=...` line has been completely deleted from `services/api/.env`
- [ ] The `JOB_SOURCES=` line no longer contains `jooble` (11 sources, not 12)
- [ ] The `RAPIDAPI_KEY=...` line is still present in `services/api/.env`
- [ ] The `JOB_SOURCES=` line still contains `jsearch` at the end
- [ ] The API server starts with no errors
- [ ] The worker starts with no errors
- [ ] A test job ingestion with `jsearch` as the source completes successfully
- [ ] No `jooble` references appear in the worker logs during ingestion

---

## Files Modified in This Prompt

| Action | File Path |
|--------|-----------|
| Modified | `services/api/.env` (1 line deleted, 1 line edited) |

No code files were created or modified. This was a configuration-only change.

---

## Notes

- **JSearch costs money.** It uses your RapidAPI subscription. Monitor your usage at [rapidapi.com/dashboard](https://rapidapi.com/dashboard) to avoid surprise charges. The free tier typically allows ~500 requests/month; paid plans scale from there.
- **Jooble API key is still valid.** If you ever want to re-add Jooble, you can add the `JOOBLE_API_KEY` line back to `.env` and add `,jooble` back to `JOB_SOURCES`. The code for it still exists in the codebase — you only removed the configuration, not the code.
- **JSearch aggregates LinkedIn, Indeed, and Glassdoor.** These are the three largest job boards that don't offer free APIs, so JSearch is the only way to get their listings programmatically.

---

**PROMPT61_Remove_Jooble_Configure_JSearch v1.0**
Last updated: 2026-02-27
