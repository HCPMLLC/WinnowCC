# PROMPT77: Unified Job Parser — Consolidate All Parsing Into One Service

Read CLAUDE.md, AGENTS.md, ARCHITECTURE.md, PROMPT10_Job_Parser.md, PROMPT14_Enhance_Parsers.md (Track B only), and PROMPT43_Job_Uploader.md before making changes.

---

## Purpose

Consolidate three overlapping job-parsing PROMPTs into **one unified parser service** so that every entry point — web upload, email ingest, and the automated ingestion pipeline — uses the same recruiter-grade extraction, fraud detection, and quality scoring.

**The problem today:** Three different PROMPTs each define their own job parsing logic:

| PROMPT | What it parses | Parser it creates | Intelligence level |
|--------|---------------|-------------------|-------------------|
| **PROMPT10** (design spec) | Ingested jobs from APIs/feeds | Conceptual — no actual file | Senior-recruiter-grade: title normalization, seniority detection, compensation inference, skills required vs. preferred, fraud signals, 4-layer dedup |
| **PROMPT14** Track B (implementation) | Ingested jobs from APIs/feeds | `services/api/app/services/job_parser.py` + `job_fraud_detector.py` | Implements PROMPT10: full `job_parsed_details` table, `JobParserService` class, `JobFraudDetector`, 6-dimension match scoring |
| **PROMPT43** (implementation) | Employer `.docx` uploads via web UI | `services/api/app/services/job_parser.py` | Basic: Claude prompt → JSON, simple category mapping, post-processing. No fraud detection, no quality scoring, no dedup |

If both PROMPT14 and PROMPT43 were executed in Cursor at different times, you may have **conflicting code** in the same file (`job_parser.py`) — or PROMPT43's simpler version may have overwritten PROMPT14's richer version (or vice versa).

**The solution:** This prompt creates a single unified service architecture where:

1. **One parser engine** handles all three input types (`.docx` files, `.pdf` files, and raw text from API feeds).
2. **One fraud/quality scorer** runs on every job regardless of source.
3. **Three entry points** (web upload, email ingest, ingestion pipeline) all call the same parser.
4. **Source tracking** records where each job came from (`web_upload`, `email_upload`, `api_feed`).

---

## Triggers — When to Use This Prompt

- You've implemented PROMPT14 and/or PROMPT43 and want to make sure they aren't conflicting.
- You're about to implement email-based job ingestion and want one parser for all entry points.
- You notice inconsistent parsing quality between uploaded jobs and ingested jobs.
- Product asks for "unified parsing" or "why do uploaded jobs parse differently?"

---

## What Already Exists (Cursor MUST read these files first)

Before making ANY changes, read the following files and understand what's currently implemented:

1. `services/api/app/services/job_parser.py` — **Read this first.** Determine which version exists: the simple PROMPT43 version (function `parse_job_document()`) or the richer PROMPT14 version (class `JobParserService`), or both, or neither.
2. `services/api/app/services/job_fraud_detector.py` — May or may not exist. If it does, PROMPT14 Track B was at least partially implemented.
3. `services/api/app/models/job_parsed_details.py` — May or may not exist. If it does, the enriched parsed data table is already in place.
4. `services/api/app/models/employer_job.py` — The employer job model with fields from PROMPT43 (parsed_from_document, parsing_confidence, source_document_url, etc.).
5. `services/api/app/routers/employer_jobs.py` — Contains `POST /api/employer/jobs/upload-document`.
6. `services/api/app/services/job_ingestion.py` or `job_pipeline.py` — The automated job ingestion pipeline.
7. `services/api/app/main.py` — Check which routers are registered.

---

## Implementation Steps

### PART 1: ASSESS CURRENT STATE

**Step 1: Read the Codebase**

Before writing any code, Cursor must determine the current state by reading the files listed above. Based on what exists, follow the appropriate path:

**Path A — Only PROMPT43 exists (simple `parse_job_document()` function):**
The file has a standalone function that extracts text from `.docx`, sends it to Claude, and returns basic JSON. Follow all steps below to upgrade it.

**Path B — Only PROMPT14 exists (class `JobParserService` + `JobFraudDetector`):**
The file has a full class-based parser with title normalization, fraud detection, and quality scoring — but it only handles raw text from API feeds, not `.docx`/`.pdf` file uploads. Follow Steps 3–6 to add file-handling entry points.

