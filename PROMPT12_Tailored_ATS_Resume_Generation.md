# PROMPT11_Tailored_ATS_Resume_Generation.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Implement the production-grade Tailored ATS Resume Generation pipeline — Winnow's **#1 product differentiator**. When a user clicks "Generate ATS Resume" on a job match, the system produces a job-specific DOCX resume that is grounded entirely in the candidate's real experience, optimized for ATS keyword scanning, and accompanied by a transparent change log showing exactly what was modified and why.

This is the feature that separates Winnow from every competitor. It must be done right.

---

## Triggers — When to Use This Prompt

- Building or upgrading the tailored resume generation pipeline.
- Implementing SPEC §3.5 (Tailored Resume — ATS-safe).
- Implementing SPEC Flow C (Tailored Resume Generation).
- Product asks for "ATS resume," "tailored resume," "job-specific resume," or "resume optimization."
- Improving DOCX output quality, grounding, or change log.

---

## What Already Exists (DO NOT recreate — read the codebase first)

The API plumbing and database are in place. Read these files before writing any code:

1. **Tailor router:** `services/api/app/routers/tailor.py` — already registered in `main.py`. Endpoints:
   - `POST /api/tailor/{job_id}` → enqueues an RQ worker job, returns `TailorRequestResponse` with `rq_job_id`
   - `GET /api/tailor/status/{rq_job_id}` → returns `TailorStatusResponse` (status: queued / started / finished / failed, plus `tailored_resume_id` when done)
   - `GET /api/tailor/files/{tailored_id}/resume` → downloads the DOCX file
   - `GET /api/tailor/files/{tailored_id}/cover-letter` → downloads the cover letter DOCX

2. **Tailor service:** `services/api/app/services/tailor.py` — the worker function that runs when a tailor job is dequeued. **This is the file you will primarily modify.** Currently it may be a placeholder or minimal implementation.

3. **Tailored resumes model:** `services/api/app/models/tailored_resume.py` (or within the models package). The `tailored_resumes` table has columns: `id`, `user_id`, `job_id`, `profile_version`, `docx_url`, `cover_letter_url`, `change_log` (JSON), `created_at`.

4. **Candidate profile:** `services/api/app/models/candidate_profile.py` — contains `profile_json` (the full structured profile with basics, experience, education, skills, preferences) and `version`.

5. **Job model:** `services/api/app/models/job.py` — contains `title`, `company`, `description`, `requirements`, `location`, `salary_min/max`, `remote_ok`, etc.

6. **Match model:** `services/api/app/models/match.py` — contains `match_score`, `reasons` (JSON with matched_skills, missing_skills, evidence_refs, etc.), `application_status`.

7. **Queue service:** `services/api/app/services/queue.py` — RQ wrapper for enqueuing background jobs.

8. **Frontend matches page:** `apps/web/app/matches/page.tsx` — already displays match cards. The "Generate ATS Resume" button may already exist (from PROMPT5) calling `POST /api/tailor/{job_id}`.

---

## What to Build

### Part 1: The LLM Tailoring Prompt — Content Generation

**File to modify:** `services/api/app/services/tailor.py`

This is the core intelligence. The worker function must:

#### 1.1 Load all inputs

When the worker job runs, load from the database:
- The **candidate profile** (latest version for this user) — `profile_json`
- The **job posting** — full `description` + `requirements` + metadata
- The **match data** — `reasons` JSON (matched skills, missing skills, evidence refs, gaps)
- The **original resume text** — from `resume_documents` table (the raw extracted text)

#### 1.2 Build the LLM system prompt

Construct a system prompt for Claude (or other LLM) with these **non-negotiable grounding rules**:

