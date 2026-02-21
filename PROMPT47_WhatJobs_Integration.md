# PROMPT46_WhatJobs_Integration.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, PROMPT28_Seed_Job_Data.md, and the existing job source adapters before making changes.

## Purpose

Add WhatJobs (whatjobs.com) as a new job ingestion source for Winnow. WhatJobs is a job search engine and aggregator with an affiliate API that provides access to 1.5M+ US job listings via a REST API returning JSON or XML. This expands Winnow's job pool significantly beyond the existing Remotive, The Muse, Greenhouse, Lever, and Jooble sources.

This prompt covers: obtaining and configuring the API key, building the WhatJobs source adapter, registering it in the source registry, wiring it into the seed script and ingestion pipeline, and testing the integration end-to-end.

---

## Triggers — When to Use This Prompt

- Adding WhatJobs as a new job data source.
- Expanding Winnow's job pool with a new aggregator.
- Implementing new job source adapters following the existing pattern.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Job source adapters directory:** `services/api/app/services/job_sources/` — contains existing adapters (e.g., `remotive.py`, `themuse.py`, `greenhouse.py`, `lever.py`, `jooble.py`). Each adapter implements a `fetch_jobs()` method that returns a list of normalized job dicts.
2. **Source registry:** There is a registry or mapping (check `job_sources/__init__.py` or the ingestion service) that maps source names like `"remotive"`, `"themuse"` to their adapter classes/functions. New sources must be registered here.
3. **Job model:** `services/api/app/models/job.py` — stores jobs with `source`, `source_job_id`, `url`, `title`, `company`, `location`, `remote_flag`, `salary_min`, `salary_max`, `currency`, `description_text`, `embedding`, `posted_at`, `ingested_at`, `content_hash`.
4. **Ingestion pipeline:** Existing pipeline computes `content_hash` (SHA-256 of title + company + location + description) for deduplication, inserts new jobs, then enqueues `parse_job_posting` and `generate_embedding` worker jobs.
5. **Seed script:** `services/api/scripts/seed_jobs.py` — bulk ingestion script with category-based fetching, dedup, logging.
6. **Admin ingestion endpoint:** `POST /api/admin/ingest` — triggers ingestion via the API. Protected by `ADMIN_TOKEN`.
7. **Job fraud detector:** `services/api/app/services/job_fraud_detector.py` — checks for spam, staleness, and suspicious patterns. WhatJobs jobs should pass through this like all other sources.
8. **Environment configuration:** `services/api/.env` and `services/api/.env.example` — stores API keys and configuration for all sources.

---

## Pre-Requisite: Obtain WhatJobs API Key

Before implementing any code, you must request an API key from WhatJobs:

1. Go to: `https://www.whatjobs.com/affiliates`
2. Look for the "Publisher Program" or "FeedAPI" section.
3. Contact WhatJobs to request affiliate/publisher API access.
4. You will receive:
   - An **API key** (Bearer token)
   - Possibly a **publisher ID** or **affiliate ID**
5. Save these credentials — you will add them to your `.env` file in Part 1.

**Important:** You cannot proceed with live testing until you have a valid API key. However, you CAN build and unit-test the adapter using mocked responses before the key arrives.

---

# PART 1 — Environment Configuration

## Step 1.1 — Add WhatJobs credentials to .env.example

**File to edit:** `services/api/.env.example`

Find the section where other job source API keys are defined (look for `JOOBLE_API_KEY`, `REMOTIVE_URL`, `THE_MUSE_API_KEY`, or similar). Add these new lines nearby:

```env
# WhatJobs Affiliate API
WHATJOBS_API_KEY=your-whatjobs-api-key-here
WHATJOBS_BASE_URL=https://api.whatjobs.com/v1
```

## Step 1.2 — Add WhatJobs credentials to your local .env

**File to edit:** `services/api/.env`

Add the same two lines, replacing `your-whatjobs-api-key-here` with your actual API key once you receive it:

```env
# WhatJobs Affiliate API
WHATJOBS_API_KEY=your-actual-key
WHATJOBS_BASE_URL=https://api.whatjobs.com/v1
```

## Step 1.3 — Add WhatJobs to the JOB_SOURCES list