**Path C — Both exist and conflict:**
There may be duplicate function names or two different approaches in the same file. Follow all steps below, keeping PROMPT14's richer logic as the base and adding PROMPT43's file-handling capability on top.

**Path D — Neither exists yet:**
Follow all steps below from scratch.

---

### PART 2: UNIFIED PARSER SERVICE

**Step 2: Create (or replace) the Unified Parser**

**File:** `services/api/app/services/job_parser.py`

**What this file must contain after this step:**

The unified parser must have these public entry points:

```python
# ── Entry Point 1: Parse a file (for web upload + email upload) ──────────
async def parse_job_from_file(
    file_path: str,
    source: str = "web_upload",  # or "email_upload"
    employer_id: str = None,
    user_id: str = None,
) -> dict:
    """
    Parse a .docx or .pdf job description file into structured data.
    
    Steps:
      1. Detect file type (.docx vs .pdf)
      2. Extract raw text from the file
      3. Send text through the unified Claude parsing prompt
      4. Post-process and validate extracted fields
      5. Run fraud/quality scoring
      6. Return structured result with confidence score
    
    Used by:
      - Employer web upload (POST /api/employer/jobs/upload-document)
      - Recruiter email ingest (email_ingest.py)
    """


# ── Entry Point 2: Parse raw text (for ingestion pipeline) ───────────────
async def parse_job_from_text(
    raw_text: str,
    source: str = "api_feed",
    source_url: str = None,
    company_name: str = None,
) -> dict:
    """
    Parse raw job description text (already extracted from an API feed).
    
    Steps:
      1. Send text through the unified Claude parsing prompt
      2. Post-process and validate extracted fields
      3. Run fraud/quality scoring
      4. Return structured result with confidence score
    
    Used by:
      - Job ingestion pipeline (job_ingestion.py / job_pipeline.py)
      - Admin re-parse endpoints
    """


# ── Entry Point 3: Quick confidence check (no full parse) ────────────────
def estimate_parse_confidence(raw_text: str) -> float:
    """
    Quick heuristic confidence score without calling Claude.
    Checks text length, presence of key sections, formatting quality.
    Useful for pre-filtering before committing to an API call.
    """
```

**Internal architecture (private functions):**

```python
# ── Text extraction ──────────────────────────────────────────────────────
def _extract_text_from_docx(file_path: str) -> str:
    """Extract text from .docx file, including table content."""

def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from .pdf file using pypdf."""

def _detect_file_type(file_path: str) -> str:
    """Return 'docx', 'pdf', or 'unknown' based on extension and magic bytes."""


# ── Claude parsing prompt (THE SINGLE SOURCE OF TRUTH) ───────────────────
def _parse_with_claude(text: str) -> dict:
    """
    THE unified Claude prompt. This is the ONLY place where the LLM
    extraction prompt lives. All entry points call this same function.
    
    The prompt must extract ALL of these fields (senior-recruiter-grade):
    
    Basic:
      title, normalized_title, seniority_level, department, job_category,
      job_id_external, company_name
    
    Location & Mode:
      location, city, state, country, remote_policy, travel_requirements,
      relocation_offered
    
    Employment:
      employment_type (full-time/part-time/contract/internship),
      job_type (permanent/contract/temporary/seasonal),
      duration_months (for contracts)
    
    Dates:
      start_date, close_date, posted_date
    
    Compensation:
      salary_min, salary_max, salary_currency, salary_type (annual/hourly/monthly),
      equity_offered, benefits_mentioned
    
    Requirements (THE MOST IMPORTANT SECTION):
      required_skills (list of {skill, years_needed, is_must_have}),
      preferred_skills (list of {skill, years_needed}),
      certifications_required,
      certifications_preferred,
      education_minimum (e.g., "Bachelor's in CS or equivalent"),
      years_experience_minimum,
      years_experience_preferred,
      clearance_required (for government jobs)
    
    Content:
      description, requirements_text, nice_to_haves_text,
      responsibilities_text, benefits_text
    
    Intelligence:
      application_email, application_url,
      company_industry (inferred),
      is_likely_recruiter_posting (boolean — staffing agency vs direct employer),
      posting_quality_score (0-100)
    
    Fraud signals:
      vague_language_score (0-10), excessive_urgency (boolean),
      unrealistic_salary (boolean), missing_company_details (boolean),
      suspicious_contact_info (boolean)
    """


# ── Post-processing ──────────────────────────────────────────────────────
def _post_process(parsed: dict) -> dict:
    """
    Clean and validate Claude output:
      - Normalize job_category to standard list (14 categories)
      - Normalize seniority_level to standard list
      - Expand title abbreviations (Sr. → Senior, PM → Project Manager)
      - Parse dates to ISO format
      - Validate salary ranges (min < max, reasonable for role)
      - Calculate overall confidence score (0.0 - 1.0)
    """


# ── Fraud & quality scoring ──────────────────────────────────────────────
def _score_quality_and_fraud(parsed: dict) -> dict:
    """
    Run fraud detection and quality scoring (from PROMPT10/14):
      - Vague language detection (regex patterns)
      - Missing critical fields penalty
      - Salary reasonableness check against role + location
      - Company name validation (known staffing agencies flagged)
      - Contact info red flags (gmail/yahoo for enterprise jobs)
      - Posting freshness (penalize if close_date already passed)
    
    Returns the parsed dict with added fields:
      fraud_score (0-100, lower is better),
      quality_score (0-100, higher is better),
      fraud_flags (list of string reasons),
      quality_notes (list of string reasons)
    """
```