```
GROUNDING RULES — ABSOLUTE REQUIREMENTS:
1. NEVER invent, fabricate, or hallucinate any of the following:
   - Employers, company names, or organizations the candidate did not work for
   - Job titles the candidate did not hold
   - Dates of employment not present in the candidate's profile
   - Degrees, certifications, or credentials not present in the candidate's profile
   - Tools, technologies, or skills the candidate has not claimed
   - Quantified results, metrics, or numbers not present in the original resume bullets

2. You MAY:
   - Reword existing bullets to better align with the job description's language
   - Reorder sections or bullets to prioritize the most relevant experience
   - Add a professional summary/objective tailored to this specific role
   - Emphasize skills and experience that match the job requirements
   - Use keywords from the job description where they truthfully apply to the candidate
   - Strengthen action verbs (e.g., "helped with" → "managed" IF the scope supports it)
   - Consolidate or expand bullets for clarity and impact

3. You MUST:
   - Preserve all employers, titles, dates, and education exactly as stated in the profile
   - For every modified bullet, note what changed and why in the change log
   - Flag any skills from the job description that the candidate does NOT have (keyword gaps)
   - Output the resume content as structured JSON (not DOCX — DOCX is built separately)
```

#### 1.3 Build the LLM user prompt

Send the candidate profile, job description, and match reasons. Request structured JSON output:

```json
{
  "professional_summary": "A 2-3 sentence summary tailored to this role...",
  "experience": [
    {
      "company": "Exact company from profile",
      "title": "Exact title from profile",
      "start_date": "Exact date from profile",
      "end_date": "Exact date from profile",
      "location": "Exact location from profile",
      "bullets": [
        "Reworded bullet emphasizing relevant skills..."
      ],
      "original_bullets": [
        "Original bullet text for change log comparison..."
      ]
    }
  ],
  "education": [...],
  "skills": {
    "technical": ["skill1", "skill2"],
    "certifications": ["cert1"],
    "languages": ["lang1"]
  },
  "keyword_alignment": {
    "matched_keywords": ["keyword1", "keyword2"],
    "gap_keywords": ["keyword3"],
    "added_keywords": ["keyword4"]
  },
  "change_log": [
    {
      "section": "experience",
      "company": "Acme Corp",
      "change": "Reworded bullet 2 to emphasize project management skills matching job requirement",
      "original": "Helped coordinate team projects",
      "modified": "Led cross-functional project coordination for 3 concurrent initiatives"
    }
  ]
}
```

#### 1.4 Validate the LLM output

After receiving the LLM response, **validate grounding**:
- Compare every company name, title, and date against the original profile. If any don't match, reject and retry (or strip the hallucinated content).
- Compare every education entry against the original profile.
- Compare every certification against the original profile.
- Log any validation failures for debugging.

---

### Part 2: DOCX Generation — ATS-Safe Formatting

**File to create:** `services/api/app/services/docx_builder.py` (NEW)

**Dependency:** Add `python-docx` to `services/api/requirements.txt`:
```
python-docx>=1.1.0
```

Build a DOCX file from the validated LLM output using `python-docx`. The document MUST follow these ATS-safe formatting rules (from SPEC §3.5):

#### 2.1 ATS formatting rules (non-negotiable)

- **Single column layout** — no tables for layout, no text boxes, no columns
- **Standard headings** — use Word heading styles (Heading 1, Heading 2) not just bold text
- **No tables** — ATS systems frequently misparse tables. Use plain paragraphs and lists.
- **No text boxes or shapes** — invisible to most ATS parsers
- **No icons, images, or graphics** — ATS ignores them
- **No headers/footers for critical info** — name and contact info must be in the body, not the header
- **Standard fonts** — Arial, Calibri, or Times New Roman. Size 10-12 for body, 14-16 for name.
- **Consistent date format** — "MMM YYYY – MMM YYYY" (e.g., "Jan 2020 – Present")
- **Standard section headings** — Professional Summary, Experience, Education, Skills, Certifications
- **Bullet points** — use actual Word bullet list formatting (not unicode characters)

#### 2.2 Document structure

```
[Candidate Name — large, bold, centered]
[Email | Phone | City, State | LinkedIn URL]
[blank line]

PROFESSIONAL SUMMARY
[2-3 sentence summary tailored to this job]
[blank line]

EXPERIENCE
[Company Name — bold]
[Title — italic] | [City, State] | [Start Date – End Date]
• Bullet point 1
• Bullet point 2
• Bullet point 3
[blank line between jobs]

EDUCATION
[Degree — bold] | [School Name] | [Graduation Year]
[blank line]

SKILLS
[Comma-separated skills list, grouped by category if useful]
[blank line]

CERTIFICATIONS (if any)
[Cert name — Year obtained]
```