In the same `.env` file, find the `JOB_SOURCES` variable (or wherever active sources are listed). Add `whatjobs` to the comma-separated list:

```env
# Before:
JOB_SOURCES=remotive,themuse,jooble,greenhouse,lever

# After:
JOB_SOURCES=remotive,themuse,jooble,greenhouse,lever,whatjobs
```

---

# PART 2 — Build the WhatJobs Source Adapter

## Step 2.1 — Create the adapter file

**File to create:** `services/api/app/services/job_sources/whatjobs.py`

```python
"""
WhatJobs affiliate API adapter.

Fetches job listings from WhatJobs' REST API.
API docs: https://www.whatjobs.com/affiliates (FeedAPI section)
Public API reference: https://publicapi.dev/what-jobs-api

Authentication: Bearer token via Authorization header.
Rate limit: 1,000 requests per hour.
Response format: JSON.

Environment variables required:
  - WHATJOBS_API_KEY: Bearer token from WhatJobs affiliate program
  - WHATJOBS_BASE_URL: API base URL (default: https://api.whatjobs.com/v1)
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration from environment
WHATJOBS_API_KEY = os.getenv("WHATJOBS_API_KEY", "")
WHATJOBS_BASE_URL = os.getenv("WHATJOBS_BASE_URL", "https://api.whatjobs.com/v1")

# Rate limit: 1,000 requests/hour. We use conservative page sizes to stay well under.
DEFAULT_MAX_RESULTS = 50
REQUEST_TIMEOUT = 30  # seconds


def _parse_salary(salary_str: Optional[str]) -> tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Parse salary string like '50000-70000' into (min, max, currency).
    Returns (None, None, None) if unparseable.
    """
    if not salary_str:
        return None, None, None

    salary_str = salary_str.strip()
    currency = "USD"  # Default; WhatJobs is primarily US-focused

    # Handle range format: "50000-70000"
    if "-" in salary_str:
        parts = salary_str.split("-")
        try:
            salary_min = int(parts[0].strip().replace(",", "").replace("$", ""))
            salary_max = int(parts[1].strip().replace(",", "").replace("$", ""))
            return salary_min, salary_max, currency
        except (ValueError, IndexError):
            pass

    # Handle single value
    try:
        val = int(salary_str.strip().replace(",", "").replace("$", ""))
        return val, val, currency
    except ValueError:
        pass

    return None, None, None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse date string from WhatJobs API response.
    Expected formats: '2022-01-01', ISO 8601, or similar.
    Returns None if unparseable.
    """
    if not date_str:
        return None

    # Try common formats
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f"]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _infer_remote(location: str, title: str, description: str) -> bool:
    """
    Infer whether a job is remote based on location, title, and description.
    """
    text = f"{location} {title} {description[:500]}".lower()
    remote_keywords = ["remote", "work from home", "wfh", "anywhere", "distributed"]
    return any(kw in text for kw in remote_keywords)


def _normalize_job(raw_job: dict) -> dict:
    """
    Normalize a single WhatJobs API response into Winnow's Job schema.

    WhatJobs response fields (from API docs):
    {
        "title": "Software Developer",
        "company": "ABC Company",
        "location": "New York",
        "description": "Lorem ipsum...",
        "salary": "50000-70000",
        "datePosted": "2022-01-01",
        "requirements": "Bachelor's degree...",  (optional, in detail endpoint)
        "responsibilities": "Developing..."      (optional, in detail endpoint)
    }
    """
    title = raw_job.get("title", "").strip()
    company = raw_job.get("company", "").strip()
    location = raw_job.get("location", "").strip()
    description = raw_job.get("description", "").strip()
    salary_str = raw_job.get("salary")
    date_posted = raw_job.get("datePosted")

    # Append requirements/responsibilities to description if present
    requirements = raw_job.get("requirements", "")
    responsibilities = raw_job.get("responsibilities", "")
    if requirements:
        description += f"\n\nRequirements:\n{requirements}"
    if responsibilities:
        description += f"\n\nResponsibilities:\n{responsibilities}"

    salary_min, salary_max, currency = _parse_salary(salary_str)
    posted_at = _parse_date(date_posted)
    remote_ok = _infer_remote(location, title, description)

    # Build a source_job_id from available data
    # WhatJobs may return an 'id' field; fall back to hash of title+company+location
    source_job_id = raw_job.get("id") or raw_job.get("job_id")
    if not source_job_id:
        import hashlib
        source_job_id = hashlib.sha256(
            f"{title}|{company}|{location}".encode()
        ).hexdigest()[:16]

    # Build application URL
    url = raw_job.get("url") or raw_job.get("application_url") or raw_job.get("link", "")

    return {
        "source": "whatjobs",
        "source_job_id": str(source_job_id),
        "url": url,
        "title": title,
        "company": company,
        "location": location,
        "remote_flag": remote_ok,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "description_text": description,
        "posted_at": posted_at,
        "ingested_at": datetime.now(timezone.utc),
    }


async def fetch_jobs(
    query: str = "",
    location: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
    **kwargs,
) -> list[dict]:
    """
    Fetch jobs from WhatJobs API.

    Args:
        query: Job search query (e.g., 'software developer', 'project manager')
        location: Location filter (e.g., 'New York', 'Remote')
        max_results: Maximum number of jobs to fetch (default: 50)
        **kwargs: Additional API parameters

    Returns:
        List of normalized job dicts matching Winnow's Job schema.
    """
    if not WHATJOBS_API_KEY:
        logger.warning("WHATJOBS_API_KEY not set — skipping WhatJobs ingestion")
        return []

    jobs = []
    params = {}

    # Build query parameters
    if query:
        params["search"] = query
    if location:
        params["location"] = location
    if max_results:
        params["limit"] = min(max_results, 100)  # API may have its own max

    # Add any extra params
    for key, value in kwargs.items():
        if key not in ("query", "location", "max_results"):
            params[key] = value

    url = f"{WHATJOBS_BASE_URL}/jobs"

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            logger.info(f"WhatJobs: fetching jobs — query='{query}', location='{location}', limit={max_results}")

            response = await client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {WHATJOBS_API_KEY}",
                    "Accept": "application/json",
                },
            )

            if response.status_code == 429:
                logger.warning("WhatJobs: rate limit hit (429). Try again later.")
                return []

            if response.status_code == 401:
                logger.error("WhatJobs: authentication failed (401). Check WHATJOBS_API_KEY.")
                return []

            if response.status_code == 403:
                logger.error("WhatJobs: access forbidden (403). Verify affiliate account status.")
                return []

            response.raise_for_status()

            data = response.json()

            # WhatJobs may return jobs in different structures:
            # {"jobListings": [...]} or {"jobs": [...]} or just [...]
            raw_jobs = []
            if isinstance(data, list):
                raw_jobs = data
            elif isinstance(data, dict):
                raw_jobs = (
                    data.get("jobListings")
                    or data.get("jobs")
                    or data.get("results")
                    or data.get("data")
                    or []
                )

            logger.info(f"WhatJobs: received {len(raw_jobs)} raw jobs")

            for raw_job in raw_jobs[:max_results]:
                try:
                    normalized = _normalize_job(raw_job)
                    # Skip jobs with missing critical fields
                    if not normalized["title"] or not normalized["company"]:
                        logger.debug(f"WhatJobs: skipping job with missing title/company: {raw_job}")
                        continue
                    jobs.append(normalized)
                except Exception as e:
                    logger.warning(f"WhatJobs: failed to normalize job: {e}")
                    continue

            logger.info(f"WhatJobs: normalized {len(jobs)} jobs (from {len(raw_jobs)} raw)")

    except httpx.TimeoutException:
        logger.error(f"WhatJobs: request timed out after {REQUEST_TIMEOUT}s")
    except httpx.HTTPStatusError as e:
        logger.error(f"WhatJobs: HTTP error {e.response.status_code}: {e}")
    except Exception as e:
        logger.error(f"WhatJobs: unexpected error: {e}")

    return jobs


# Synchronous wrapper for compatibility with existing adapters that use sync calls
def fetch_jobs_sync(
    query: str = "",
    location: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
    **kwargs,
) -> list[dict]:
    """
    Synchronous wrapper around fetch_jobs() for adapters that don't use async.
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(
                    asyncio.run,
                    fetch_jobs(query=query, location=location, max_results=max_results, **kwargs)
                ).result()
        else:
            return loop.run_until_complete(
                fetch_jobs(query=query, location=location, max_results=max_results, **kwargs)
            )
    except RuntimeError:
        return asyncio.run(
            fetch_jobs(query=query, location=location, max_results=max_results, **kwargs)
        )
```