**Key implementation rules for Cursor:**

1. **DO NOT create a second parser file.** Everything lives in `job_parser.py`.
2. **If `job_fraud_detector.py` already exists**, keep it as a separate module but import and call it from within `_score_quality_and_fraud()`. Don't duplicate the logic.
3. **The Claude prompt in `_parse_with_claude()` must be comprehensive** — it replaces both PROMPT43's basic prompt and PROMPT14's richer extraction. Use the field list above.
4. **Table extraction from `.docx`:** The PROMPT43 version only reads paragraphs. You MUST also read table content, because many job descriptions put requirements in tables. Use:
   ```python
   for table in doc.tables:
       for row in table.rows:
           row_text = " | ".join(cell.text.strip() for cell in row.cells)
           if row_text.strip():
               full_text += "\n" + row_text
   ```
5. **PDF support:** Use `pypdf` (already in the project) to extract text from PDFs. Fall back gracefully if text extraction yields nothing (scanned PDFs).
6. **Confidence score formula:**
   ```
   confidence = (
       0.25 * (1.0 if title else 0.0) +
       0.20 * (1.0 if description and len(description) > 100 else 0.5 if description else 0.0) +
       0.20 * (1.0 if required_skills and len(required_skills) > 0 else 0.0) +
       0.15 * (1.0 if location else 0.0) +
       0.10 * (1.0 if salary_min or salary_max else 0.0) +
       0.10 * (1.0 if employment_type else 0.0)
   )
   ```

---

### PART 3: UPDATE THE EMPLOYER UPLOAD ROUTER

**Step 3: Update the Web Upload Endpoint**

**File:** `services/api/app/routers/employer_jobs.py` (or wherever `POST /api/employer/jobs/upload-document` lives)

**What to change:** Replace the import of the old parser function with the new unified one:

```python
# OLD (from PROMPT43):
from app.services.job_parser import parse_job_document

# NEW (unified):
from app.services.job_parser import parse_job_from_file
```

Then update the upload handler to call `parse_job_from_file()` instead of `parse_job_document()`:

```python
# Inside the upload endpoint:
parsed_data = await parse_job_from_file(
    file_path=temp_file_path,
    source="web_upload",
    employer_id=str(current_user_employer.id),
    user_id=str(current_user.id),
)
```

The rest of the endpoint (creating the draft job, returning the response) stays the same — the return format from `parse_job_from_file()` must match what the endpoint already expects. Map any new field names in the return dict so existing frontend code doesn't break.

---

### PART 4: UPDATE THE INGESTION PIPELINE

**Step 4: Wire the Ingestion Pipeline to Use the Unified Parser**

**File:** `services/api/app/services/job_ingestion.py` or `services/api/app/services/job_pipeline.py` (whichever exists)

**What to change:** Find where jobs from API feeds are currently stored raw (or parsed with a simple approach). Add a call to the unified parser:

