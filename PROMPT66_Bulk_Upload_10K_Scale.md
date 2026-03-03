# PROMPT66_Bulk_Upload_10K_Scale.md

Read CLAUDE.md, ARCHITECTURE.md, and tasks/lessons.md before making changes.

## Purpose

Scale the ZIP resume bulk upload system from 1,000 to 10,000 files without degrading system-wide performance. Add a system-wide import queue with progress indicators, queue position, and estimated start/finish times. Only 1 large ZIP import processes at a time; others wait in queue with full visibility.

---

## Triggers — When to Use This Prompt

- You are ready to support agency-tier recruiters uploading 10,000-resume ZIP archives.
- The custom domain cutover (PROMPT64) is complete and the system is live on winnowcc.ai.

---

## Prerequisites

- PROMPT64 (Custom Domain Cutover) is complete — `api.winnowcc.ai` and `winnowcc.ai` are live with active SSL.

---

## Background — The 6 Problems at 10,000 Scale

1. **Hard cap**: `MAX_ZIP_FILES = 1000` in `services/api/app/services/batch_upload.py` line 34 blocks uploads >1,000 files.
2. **ZIP extraction OOM**: `zf.extractall()` dumps all 10K files to disk + reads each into memory. Worker has 1GB RAM, 10K files × 200KB avg = 2GB → crash.
3. **Giant DB transaction**: 10,000 `UploadBatchFile` INSERT + flush in one transaction during staging. Holds a long lock, risks timeout.
4. **Queue starvation**: 10K parse jobs + 10K LLM reparse jobs = 20K jobs on "bulk" queue, delaying all other users' work.
5. **O(N²) finalize**: `_finalize_batch()` runs a `COUNT(*)` aggregate across all batch files after every file completes. 10K calls × 10K rows each = 100M row reads.
6. **Polling returns all rows**: Status endpoint returns all 10K `UploadBatchFile` rows every 2 seconds (~2MB JSON per poll).
7. **No system-wide concurrency limit**: Multiple large imports can stampede the workers.

---

## Implementation Steps

### Step 1: Atomic Batch Counter Increments (biggest perf win)

**File:** `services/api/app/services/batch_upload.py` — `_finalize_batch()` (lines 775-810)

**What to do:**
1. Replace the `COUNT(*)` aggregate query with an atomic `UPDATE ... SET files_completed = files_completed + 1 RETURNING total_files, files_completed, files_succeeded, files_failed`.
2. Add a `file_status: str` parameter to `_finalize_batch()` so it knows which counter to increment (`"succeeded"`, `"failed"`, or `"skipped"`).
3. Update all call sites to pass the file's final status:
   - Line 349: `_finalize_batch(session, batch_id, "failed")`
   - Line 544: `_finalize_batch(session, batch_id, "succeeded")`
   - Line 567: `_finalize_batch(session, batch_id, "failed")`
   - Line 626: `_finalize_batch(session, batch_id, "failed")` (in `process_batch_job_document`)
   - Line 666: `_finalize_batch(session, batch_id, "failed")` (in `process_batch_job_document`)
4. When `files_completed >= total_files`, mark batch as `"completed"`, set `completed_at`, and send the ZIP completion email.
5. Add a safety-net `reconcile_stale_batches()` function that corrects counters for any batch stuck in `"processing"` for >2 hours (runs a `COUNT(*)` only for those stale batches). Wire into `services/api/app/scheduler.py`.

**Why:** Each finalize call becomes O(1) instead of O(N). Saves 100M row reads for a 10K-file batch.

---

### Step 2: Streaming ZIP Extraction + Chunked DB Commits

**File:** `services/api/app/services/batch_upload.py` — `create_upload_batch_from_zip()` (lines 148-261)

**What to do:**
1. Replace `zf.extractall(extract_dir)` + `_collect_resume_files()` + file loop with:
   - `zf.infolist()` to enumerate entries (names only, no extraction)
   - Filter for `.pdf`/`.docx`, skip hidden files and `__MACOSX`, skip files > `MAX_FILE_SIZE`
   - Sort by filename
   - Validate count against `MAX_ZIP_FILES`
2. Stream files one at a time: `contents = zf.read(info.filename)` → hash → upload to GCS → create `UploadBatchFile` row → `del contents`
3. Commit DB rows every 500 files: `if (idx + 1) % 500 == 0: session.commit()`
4. Remove the temp directory creation (`tempfile.mkdtemp`) and cleanup — only the single ZIP temp file is needed.
5. Keep `_collect_resume_files()` for any other callers but it's no longer used in the ZIP path.

**Why:** Peak memory drops from ~2GB to ~200KB. No temp directory needed. Transactions stay small (~500 rows each).

---

### Step 3: Raise Hard Cap

**File:** `services/api/app/services/batch_upload.py` — line 34

**What to do:** Change `MAX_ZIP_FILES = 1000` to `MAX_ZIP_FILES = 10_000`.

---

### Step 4: Move LLM Reparse to "low" Queue

**File:** `services/api/app/services/batch_upload.py` — line 501