---

# PART 3 — Register WhatJobs in the Source Registry

## Step 3.1 — Find the source registry

Open the job sources directory in Cursor:

```
services/api/app/services/job_sources/
```

Look at `__init__.py` (or wherever existing sources are registered). It will have a pattern like one of these:

**Pattern A — Dict mapping:**
```python
SOURCE_ADAPTERS = {
    "remotive": remotive.fetch_jobs,
    "themuse": themuse.fetch_jobs,
    "jooble": jooble.fetch_jobs,
    "greenhouse": greenhouse.fetch_jobs,
    "lever": lever.fetch_jobs,
}
```

**Pattern B — Class registry:**
```python
SOURCES = {
    "remotive": RemotiveAdapter,
    "themuse": TheMuseAdapter,
    ...
}
```

**Pattern C — Import-based with if/elif:**
```python
if source == "remotive":
    from .remotive import fetch_jobs
elif source == "themuse":
    from .themuse import fetch_jobs
...
```

## Step 3.2 — Add WhatJobs to the registry

Whichever pattern you find, add the WhatJobs adapter.

**If Pattern A:**

Add this import at the top of the file:
```python
from . import whatjobs
```

Add this entry to the dict:
```python
"whatjobs": whatjobs.fetch_jobs,
```

**If Pattern B:**