#### 2.3 The `build_tailored_docx` function

```python
def build_tailored_docx(tailored_content: dict, output_path: str) -> str:
    """
    Build an ATS-safe DOCX from the tailored content JSON.
    
    Args:
        tailored_content: Validated JSON from LLM with resume sections
        output_path: Where to save the DOCX file
    
    Returns:
        The output_path for storage
    """
```

Use `python-docx` (`from docx import Document`) to:
1. Create a new Document
2. Set default font to Calibri 11pt
3. Set margins to 0.75 inches all around (slightly narrow for more content)
4. Add candidate name as a centered, bold, 16pt paragraph
5. Add contact info as a centered, 10pt paragraph
6. Add each section with proper heading styles
7. Add experience entries with company/title/date formatting
8. Add bullet points using actual Word list styles
9. Save to `output_path`

---

### Part 3: Cover Letter Generation

**File to modify:** `services/api/app/services/tailor.py` (same file as Part 1)

After generating the tailored resume, generate a job-specific cover letter using the same LLM:

#### 3.1 Cover letter LLM prompt

```
Generate a professional cover letter for the following candidate applying to the following job.

GROUNDING RULES:
- Only reference experience, skills, and accomplishments from the candidate's actual profile.
- Do NOT fabricate projects, metrics, or experiences.
- Address the hiring manager by name if available (from job posting).
- Reference the specific company and role by name.
- Keep to 3-4 paragraphs: opening hook, 1-2 body paragraphs with specific examples, confident closing.
- Tone: professional, confident, specific (not generic).

Output as JSON: { "greeting": "...", "body_paragraphs": ["...", "...", "..."], "closing": "...", "sign_off": "Sincerely,\n[Candidate Name]" }
```

#### 3.2 Cover letter DOCX

Create a separate DOCX file with:
- Candidate contact info at top
- Date
- Company name and address (if available)
- Greeting
- Body paragraphs
- Closing and signature
- Same ATS-safe formatting rules (Calibri, single column, no graphics)

---

### Part 4: Change Log and Keyword Alignment

**File to modify:** `services/api/app/services/tailor.py`

After generation, build and store the change log and keyword alignment summary.

#### 4.1 Change log structure

Store in `tailored_resumes.change_log` as JSON:

```json
{
  "summary": "Modified 8 bullets across 3 roles. Added professional summary. Reordered skills section.",
  "changes": [
    {
      "section": "professional_summary",
      "type": "added",
      "description": "Added job-specific professional summary highlighting project management and cloud migration experience"
    },
    {
      "section": "experience",
      "company": "Acme Corp",
      "bullet_index": 2,
      "type": "modified",
      "original": "Helped coordinate team projects",
      "modified": "Led cross-functional project coordination for 3 concurrent initiatives, improving delivery timelines by 15%",
      "reason": "Strengthened action verb and added quantification from existing bullet context to match job requirement for 'project leadership'"
    },
    {
      "section": "skills",
      "type": "reordered",
      "description": "Moved AWS, Terraform, and CI/CD to top of skills list to match job's cloud infrastructure emphasis"
    }
  ],
  "keyword_alignment": {
    "matched_keywords": ["project management", "AWS", "CI/CD", "Python", "agile"],
    "gap_keywords": ["Kubernetes", "Go"],
    "added_to_resume": ["cloud migration", "infrastructure as code"],
    "match_rate_before": 62,
    "match_rate_after": 85
  },
  "grounding_validation": {
    "employers_verified": true,
    "titles_verified": true,
    "dates_verified": true,
    "education_verified": true,
    "certifications_verified": true,
    "hallucinations_detected": 0
  }
}
```

#### 4.2 Store the change log

After the LLM generates content and the DOCX is built:
1. Construct the change log JSON from the LLM's `change_log` output + the keyword alignment data
2. Save it to `tailored_resumes.change_log` in the database
3. Also store `docx_url` (local path for dev, GCS URL for production) and `cover_letter_url`

---

### Part 5: Worker Function — Full Pipeline