**What to do:** Change `get_queue("bulk").enqueue(recruiter_llm_reparse_job, ...)` to `get_queue("low").enqueue(recruiter_llm_reparse_job, ...)`.

**Why:** The initial regex parse (fast, on "bulk") gives usable candidate profiles immediately. The LLM enrichment (2-5s API call each) is background work users don't see or wait for. Moving it to "low" cuts "bulk" queue depth in half (10K jobs instead of 20K).

---

### Step 5: System-Wide Import Gate with Queue Position and Time Estimates

Only 1 large ZIP import (>1,000 files) processes at a time system-wide. Others wait in a FIFO queue with full visibility.

#### 5a. Add "queued" status to MigrationJob

**File:** `services/api/app/models/migration.py`

Add a `queued_at` column (`DateTime(timezone=True)`, nullable). Valid status progression becomes: `pending → queued → importing → completed/failed`.

**Migration:** Create a new Alembic revision to add the `queued_at` column to the `migration_jobs` table.

#### 5b. System-wide gate in migration start endpoint

**File:** `services/api/app/routers/recruiter_migration.py` — `POST /api/recruiter/migration/{job_id}/start` (lines 168-239)

When starting a `resume_archive` migration:
1. Query for any active large import:
   - `MigrationJob` with `status="importing"` and `source_platform="resume_archive"`
   - OR `UploadBatch` with `batch_type` containing `"zip"` and `status` in `("pending", "processing")`
2. **If one is active:** set this job's `status = "queued"` and `queued_at = datetime.now(UTC)`. Do NOT enqueue the RQ job. Return response with queue position and time estimates (from `get_import_queue_info()`).
3. **If none active:** proceed as today — enqueue `expand_zip_batch_job`, set `status = "importing"`.

#### 5c. Calculate queue position and time estimates

**File:** `services/api/app/services/batch_upload.py` — new function

```python
def get_import_queue_info(session, migration_job_id: int) -> dict:
    """Calculate queue position and estimated start/finish times.

    Returns:
        queue_position: 0 = currently processing, 1 = next, etc.
        estimated_start_utc: ISO string (null if already processing)
        estimated_finish_utc: ISO string
        active_batch_progress: dict with total/completed (null if no active batch)
    """
    PROCESSING_RATE = 960  # files/hour (8 workers × 2 per minute)

    # 1. Find the active import (if any) and its UploadBatch
    # 2. Count queued jobs ahead of this one (ordered by queued_at)
    # 3. For the active batch: remaining = total_files - files_completed
    #    hours_left = remaining / PROCESSING_RATE
    # 4. For each queued job ahead: estimate its total_files from the ZIP metadata
    #    (stored in MigrationJob.config_json during upload detection)
    # 5. Sum up wait time → estimated_start_utc
    # 6. estimated_finish_utc = estimated_start_utc + (my_total_files / PROCESSING_RATE)
```

The rate constant (960 files/hour) is a reasonable estimate based on 8 workers at ~30s per file. It doesn't need to be exact — users just want a ballpark.

#### 5d. Auto-start queued jobs when slot opens

**File:** `services/api/app/scheduler.py`

Add a new scheduled job running every 2 minutes:
1. Check if there's an active large import (`MigrationJob` with `status="importing"` and `source_platform="resume_archive"`)
2. If no active import, find the oldest `MigrationJob` with `status="queued"`
3. Enqueue its `expand_zip_batch_job` and set `status = "importing"`, `started_at = now()`

**Also:** In `_finalize_batch()` in `batch_upload.py`, when a ZIP batch completes, call the same auto-start logic. This gives faster turnaround than waiting for the next 2-minute scheduler tick.

#### 5e. Migration status endpoint with queue info

**File:** `services/api/app/routers/recruiter_migration.py`

Add or update `GET /api/recruiter/migration/{job_id}/status`:

```python
# Response includes:
{
    "status": "queued",           # queued | importing | completed | failed
    "queue_position": 2,          # 0 = currently processing
    "estimated_start_utc": "2026-03-15T14:30:00Z",
    "estimated_finish_utc": "2026-03-16T01:00:00Z",
    "progress": {                 # null if queued (no UploadBatch yet)
        "total_files": 10000,
        "files_completed": 3450,
        "files_succeeded": 3398,
        "files_failed": 52
    }
}
```

---

### Step 6: Summary-Only Polling with Pagination

**File:** `services/api/app/routers/upload_batches.py` (lines 21-74)

**What to do:**
1. Add query params: `include_files: bool = Query(False)`, `page: int = Query(1, ge=1)`, `page_size: int = Query(100, ge=1, le=500)`
2. During processing (`batch.status != "completed"` and `include_files == False`): return only the batch summary counters. `files` list is empty.
3. On completion or when `include_files=true`: load `UploadBatchFile` rows with `.offset((page-1)*page_size).limit(page_size)` and return paginated results.

**File:** `services/api/app/schemas/upload_batch.py`