Import and add:
```python
from .whatjobs import fetch_jobs as whatjobs_fetch
# ... then add to SOURCES dict:
"whatjobs": whatjobs_fetch,
```

**If Pattern C:**

Add a new elif:
```python
elif source == "whatjobs":
    from .whatjobs import fetch_jobs
```

---

# PART 4 — Wire WhatJobs into the Seed Script

## Step 4.1 — Add WhatJobs search categories

**File to edit:** `services/api/scripts/seed_jobs.py`

Find the `SEED_CATEGORIES` dict. Add `"whatjobs"` entries to the categories that are relevant. WhatJobs is a general aggregator so it covers most categories:

```python
SEED_CATEGORIES = {
    "tech": {
        "remotive": {"category": "software-dev", "limit": 50},
        "themuse": {"category": "Engineering", "level": "Senior Level,Mid Level", "page_size": 50},
        "whatjobs": {"query": "software developer", "location": "", "max_results": 50},  # ADD THIS
    },
    "project_management": {
        "remotive": {"category": "project-management", "limit": 30},
        "themuse": {"category": "Project & Program Management", "level": "Senior Level,Mid Level", "page_size": 30},
        "whatjobs": {"query": "project manager", "location": "", "max_results": 30},  # ADD THIS
    },
    "business": {
        "themuse": {"category": "Business & Strategy", "level": "Senior Level,Mid Level", "page_size": 40},
        "whatjobs": {"query": "business analyst", "location": "", "max_results": 40},  # ADD THIS
    },
    "marketing": {
        "remotive": {"category": "marketing", "limit": 30},
        "themuse": {"category": "Marketing & PR", "page_size": 30},
        "whatjobs": {"query": "marketing manager", "location": "", "max_results": 30},  # ADD THIS
    },
    "data": {
        "remotive": {"category": "data", "limit": 30},
        "themuse": {"category": "Data Science", "page_size": 30},
        "whatjobs": {"query": "data scientist", "location": "", "max_results": 30},  # ADD THIS
    },
    "design": {
        "remotive": {"category": "design", "limit": 20},
        "themuse": {"category": "Design & UX", "page_size": 20},
        "whatjobs": {"query": "UX designer", "location": "", "max_results": 20},  # ADD THIS
    },
    "finance": {
        "themuse": {"category": "Finance", "page_size": 30},
        "whatjobs": {"query": "financial analyst", "location": "", "max_results": 30},  # ADD THIS
    },
    "healthcare": {
        "themuse": {"category": "Healthcare", "page_size": 20},
        "whatjobs": {"query": "healthcare", "location": "", "max_results": 20},  # ADD THIS
    },
}
```

## Step 4.2 — Verify the seed script handles the adapter