```python
from app.services.job_parser import parse_job_from_text

# After fetching raw job data from an API source:
enriched = await parse_job_from_text(
    raw_text=job_description_text,
    source="api_feed",
    source_url=job_source_url,
    company_name=job_company_name,
)
```

**Important:** The ingestion pipeline processes many jobs in bulk. To avoid excessive Claude API costs:

1. **Only parse NEW jobs** — skip jobs that already have a `job_parsed_details` record.
2. **Use `estimate_parse_confidence()` first** — if the raw text is too short or clearly garbage, skip the full Claude call.
3. **Batch rate limiting** — add a small delay between Claude calls (0.5s) to stay within rate limits during bulk ingestion.

---

### PART 5: SUPPORT THE EMAIL INGEST ENTRY POINT

**Step 5: Create the Email Parser Bridge**

**File:** `services/api/app/services/email_ingest.py` (from PROMPT78 / email-to-job-upload feature)

**What to change:** When email ingest exists, its `_process_single_message()` function should call:

```python
from app.services.job_parser import parse_job_from_file

parsed_data = await parse_job_from_file(
    file_path=downloaded_attachment_path,
    source="email_upload",
    employer_id=str(employer.id) if employer else None,
    user_id=str(user.id),
)
```

If email ingest hasn't been built yet, this step is just a note — when it IS built, it must import from this same unified parser.

---

### PART 6: OPTIONAL — STORE ENRICHED DATA IN `job_parsed_details`

**Step 6: Wire to `job_parsed_details` Table (If It Exists)**

If PROMPT14 Track B was implemented and the `job_parsed_details` table exists in your database, the unified parser should store its enriched output there in addition to (or instead of) the basic `employer_jobs` fields.

**File:** `services/api/app/services/job_parser.py`

Add a helper function:

```python
def store_parsed_details(job_id: str, parsed_data: dict, db: Session):
    """
    Store the full enriched parsing output in job_parsed_details.
    Called after creating or updating a job record.
    """
    from app.models.job_parsed_details import JobParsedDetails

    existing = db.query(JobParsedDetails).filter_by(job_id=job_id).first()
    if existing:
        # Update existing record
        for key, value in parsed_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
    else:
        # Create new record
        details = JobParsedDetails(job_id=job_id, **parsed_data)
        db.add(details)
    
    db.flush()
```

If the table does NOT exist, skip this step — the basic fields on `employer_jobs` (from PROMPT43) are sufficient until PROMPT14 is fully implemented.

---

### PART 7: BACKWARD COMPATIBILITY

**Step 7: Keep the Old Function Name as an Alias**

To avoid breaking anything that currently imports the old function name:

**File:** `services/api/app/services/job_parser.py`

At the bottom of the file, add:

```python
# ── Backward compatibility ───────────────────────────────────────────────
# PROMPT43 used this function name. Keep it as an alias so existing code
# that imports parse_job_document() doesn't break.
def parse_job_document(file_path: str) -> dict:
    """Legacy alias — calls the unified parser synchronously."""
    import asyncio
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If already in an async context, create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                parse_job_from_file(file_path, source="web_upload")
            )
            return future.result()
    else:
        return asyncio.run(parse_job_from_file(file_path, source="web_upload"))
```

---

### PART 8: LINT & TEST

**Step 8: Lint and Format**

```powershell
cd services/api
python -m ruff check .
python -m ruff format .
```

**Step 9: Verify**

Run the API and confirm:

```powershell
cd services/api
uvicorn app.main:app --reload
```

Check that:
- The API starts without import errors.
- `POST /api/employer/jobs/upload-document` still works (upload a `.docx`).
- The ingestion pipeline still runs (if you have jobs in your database).

---

## Complete File Summary