Add optional fields to `UploadBatchStatusResponse`:
- `page: int | None = None`
- `total_pages: int | None = None`
- `queue_position: int | None = None`
- `estimated_start_utc: str | None = None`
- `estimated_finish_utc: str | None = None`

---

### Step 7: Frontend — Progress, Queue Position, Time Estimates, Pagination

**File:** `apps/web/app/recruiter/candidates/upload/page.tsx`

#### Queued state (status = "queued"):
- Display: "Your import is **#2** in queue"
- Display: "Estimated start: **~2:30 PM**" and "Estimated finish: **~1:00 AM**"
- Poll the migration status endpoint every 10 seconds

#### Processing state (status = "importing" / "processing"):
- Progress bar: "Processing **3,450** of **10,000** files... **34%**"
- Display: "Estimated finish: **~1:00 AM**"
- Show succeeded/failed counters below progress bar
- Poll every 5 seconds (summary-only, no per-file rows)

#### Completed state (status = "completed"):
- Final summary: "**10,000 files processed** — 9,847 succeeded, 153 failed"
- Fetch first page of results: `?include_files=true&page=1&page_size=100`
- "Load More" button for subsequent pages
- Stop polling

---

## Files Modified

| File | Changes |
|------|---------|
| `services/api/app/services/batch_upload.py` | Steps 1-4: atomic finalize, streaming ZIP, raise cap, queue split. Step 5c: `get_import_queue_info()`. Step 5d: trigger next queued job on batch completion. |
| `services/api/app/routers/upload_batches.py` | Step 6: summary-only polling + pagination |
| `services/api/app/schemas/upload_batch.py` | Steps 5-6: add queue/estimate/pagination fields |
| `services/api/app/routers/recruiter_migration.py` | Step 5b: system-wide gate. Step 5e: migration status endpoint with queue info. |
| `services/api/app/models/migration.py` | Step 5a: add `queued_at` column |
| `services/api/app/scheduler.py` | Step 5d: auto-start queued imports every 2 min. Step 1: reconcile stale batches. |
| `apps/web/app/recruiter/candidates/upload/page.tsx` | Step 7: queue position, time estimates, progress bar, paginated results |
| New Alembic migration | Add `queued_at` column to `migration_jobs` table |

## What Does NOT Change

- Worker count/config (8 max instances, 1GB RAM, 2 CPU — sufficient with streaming fix)
- Queue structure (still 4 queues: critical > default > bulk > low)
- DB pool size (2+3 per worker — fine for serial job processing)
- Cloud Run deployment config
- The HTTP multi-file upload path (`create_upload_batch`) — only the ZIP path changes
- Small batches (<1,000 files) — no system-wide gate, work exactly as today

## Capacity After These Changes

| Metric | Value |
|--------|-------|
| Max files per ZIP | 10,000 |
| Concurrent large imports | 1 system-wide (others queued) |
| Processing rate | ~960 files/hour (8 workers × ~30s each) |
| Time for 10K batch | ~10-11 hours |
| Peak memory (ZIP expansion) | ~200KB (one file at a time) |
| Daily throughput (bulk only) | ~16,000 files (reserving 30% for normal ops) |
| Safe recommendation | 1-2 large imports per day |

## Verification

1. Unit test streaming ZIP extraction with mock ZIP (50 files) — verify chunked commits, correct row counts
2. Unit test atomic `_finalize_batch` — verify increment, completion detection, email trigger
3. Unit test system-wide gate — verify "queued" status when another import is active, auto-start when slot opens
4. Unit test status endpoint — verify summary-only mode, pagination, queue info fields
5. Unit test time estimates — verify calculation against known batch progress
6. Manual test: upload ZIP with ~100 resumes through migration flow, confirm progress bar, time estimates, paginated results
7. Verify existing tests still pass (HTTP upload path is unchanged)

## Checklist

- [ ] Step 1: `_finalize_batch()` uses atomic counter increment
- [ ] Step 1: `reconcile_stale_batches()` added to scheduler
- [ ] Step 2: `create_upload_batch_from_zip()` streams from ZIP, no extractall
- [ ] Step 2: DB commits chunked every 500 rows
- [ ] Step 3: `MAX_ZIP_FILES = 10_000`
- [ ] Step 4: LLM reparse enqueued on "low" queue
- [ ] Step 5a: `queued_at` column added to `migration_jobs` via Alembic
- [ ] Step 5b: System-wide gate in migration start endpoint
- [ ] Step 5c: `get_import_queue_info()` calculates position and time estimates
- [ ] Step 5d: Scheduler auto-starts queued imports every 2 min
- [ ] Step 5d: `_finalize_batch()` triggers next queued import on ZIP batch completion
- [ ] Step 5e: Migration status endpoint returns queue info
- [ ] Step 6: Status endpoint supports summary-only mode and pagination
- [ ] Step 6: Schema updated with queue/pagination fields
- [ ] Step 7: Frontend shows queue position and estimated times
- [ ] Step 7: Frontend progress bar during processing
- [ ] Step 7: Frontend paginates completed results with "Load More"
- [ ] All existing tests pass
- [ ] Manual end-to-end test with ~100 resume ZIP