The seed script should already loop through all sources in each category and call the corresponding adapter's `fetch_jobs()`. Since WhatJobs uses `query` and `location` as parameters (matching the adapter's function signature), it should work without additional changes.

If the seed script passes parameters by keyword, verify it unpacks the dict correctly:

```python
# This pattern should already exist:
for source_name, params in category_sources.items():
    adapter = SOURCE_ADAPTERS.get(source_name)
    if adapter:
        results = adapter(**params)  # or await adapter(**params) if async
```

If the seed script uses a different calling convention, adapt the WhatJobs params to match.

---

# PART 5 — Add Rate Limiting Protection

## Step 5.1 — Add a simple rate limiter

WhatJobs allows 1,000 requests per hour. To be safe, add a small delay between paginated requests if the adapter ever needs to paginate.

This is already handled in the adapter above (single request per `fetch_jobs()` call). However, if the seed script calls `fetch_jobs()` many times across categories in rapid succession, add a delay in the seed script:

**File to edit:** `services/api/scripts/seed_jobs.py`

Find the loop where sources are called. After each WhatJobs call, add a small sleep:

```python
import time

# After calling whatjobs adapter:
if source_name == "whatjobs":
    time.sleep(1)  # 1 second delay between WhatJobs API calls
```

This keeps you well under the 1,000/hour limit even with aggressive seeding.

---

# PART 6 — Testing

## Step 6.1 — Unit test with mocked responses

**File to create:** `services/api/tests/test_whatjobs_adapter.py`

```python
"""
Unit tests for the WhatJobs source adapter.
Tests normalization logic with mocked API responses.
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.job_sources.whatjobs import _normalize_job, _parse_salary, _parse_date, _infer_remote


class TestParseSalary:
    def test_range_format(self):
        assert _parse_salary("50000-70000") == (50000, 70000, "USD")

    def test_single_value(self):
        assert _parse_salary("60000") == (60000, 60000, "USD")

    def test_with_dollar_signs(self):
        assert _parse_salary("$50,000-$70,000") == (50000, 70000, "USD")

    def test_none(self):
        assert _parse_salary(None) == (None, None, None)

    def test_empty_string(self):
        assert _parse_salary("") == (None, None, None)

    def test_unparseable(self):
        assert _parse_salary("competitive") == (None, None, None)


class TestParseDate:
    def test_standard_date(self):
        result = _parse_date("2026-01-15")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_iso_format(self):
        result = _parse_date("2026-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2026

    def test_none(self):
        assert _parse_date(None) is None

    def test_unparseable(self):
        assert _parse_date("not-a-date") is None


class TestInferRemote:
    def test_remote_in_location(self):
        assert _infer_remote("Remote", "Developer", "Build stuff") is True

    def test_remote_in_title(self):
        assert _infer_remote("New York", "Remote Developer", "Build stuff") is True

    def test_wfh_in_description(self):
        assert _infer_remote("NYC", "Dev", "This is a work from home position") is True

    def test_not_remote(self):
        assert _infer_remote("New York, NY", "Developer", "In-office position") is False


class TestNormalizeJob:
    def test_basic_normalization(self):
        raw = {
            "title": "Software Developer",
            "company": "ABC Company",
            "location": "New York",
            "description": "Build cool things.",
            "salary": "50000-70000",
            "datePosted": "2026-01-01",
            "id": "abc123",
            "url": "https://example.com/job/abc123",
        }
        result = _normalize_job(raw)
        assert result["source"] == "whatjobs"
        assert result["source_job_id"] == "abc123"
        assert result["title"] == "Software Developer"
        assert result["company"] == "ABC Company"
        assert result["location"] == "New York"
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 70000
        assert result["currency"] == "USD"
        assert result["remote_flag"] is False
        assert result["url"] == "https://example.com/job/abc123"

    def test_remote_inference(self):
        raw = {
            "title": "Remote Software Developer",
            "company": "XYZ Corp",
            "location": "Remote",
            "description": "Work from anywhere.",
            "salary": None,
            "datePosted": None,
        }
        result = _normalize_job(raw)
        assert result["remote_flag"] is True
        assert result["salary_min"] is None

    def test_missing_id_generates_hash(self):
        raw = {
            "title": "Developer",
            "company": "Test Co",
            "location": "Austin",
            "description": "Test",
        }
        result = _normalize_job(raw)
        assert result["source_job_id"] is not None
        assert len(result["source_job_id"]) == 16  # SHA256 truncated to 16

    def test_requirements_appended_to_description(self):
        raw = {
            "title": "Dev",
            "company": "Co",
            "location": "NY",
            "description": "Base description.",
            "requirements": "BS in CS",
            "responsibilities": "Write code",
        }
        result = _normalize_job(raw)
        assert "Requirements:" in result["description_text"]
        assert "BS in CS" in result["description_text"]
        assert "Responsibilities:" in result["description_text"]
        assert "Write code" in result["description_text"]
```