**File to modify:** `services/api/app/services/tailor.py`

The complete worker function should execute this pipeline:

```python
def run_tailoring_job(user_id: int, job_id: int) -> int:
    """
    Full tailoring pipeline. Called by RQ worker.
    
    Returns: tailored_resume.id
    """
    # Step 1: Load candidate profile (latest version)
    # Step 2: Load job posting
    # Step 3: Load match data (reasons, matched/missing skills)
    # Step 4: Load original resume text
    # Step 5: Call LLM to generate tailored resume content (JSON)
    # Step 6: Validate grounding (no hallucinations)
    # Step 7: Build ATS-safe DOCX from validated content
    # Step 8: Call LLM to generate cover letter (JSON)
    # Step 9: Build cover letter DOCX
    # Step 10: Construct change log + keyword alignment
    # Step 11: Save files (local dev folder or GCS)
    # Step 12: Create/update tailored_resumes DB record
    # Step 13: Return tailored_resume.id
```

#### 5.1 LLM client

Use the Anthropic Python SDK to call Claude. Add to `services/api/requirements.txt`:
```
anthropic>=0.40.0
```

Add environment variable to `services/api/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

In the service, initialize the client:
```python
import anthropic
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
```

Use `claude-sonnet-4-20250514` for the tailoring calls (good balance of quality and speed). Set `max_tokens=4096` for the resume generation and `max_tokens=2048` for the cover letter.

#### 5.2 File storage (local dev)

For local development, store generated DOCX files in:
```
services/api/generated/tailored/{user_id}/{tailored_resume_id}/
  ├── resume.docx
  └── cover_letter.docx
```

Create the directory if it doesn't exist. Store the path in `tailored_resumes.docx_url` and `tailored_resumes.cover_letter_url`.

For production (future), these will be GCS signed URLs. The router's download endpoints already serve the files — just make sure the path resolution works.

---

### Part 6: Frontend — "What Changed" View

**File to create:** `apps/web/app/matches/[matchId]/tailored/page.tsx` (NEW)

Or modify the existing match detail / tailored resume view if one exists. This page shows the change log and download links after a tailored resume is generated.

#### 6.1 Layout

```
[Back to Matches ←]

Tailored Resume for [Job Title] at [Company]
Generated [date]

[Download Resume DOCX]  [Download Cover Letter DOCX]

─── What Changed ───────────────────────
[Summary: "Modified 8 bullets across 3 roles..."]

[Change 1 card]
  Section: Experience → Acme Corp
  Original: "Helped coordinate team projects"
  Modified: "Led cross-functional project coordination for 3 concurrent initiatives"
  Reason: "Strengthened action verb to match job requirement for 'project leadership'"

[Change 2 card]
  ...