| # | Action | File Path |
|---|--------|-----------|
| 1 | Read first | `services/api/app/services/job_parser.py` (determine current state) |
| 2 | Read first | `services/api/app/services/job_fraud_detector.py` (if exists) |
| 3 | Read first | `services/api/app/models/job_parsed_details.py` (if exists) |
| 4 | Read first | `services/api/app/routers/employer_jobs.py` (upload endpoint) |
| 5 | Read first | `services/api/app/services/job_ingestion.py` or `job_pipeline.py` |
| 6 | **Create/Replace** | `services/api/app/services/job_parser.py` — unified parser |
| 7 | **Edit** | `services/api/app/routers/employer_jobs.py` — update import + call |
| 8 | **Edit** | `services/api/app/services/job_ingestion.py` — wire unified parser |
| 9 | **Edit** | `services/api/app/services/email_ingest.py` — wire unified parser (if exists) |
| 10 | **Optional edit** | Store enriched data in `job_parsed_details` (if table exists) |
| 11 | Terminal | `python -m ruff check . && python -m ruff format .` |
| 12 | Terminal | `uvicorn app.main:app --reload` (verify startup) |

---

## Testing Checklist

After implementation, verify:

- ✅ API starts without import errors
- ✅ `parse_job_from_file()` accepts `.docx` files and returns structured data
- ✅ `parse_job_from_file()` accepts `.pdf` files and returns structured data
- ✅ `parse_job_from_text()` accepts raw text and returns structured data
- ✅ All three entry points return the SAME field structure
- ✅ Confidence score is calculated and included in output
- ✅ Fraud/quality scoring runs on every parse (check for `fraud_score` and `quality_score` in output)
- ✅ Table content from `.docx` files is extracted (not just paragraphs)
- ✅ The old function name `parse_job_document()` still works (backward compat alias)
- ✅ Employer web upload endpoint (`POST /api/employer/jobs/upload-document`) still creates draft jobs
- ✅ Ingestion pipeline uses the unified parser (if wired)
- ✅ No duplicate parser logic exists across multiple files

---

## Success Criteria

- ✅ **One parser to rule them all:** `services/api/app/services/job_parser.py` is the single source of truth for all job parsing
- ✅ **One Claude prompt:** The LLM extraction prompt lives in exactly one place (`_parse_with_claude()`)
- ✅ **Three entry points:** `parse_job_from_file()`, `parse_job_from_text()`, and legacy `parse_job_document()`
- ✅ **Consistent quality:** A job uploaded via email parses identically to one uploaded via the web UI or ingested from an API
- ✅ **Fraud/quality scoring on every job:** No job enters the system without a quality assessment
- ✅ **No breaking changes:** Existing endpoints and frontend code continue to work

---

## Relationship to Other PROMPTs

| PROMPT | Status After This | Notes |
|--------|-------------------|-------|
| PROMPT10 | **Superseded** (design only) | Its extraction specs are now built into `_parse_with_claude()` |
| PROMPT14 Track B | **Merged** | Its `JobParserService` logic is now in the unified `job_parser.py`. If `job_fraud_detector.py` exists, it's imported and used — not duplicated |
| PROMPT43 | **Merged** | Its `parse_job_document()` is now a backward-compat alias for `parse_job_from_file()`. Its upload router still works |
| PROMPT45 (Forms Handler) | **Unaffected** | Form parsing is a separate concern (parses forms, not job descriptions) |
| Email Ingest (future) | **Ready** | Will call `parse_job_from_file()` when implemented |

---

## Notes

- **Cost:** Each Claude parse call costs ~$0.001–$0.003 depending on document length. At 100 jobs/day = ~$0.30/day.
- **Latency:** Claude parsing takes 2–5 seconds. Acceptable for single uploads (web/email). For bulk ingestion, run async in the worker queue.
- **Model:** Use `claude-sonnet-4-20250514` for the best balance of quality and speed. Do NOT use Opus for parsing — it's slower and more expensive for structured extraction.
- **Fallback:** If Claude API is down, `parse_job_from_file()` should still extract basic fields (title from first line, raw text as description) and set `confidence = 0.1` so the job at least enters the system as a draft.

---

**Status:** Ready for implementation
**Estimated Time:** 2–3 hours (mostly refactoring, not new logic)
**Dependencies:** At least one of PROMPT14 or PROMPT43 must have been partially implemented
**Required:** Anthropic API key for Claude parsing
**Run in Cursor:**
```
Read PROMPT77_Unified_Job_Parser.md and implement all steps. Read CLAUDE.md, AGENTS.md, and ARCHITECTURE.md first. Before writing any code, read the files listed in Steps 1-5 to understand the current state of the codebase, then follow the appropriate path (A, B, C, or D) described in Step 1.
```