## Step 6.2 — Run unit tests

```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
python -m pytest tests/test_whatjobs_adapter.py -v
```

All tests should pass. These test the normalization logic without making any real API calls.

## Step 6.3 — Integration test (requires valid API key)

Once you have your WhatJobs API key set in `.env`, test a live fetch:

```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
python -c "
import asyncio
from app.services.job_sources.whatjobs import fetch_jobs

async def test():
    jobs = await fetch_jobs(query='project manager', location='Texas', max_results=5)
    print(f'Fetched {len(jobs)} jobs')
    for j in jobs[:3]:
        print(f'  - {j[\"title\"]} at {j[\"company\"]} ({j[\"location\"]})')
        print(f'    Salary: {j[\"salary_min\"]}-{j[\"salary_max\"]} {j[\"currency\"]}')
        print(f'    Remote: {j[\"remote_flag\"]}')
        print(f'    URL: {j[\"url\"][:80]}')
        print()

asyncio.run(test())
"
```

**Expected output (if API key is valid):**
```
WhatJobs: fetching jobs — query='project manager', location='Texas', limit=5
WhatJobs: received 5 raw jobs
WhatJobs: normalized 5 jobs (from 5 raw)
Fetched 5 jobs
  - Senior Project Manager at Some Company (Dallas, TX)
    Salary: 90000-120000 USD
    Remote: False
    URL: https://...
```

**If API key is not set:**
```
WhatJobs: WHATJOBS_API_KEY not set — skipping WhatJobs ingestion
Fetched 0 jobs
```

## Step 6.4 — Test via seed script

```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
python scripts/seed_jobs.py --categories tech --dry-run
```

Verify that WhatJobs appears in the output alongside other sources:
```
INFO   Category: tech
INFO     Remotive: fetched 47 jobs, 42 new, 5 duplicates
INFO     The Muse: fetched 50 jobs, 48 new, 2 duplicates
INFO     WhatJobs: fetched 50 jobs, 49 new, 1 duplicates    <-- NEW
```

## Step 6.5 — Full ingestion test (live, not dry-run)

```powershell
cd services\api
.\.venv\Scripts\Activate.ps1
python scripts/seed_jobs.py --categories tech,project_management --max-per-source 10
```

Then verify jobs were inserted:

```powershell
python -c "
from app.db import SessionLocal
from app.models.job import Job

db = SessionLocal()
count = db.query(Job).filter(Job.source == 'whatjobs').count()
print(f'WhatJobs jobs in database: {count}')
db.close()
"
```

---

# PART 7 — API Response Adaptation

The WhatJobs API may return a slightly different JSON structure than documented in third-party API directories. The adapter in Part 2 handles multiple possible response shapes (list, dict with `jobListings`, `jobs`, `results`, or `data` keys).

If after your first live test the API returns a different structure, you will need to:

1. Add a `print(data)` or `logger.debug(f"Raw response: {data}")` line in the adapter to see the actual shape.
2. Adjust the response parsing in the `raw_jobs = ...` section of `fetch_jobs()`.
3. Adjust the field mapping in `_normalize_job()` if the job fields have different names.

**Common field name variations to watch for:**

| Winnow expects | WhatJobs might use |
|---|---|
| `title` | `title`, `jobTitle`, `job_title` |
| `company` | `company`, `companyName`, `company_name`, `employer` |
| `location` | `location`, `jobLocation`, `job_location`, `city` |
| `description` | `description`, `jobDescription`, `job_description`, `snippet` |
| `salary` | `salary`, `salaryRange`, `salary_range`, `compensation` |
| `datePosted` | `datePosted`, `date_posted`, `postedDate`, `created_at`, `publishDate` |
| `id` | `id`, `jobId`, `job_id`, `listingId` |
| `url` | `url`, `link`, `applyUrl`, `application_url`, `jobUrl` |