─── Keyword Alignment ─────────────────
  Matched: project management, AWS, CI/CD, Python, agile
  Gaps: Kubernetes, Go (you don't have these — consider upskilling)
  Added: cloud migration, infrastructure as code

  Match Rate: 62% → 85%

─── Grounding Verification ─────────────
  ✅ All employers verified
  ✅ All titles verified
  ✅ All dates verified
  ✅ All education verified
  ✅ No hallucinations detected
```

#### 6.2 Data source

Fetch the tailored resume record from the API. You may need to add:
- `GET /api/tailor/{tailored_id}` → returns the `tailored_resumes` record including `change_log` JSON

If this endpoint doesn't exist yet, add it to `services/api/app/routers/tailor.py`:

```python
@router.get("/{tailored_id}", response_model=TailorDetailResponse)
async def get_tailored_resume(tailored_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    """Return the tailored resume record including change log."""
    # Query tailored_resumes by id, verify user_id matches
    # Return record with change_log, keyword_alignment, etc.
```

#### 6.3 Matches page integration

In `apps/web/app/matches/page.tsx`, for each match card:
- If a tailored resume exists for this match (check via API or include in match list response), show a "View Tailored Resume" link alongside "Generate ATS Resume."
- The "Generate ATS Resume" button should:
  1. Call `POST /api/tailor/{job_id}`
  2. Show a progress indicator (poll `GET /api/tailor/status/{rq_job_id}` every 2-3 seconds)
  3. When status is `finished`, navigate to the "What Changed" view or show download links inline

---

## Environment Variables

Add to `services/api/.env.example` and `services/api/.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

No other new environment variables required. Everything else (DB, Redis, auth) already exists.

---

## Dependencies to Add

**File to edit:** `services/api/requirements.txt`

Add these lines if not already present:
```
python-docx>=1.1.0
anthropic>=0.40.0
```

Then install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Tailor service (core logic) | `services/api/app/services/tailor.py` | MODIFY — add LLM tailoring, grounding validation, change log |
| DOCX builder | `services/api/app/services/docx_builder.py` | CREATE — ATS-safe DOCX generation with python-docx |
| Tailor router | `services/api/app/routers/tailor.py` | MODIFY — add GET /{tailored_id} detail endpoint |
| Tailor schemas | `services/api/app/schemas/tailor.py` (or within router) | MODIFY — add TailorDetailResponse with change_log |
| Tailored resume model | `services/api/app/models/tailored_resume.py` | READ — already has change_log JSON column |
| Queue service | `services/api/app/services/queue.py` | READ — already enqueues tailor jobs |
| Requirements | `services/api/requirements.txt` | MODIFY — add python-docx, anthropic |
| Environment | `services/api/.env` | MODIFY — add ANTHROPIC_API_KEY |
| Frontend: "What Changed" page | `apps/web/app/matches/[matchId]/tailored/page.tsx` | CREATE — change log + download view |
| Frontend: Matches page | `apps/web/app/matches/page.tsx` | MODIFY — add progress polling, "View Tailored Resume" link |
| Generated files directory | `services/api/generated/tailored/` | CREATE — local dev storage for DOCX files |

---

## Implementation Order (for a beginner following in Cursor)

Follow these steps in exact order:

### Step 1: Add dependencies

1. Open `services/api/requirements.txt` in Cursor.
2. Add `python-docx>=1.1.0` and `anthropic>=0.40.0` if not already present.
3. In PowerShell:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### Step 2: Add ANTHROPIC_API_KEY to .env

1. Open `services/api/.env` in Cursor.
2. Add: `ANTHROPIC_API_KEY=sk-ant-your-key-here`
3. Also add to `services/api/.env.example`: `ANTHROPIC_API_KEY=sk-ant-...`

### Step 3: Create the DOCX builder

1. Create a new file: `services/api/app/services/docx_builder.py`
2. Implement `build_tailored_docx(tailored_content: dict, output_path: str) -> str`
3. Implement `build_cover_letter_docx(cover_letter_content: dict, candidate_basics: dict, job_info: dict, output_path: str) -> str`
4. Follow the ATS formatting rules exactly (single column, standard fonts, heading styles, real bullet lists, no tables for layout).

### Step 4: Implement the LLM tailoring logic

1. Open `services/api/app/services/tailor.py` in Cursor.
2. Read the existing code carefully. Identify the worker function (likely `run_tailoring_job` or similar).
3. Add the LLM prompt construction with grounding rules (Part 1).
4. Add the Anthropic client call using `claude-sonnet-4-20250514`.
5. Add grounding validation (compare LLM output against profile).
6. Add cover letter generation (Part 3).
7. Wire in the DOCX builder (Part 2) to generate both files.
8. Construct and store the change log (Part 4).
9. Save files to `services/api/generated/tailored/{user_id}/{tailored_id}/`.
10. Update the `tailored_resumes` DB record with `docx_url`, `cover_letter_url`, and `change_log`.

### Step 5: Add the detail endpoint

1. Open `services/api/app/routers/tailor.py` in Cursor.
2. Add `GET /api/tailor/{tailored_id}` that returns the full tailored resume record including `change_log`.
3. Add a `TailorDetailResponse` schema with all fields the frontend needs.

### Step 6: Test the backend pipeline

1. Start infrastructure: `cd infra && docker compose up -d`
2. Start the API: `cd services/api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Start the worker: `cd services/api && python -m rq.cli worker --with-scheduler`
   (or however the worker is started — check `CLAUDE.md` or `start-dev.ps1`)
4. Open `http://127.0.0.1:8000/docs`
5. Log in (get a session cookie)
6. Call `POST /api/tailor/{job_id}` with a valid job_id
7. Poll `GET /api/tailor/status/{rq_job_id}` until status is `finished`
8. Call `GET /api/tailor/files/{tailored_id}/resume` — verify DOCX downloads
9. Call `GET /api/tailor/{tailored_id}` — verify change_log JSON is populated

### Step 7: Build the frontend "What Changed" page

1. Create: `apps/web/app/matches/[matchId]/tailored/page.tsx`
2. Fetch the tailored resume detail from `GET /api/tailor/{tailored_id}`
3. Render change log cards, keyword alignment, grounding verification, and download buttons
4. Style with Tailwind — clean, readable, professional

### Step 8: Update the matches page

1. Open `apps/web/app/matches/page.tsx` in Cursor.
2. Find the "Generate ATS Resume" button (or add one if missing).
3. Wire it to call `POST /api/tailor/{job_id}` and show a progress spinner.
4. Poll `GET /api/tailor/status/{rq_job_id}` every 2-3 seconds.
5. When finished, show "View Tailored Resume" link navigating to the "What Changed" page, or show download links inline.

### Step 9: Test end-to-end

1. Start all services (or use `.\start-dev.ps1`).
2. Log in at `http://localhost:3000`.
3. Go to Matches page.
4. Click "Generate ATS Resume" on any match.
5. Wait for generation to complete (should take 10-30 seconds).
6. Verify:
   - [ ] DOCX downloads and opens correctly in Word/Google Docs
   - [ ] Resume is single-column, no tables, standard headings
   - [ ] All employers, titles, dates match the original profile exactly
   - [ ] Professional summary is tailored to the specific job
   - [ ] Bullets are reworded to align with job keywords
   - [ ] Cover letter downloads and is job-specific
   - [ ] Change log shows what was modified and why
   - [ ] Keyword alignment shows matched, gap, and added keywords
   - [ ] Grounding verification shows all checks passed

### Step 10: Lint and format

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .

cd apps/web
npm run lint
```

---

## Quality Acceptance Criteria (from SPEC §11)

- [ ] Must not hallucinate facts — every employer, title, date, degree, cert verified
- [ ] Must produce ATS-safe DOCX consistently — single column, standard headings, no tables
- [ ] Change log must be generated for every tailored resume
- [ ] Keyword alignment summary must be truthful
- [ ] Resume generation should complete within 30 seconds (LLM call + DOCX build)
- [ ] Errors must be user-friendly and actionable (not raw stack traces)

---

## Non-Goals (Do NOT implement in this prompt)

- PDF output (optional future — DOCX is the required format)
- Subscription/billing limits on tailored resumes per month (future — PROMPT for Stripe)
- GCS file storage (future — local dev storage for now)
- Mobile (Expo) integration for tailored resumes (future — Month 5)
- A/B testing of different tailoring strategies
- Batch tailoring (one job at a time for now)

---

## Summary Checklist

- [ ] Dependencies: `python-docx` and `anthropic` installed
- [ ] Environment: `ANTHROPIC_API_KEY` in `.env`
- [ ] DOCX builder: `services/api/app/services/docx_builder.py` creates ATS-safe single-column DOCX
- [ ] LLM tailoring: `services/api/app/services/tailor.py` calls Claude with grounding rules, validates output
- [ ] Cover letter: generated via LLM, built as separate DOCX
- [ ] Grounding validation: every employer, title, date, education, cert verified against profile
- [ ] Change log: stored in `tailored_resumes.change_log` with per-change details + keyword alignment
- [ ] Detail endpoint: `GET /api/tailor/{tailored_id}` returns full record with change_log
- [ ] File storage: DOCX files saved to `services/api/generated/tailored/{user_id}/{id}/`
- [ ] Frontend: "What Changed" page shows change log, keyword alignment, grounding check, downloads
- [ ] Frontend: Matches page has working "Generate ATS Resume" button with progress polling
- [ ] End-to-end tested: generate → download → verify content → verify change log
- [ ] Linted and formatted

Return code changes only.