---

# PART 8 — Production Considerations

## Step 8.1 — Add to GCP Secret Manager

When deploying to production, add `WHATJOBS_API_KEY` to Google Cloud Secret Manager alongside your other API keys (as described in ARCHITECTURE.md §3.1):

```bash
echo -n "your-whatjobs-api-key" | gcloud secrets create WHATJOBS_API_KEY --data-file=-
```

Update your Cloud Run service to mount this secret as an environment variable.

## Step 8.2 — Add to scheduled ingestion

If you have a Cloud Scheduler cron job for periodic ingestion (as described in SPEC.md §6), WhatJobs will automatically be included as long as `"whatjobs"` is in your `JOB_SOURCES` environment variable.

## Step 8.3 — Monitor rate limits

Add a log line or metric for rate limit hits (HTTP 429). If you start hitting limits, consider:
- Reducing `max_results` per category
- Increasing the sleep delay between calls
- Caching results for a few hours before re-fetching

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Environment config | `services/api/.env.example` | MODIFY — add `WHATJOBS_API_KEY` and `WHATJOBS_BASE_URL` |
| Environment config (local) | `services/api/.env` | MODIFY — add keys, add `whatjobs` to `JOB_SOURCES` |
| WhatJobs adapter | `services/api/app/services/job_sources/whatjobs.py` | CREATE |
| Source registry | `services/api/app/services/job_sources/__init__.py` (or equivalent) | MODIFY — register `whatjobs` |
| Seed script | `services/api/scripts/seed_jobs.py` | MODIFY — add `whatjobs` entries to `SEED_CATEGORIES` |
| Unit tests | `services/api/tests/test_whatjobs_adapter.py` | CREATE |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Environment Setup (Steps 1–3)

1. **Step 1:** Add `WHATJOBS_API_KEY` and `WHATJOBS_BASE_URL` to `services/api/.env.example`.
2. **Step 2:** Add the same to your local `services/api/.env` (use a placeholder key for now).
3. **Step 3:** Add `whatjobs` to the `JOB_SOURCES` list in `services/api/.env`.

### Phase 2: Build the Adapter (Step 4)

4. **Step 4:** Create `services/api/app/services/job_sources/whatjobs.py` — copy the full implementation from Part 2.

### Phase 3: Register and Wire (Steps 5–6)

5. **Step 5:** Open `services/api/app/services/job_sources/__init__.py` (or equivalent). Import and register the `whatjobs` adapter.
6. **Step 6:** Open `services/api/scripts/seed_jobs.py`. Add `whatjobs` entries to `SEED_CATEGORIES`.

### Phase 4: Test (Steps 7–10)

7. **Step 7:** Create `services/api/tests/test_whatjobs_adapter.py` — copy from Part 6.
8. **Step 8:** Run unit tests: `python -m pytest tests/test_whatjobs_adapter.py -v`
9. **Step 9:** Once you have a valid API key, run the integration test from Part 6, Step 6.3.
10. **Step 10:** Run the seed script with `--dry-run` first, then for real: `python scripts/seed_jobs.py --categories tech --max-per-source 10`

### Phase 5: Lint + Commit (Step 11)

11. **Step 11:** Lint and format:
    ```powershell
    cd services\api
    python -m ruff check .
    python -m ruff format .
    ```
    Then commit:
    ```powershell
    git add .
    git commit -m "feat: add WhatJobs as job ingestion source (PROMPT46)"
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- WhatJobs ATS/posting API (for employers pushing jobs TO WhatJobs) — that's for the employer-side features in a future prompt.
- Scraping WhatJobs website directly — use only the official API.
- Building a dedicated WhatJobs admin UI — use existing admin ingestion endpoint.
- Pagination across multiple API pages — v1 fetches a single page per query. Pagination can be added later if the API supports it.
- Caching WhatJobs responses — not needed for v1 volume.

---

## Version

**PROMPT46_WhatJobs_Integration v1.0**
Last updated: 2026-02-13
