from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobPosting:
    source: str
    source_job_id: str
    url: str
    title: str
    company: str
    location: str
    remote_flag: bool
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    description_text: str
    posted_at: datetime | None
    application_deadline: datetime | None
    hiring_manager_name: str | None
    hiring_manager_email: str | None
    hiring_manager_phone: str | None


class JobSource:
    name = "base"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        raise NotImplementedError


class RemotiveSource(JobSource):
    name = "remotive"
    base_url = "https://remotive.com/api/remote-jobs"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        params = {}
        if query.get("search"):
            params["search"] = query["search"]
        response = httpx.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        jobs = []
        for item in payload.get("jobs", []):
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id")),
                    url=item.get("url") or "",
                    title=item.get("title") or "Untitled",
                    company=item.get("company_name") or "Unknown",
                    location=item.get("candidate_required_location") or "Remote",
                    remote_flag=True,
                    salary_min=None,
                    salary_max=None,
                    currency=None,
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("publication_date")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class TheMuseSource(JobSource):
    name = "themuse"
    base_url = "https://www.themuse.com/api/public/jobs"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        params = {"page": 1}
        if query.get("search"):
            params["text"] = query["search"]
        if query.get("location"):
            params["location"] = query["location"]
        response = httpx.get(self.base_url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        jobs = []
        for item in payload.get("results", []):
            company = (item.get("company") or {}).get("name") or "Unknown"
            locations = item.get("locations") or []
            location = locations[0].get("name") if locations else "Unknown"
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id")),
                    url=item.get("refs", {}).get("landing_page") or "",
                    title=item.get("name") or "Untitled",
                    company=company,
                    location=location,
                    remote_flag="remote" in location.lower(),
                    salary_min=None,
                    salary_max=None,
                    currency=None,
                    description_text=item.get("contents") or "",
                    posted_at=_parse_dt(item.get("publication_date")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        companies = _split_list(os.getenv("GREENHOUSE_COMPANIES", ""))
        jobs: list[JobPosting] = []
        for company in companies:
            url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
            response = httpx.get(url, timeout=30)
            if response.status_code != 200:
                continue
            payload = response.json()
            for item in payload.get("jobs", []):
                location = (item.get("location") or {}).get("name") or "Unknown"
                jobs.append(
                    JobPosting(
                        source=self.name,
                        source_job_id=str(item.get("id")),
                        url=item.get("absolute_url") or "",
                        title=item.get("title") or "Untitled",
                        company=company,
                        location=location,
                        remote_flag="remote" in location.lower(),
                        salary_min=None,
                        salary_max=None,
                        currency=None,
                        description_text=item.get("content") or "",
                        posted_at=_parse_dt(
                            item.get("updated_at") or item.get("created_at")
                        ),
                        application_deadline=None,
                        hiring_manager_name=None,
                        hiring_manager_email=None,
                        hiring_manager_phone=None,
                    )
                )
        return jobs


class LeverSource(JobSource):
    name = "lever"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        companies = _split_list(os.getenv("LEVER_COMPANIES", ""))
        jobs: list[JobPosting] = []
        for company in companies:
            url = f"https://api.lever.co/v0/postings/{company}"
            response = httpx.get(url, params={"mode": "json"}, timeout=30)
            if response.status_code != 200:
                continue
            payload = response.json()
            for item in payload:
                location = (item.get("categories") or {}).get("location") or "Unknown"
                jobs.append(
                    JobPosting(
                        source=self.name,
                        source_job_id=str(item.get("id")),
                        url=item.get("hostedUrl") or "",
                        title=item.get("text") or "Untitled",
                        company=company,
                        location=location,
                        remote_flag="remote" in location.lower(),
                        salary_min=None,
                        salary_max=None,
                        currency=None,
                        description_text=item.get("descriptionPlain") or "",
                        posted_at=_parse_dt(
                            item.get("createdAt") or item.get("created_at")
                        ),
                        application_deadline=None,
                        hiring_manager_name=None,
                        hiring_manager_email=None,
                        hiring_manager_phone=None,
                    )
                )
        return jobs


class ManualListSource(JobSource):
    name = "manual"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        path = os.getenv("MANUAL_JOBS_PATH", "").strip()
        if not path:
            return []
        file_path = Path(path)
        if not file_path.exists():
            return []
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        jobs: list[JobPosting] = []
        for item in payload:
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or item.get("url") or ""),
                    url=item.get("url") or "",
                    title=item.get("title") or "Untitled",
                    company=item.get("company") or "Unknown",
                    location=item.get("location") or "Unknown",
                    remote_flag=bool(item.get("remote_flag")),
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    currency=item.get("currency"),
                    description_text=item.get("description_text") or "",
                    posted_at=_parse_dt(item.get("posted_at")),
                    application_deadline=_parse_dt(item.get("application_deadline")),
                    hiring_manager_name=item.get("hiring_manager_name"),
                    hiring_manager_email=item.get("hiring_manager_email"),
                    hiring_manager_phone=item.get("hiring_manager_phone"),
                )
            )
        return jobs


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        cleaned = value.strip()
        # Trim fractional seconds beyond 6 digits for fromisoformat compatibility.
        cleaned = re.sub(r"(\.\d{6})\d+(?=(?:Z|[+-]\d{2}:\d{2})?$)", r"\1", cleaned)
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            try:
                return _parse_dt(float(cleaned))
            except ValueError:
                return None
    return None


def _is_remote_job(title: str, location: str) -> bool:
    """Detect if a job is remote based on title and location keywords."""
    text = f"{title} {location}".lower()
    remote_keywords = [
        "remote",
        "virtual",
        "work from home",
        "wfh",
        "telecommute",
        "telework",
        "anywhere",
        "distributed",
        "home-based",
        "home based",
    ]
    return any(kw in text for kw in remote_keywords)


def _parse_salary_text(text: str) -> tuple[int | None, int | None, str | None]:
    """
    Parse salary information from text.

    Handles formats like:
    - "$50,000 - $70,000"
    - "$50k - $70k"
    - "Between $119-$239 an hour"
    - "$100,000/year"
    - "USD 80,000 - 120,000"

    Returns (salary_min, salary_max, currency)
    """
    if not text:
        return None, None, None

    text_lower = text.lower()

    # Detect currency
    currency = None
    if "$" in text or "usd" in text_lower:
        currency = "USD"
    elif "€" in text or "eur" in text_lower:
        currency = "EUR"
    elif "£" in text or "gbp" in text_lower:
        currency = "GBP"

    # Extract salary amounts with optional 'k' suffix
    # Pattern matches: $100k, $100,000, 100k, 100000, etc.
    amount_pattern = r"[\$€£]?\s*(\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?\s*([kK])?"

    # Find all potential salary amounts
    amounts = []
    for match in re.finditer(amount_pattern, text):
        amount_str = match.group(1).replace(",", "")
        k_suffix = match.group(2)
        try:
            amount = float(amount_str)
            # Apply 'k' multiplier if present
            if k_suffix:
                amount *= 1000
            # If amount is very small (< 500), might be hourly rate
            if amount < 500:
                # Check if it's an hourly rate
                if (
                    "hour" in text_lower
                    or "/hr" in text_lower
                    or "per hr" in text_lower
                ):
                    # Convert to annual (2080 work hours/year)
                    amount = amount * 2080
            # Filter out unreasonably small amounts (likely not salaries)
            if amount >= 1000:
                amounts.append(int(amount))
        except ValueError:
            continue

    if not amounts:
        return None, None, currency

    # Sort amounts and take min/max
    amounts = sorted(set(amounts))

    if len(amounts) == 1:
        return amounts[0], amounts[0], currency
    else:
        return amounts[0], amounts[-1], currency


class RemoteOkSource(JobSource):
    name = "remoteok"
    base_url = "https://remoteok.com/api"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        response = httpx.get(self.base_url, timeout=30)
        if response.status_code != 200:
            return []
        payload = response.json()
        jobs = []
        for item in payload:
            if not isinstance(item, dict) or "id" not in item:
                continue
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id")),
                    url=item.get("url") or "",
                    title=item.get("position") or "Untitled",
                    company=item.get("company") or "Unknown",
                    location=item.get("location") or "Remote",
                    remote_flag=True,
                    salary_min=None,
                    salary_max=None,
                    currency=None,
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("date")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class AdzunaSource(JobSource):
    name = "adzuna"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        app_id = os.getenv("ADZUNA_APP_ID")
        app_key = os.getenv("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            return []
        params = {"app_id": app_id, "app_key": app_key, "results_per_page": 20}
        if query.get("search"):
            params["what"] = query["search"]
        if query.get("location"):
            params["where"] = query["location"]
        url = "https://api.adzuna.com/v1/api/jobs/us/search/1"
        response = httpx.get(url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        payload = response.json()
        jobs = []
        for item in payload.get("results", []):
            title = item.get("title") or "Untitled"
            location = (item.get("location") or {}).get("display_name") or "Unknown"
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id")),
                    url=item.get("redirect_url") or "",
                    title=title,
                    company=(item.get("company") or {}).get("display_name")
                    or "Unknown",
                    location=location,
                    remote_flag=_is_remote_job(title, location),
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    currency=item.get("salary_currency"),
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("created") or item.get("created_at")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class JoobleSource(JobSource):
    name = "jooble"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("JOOBLE_API_KEY")
        if not api_key:
            return []
        url = f"https://jooble.org/api/{api_key}"
        payload = {"keywords": query.get("search"), "location": query.get("location")}
        response = httpx.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            return []
        data = response.json()
        jobs = []
        for item in data.get("jobs", []):
            title = item.get("title") or "Untitled"
            location = item.get("location") or "Unknown"
            salary_text = item.get("salary") or ""

            # Detect remote jobs from title or location
            remote_flag = _is_remote_job(title, location)

            # Parse salary from text
            # (e.g., "$50,000 - $70,000", "Between $119-$239 an hour")
            salary_min, salary_max, currency = _parse_salary_text(salary_text)

            # Also try to extract salary from snippet if not in salary field
            snippet = item.get("snippet") or ""
            if salary_min is None and salary_max is None:
                salary_min, salary_max, currency = _parse_salary_text(snippet)

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or item.get("link") or ""),
                    url=item.get("link") or "",
                    title=title,
                    company=item.get("company") or "Unknown",
                    location=location,
                    remote_flag=remote_flag,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    description_text=snippet,
                    posted_at=_parse_dt(item.get("updated") or item.get("date")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class USAJobsSource(JobSource):
    name = "usajobs"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("USAJOBS_API_KEY")
        email = os.getenv("USAJOBS_EMAIL")
        if not api_key or not email:
            return []
        headers = {"Authorization-Key": api_key, "User-Agent": email}
        params = {
            "Keyword": query.get("search") or "",
            "LocationName": query.get("location") or "",
        }
        response = httpx.get(
            "https://data.usajobs.gov/api/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            return []
        data = response.json()
        jobs = []
        for item in data.get("SearchResult", {}).get("SearchResultItems", []):
            matched = item.get("MatchedObjectDescriptor", {})
            title = matched.get("PositionTitle") or "Untitled"
            location = (matched.get("PositionLocation") or [{}])[0].get(
                "LocationName", "Unknown"
            )

            # Parse salary from USAJobs remuneration fields
            remuneration = (matched.get("PositionRemuneration") or [{}])[0]
            salary_min = None
            salary_max = None
            if remuneration.get("MinimumRange"):
                try:
                    salary_min = int(float(remuneration["MinimumRange"]))
                except (ValueError, TypeError):
                    pass
            if remuneration.get("MaximumRange"):
                try:
                    salary_max = int(float(remuneration["MaximumRange"]))
                except (ValueError, TypeError):
                    pass

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(matched.get("PositionID") or ""),
                    url=matched.get("PositionURI", [""])[0],
                    title=title,
                    company=matched.get("OrganizationName") or "US Government",
                    location=location,
                    remote_flag=_is_remote_job(title, location),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency="USD",
                    description_text=matched.get("UserArea", {})
                    .get("Details", {})
                    .get("JobSummary", ""),
                    posted_at=_parse_dt(matched.get("PublicationStartDate")),
                    application_deadline=_parse_dt(matched.get("ApplicationCloseDate")),
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class JSearchSource(JobSource):
    """JSearch API via RapidAPI.

    Aggregates jobs from LinkedIn, Indeed, Glassdoor, etc.
    """

    name = "jsearch"
    base_url = "https://jsearch.p.rapidapi.com/search"

    @staticmethod
    def _track(counter: str) -> None:
        """Increment a daily Redis counter for JSearch API usage.

        Keys: jsearch:{requests|calls|errors}:YYYY-MM-DD
        TTL: 35 days (auto-cleanup, keeps full month visible).
        """
        try:
            from app.services.queue import get_redis_connection

            conn = get_redis_connection()
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            key = f"jsearch:{counter}:{today}"
            conn.incr(key)
            conn.expire(key, 35 * 86400)  # 35 days
        except Exception:
            pass  # tracking is best-effort

    def _build_html_from_highlights(self, highlights: dict, description: str) -> str:
        """Convert job_highlights structured data to formatted HTML."""
        html_parts = []

        # Add plain description as intro paragraph if short, else skip
        if description and len(description) < 500:
            html_parts.append(f"<p>{description}</p>")

        for section_name, items in highlights.items():
            if not items:
                continue
            # Convert section name to title case
            # (e.g., "Qualifications" -> "Qualifications")
            title = section_name.replace("_", " ").title()
            html_parts.append(f"<h3>{title}</h3>")
            html_parts.append("<ul>")
            for item in items:
                html_parts.append(f"<li>{item}</li>")
            html_parts.append("</ul>")

        return "\n".join(html_parts) if html_parts else ""

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("RAPIDAPI_KEY")
        if not api_key:
            return []

        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        params = {
            "query": query.get("search") or "project manager",
            "page": "1",
            "num_pages": "3",
            "date_posted": "week",
        }
        if query.get("location"):
            params["query"] = f"{params['query']} in {query['location']}"
        if query.get("remote"):
            params["remote_jobs_only"] = "true"
        if query.get("employment_types"):
            params["employment_types"] = query["employment_types"]

        # Retry once on transient failures (429, 5xx)
        response = None
        for attempt in range(2):
            response = httpx.get(
                self.base_url, headers=headers, params=params, timeout=30
            )
            self._track("requests")
            if response.status_code == 200:
                self._track("calls")
                break
            if attempt == 0 and response.status_code in (429, 500, 502, 503, 504):
                time.sleep(2)
                continue
            break

        if response.status_code != 200:
            self._track("errors")
            logger.warning(
                "JSearch API returned %d: %s",
                response.status_code,
                response.text[:200],
            )
            return []

        data = response.json()
        jobs = []
        for item in data.get("data", []):
            # Build location string
            city = item.get("job_city") or ""
            state = item.get("job_state") or ""
            country = item.get("job_country") or ""
            location_parts = [p for p in [city, state, country] if p]
            location = ", ".join(location_parts) or "Unknown"

            # Parse salary
            salary_min = None
            salary_max = None
            if item.get("job_min_salary"):
                try:
                    salary_min = int(float(item["job_min_salary"]))
                except (ValueError, TypeError):
                    pass
            if item.get("job_max_salary"):
                try:
                    salary_max = int(float(item["job_max_salary"]))
                except (ValueError, TypeError):
                    pass

            # Build description - use job_highlights if available for formatted HTML
            raw_description = item.get("job_description") or ""
            highlights = item.get("job_highlights")
            if highlights and isinstance(highlights, dict):
                # Use structured highlights to build formatted HTML
                description_text = self._build_html_from_highlights(
                    highlights, raw_description
                )
            else:
                description_text = raw_description

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("job_id") or ""),
                    url=item.get("job_apply_link") or "",
                    title=item.get("job_title") or "Untitled",
                    company=item.get("employer_name") or "Unknown",
                    location=location,
                    remote_flag=bool(item.get("job_is_remote")),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=item.get("job_salary_currency")
                    or ("USD" if salary_min or salary_max else None),
                    description_text=description_text,
                    posted_at=_parse_dt(item.get("job_posted_at_datetime_utc")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class JobicySource(JobSource):
    """Jobicy - remote jobs board with US geo filter."""

    name = "jobicy"
    base_url = "https://jobicy.com/api/v2/remote-jobs"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        params = {"count": 50, "geo": "usa"}
        response = httpx.get(self.base_url, params=params, timeout=30)
        if response.status_code != 200:
            return []
        payload = response.json()
        jobs = []
        for item in payload.get("jobs", []):
            salary_min = None
            salary_max = None
            currency = None
            if item.get("annualSalaryMin"):
                try:
                    salary_min = int(float(item["annualSalaryMin"]))
                except (ValueError, TypeError):
                    pass
            if item.get("annualSalaryMax"):
                try:
                    salary_max = int(float(item["annualSalaryMax"]))
                except (ValueError, TypeError):
                    pass
            if salary_min or salary_max:
                currency = item.get("salaryCurrency") or "USD"

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or ""),
                    url=item.get("url") or "",
                    title=item.get("jobTitle") or "Untitled",
                    company=item.get("companyName") or "Unknown",
                    location=item.get("jobGeo") or "Remote",
                    remote_flag=True,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    description_text=item.get("jobDescription") or "",
                    posted_at=_parse_dt(item.get("pubDate")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class JoinRiseSource(JobSource):
    """JoinRise - free public jobs API. No authentication required."""

    name = "joinrise"
    base_url = "https://api.joinrise.io/api/v1/jobs/public"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        params: dict = {
            "page": 1,
            "limit": 50,
            "sort": "desc",
            "sortedBy": "createdAt",
        }
        if query.get("search"):
            params["search"] = query["search"]
        if query.get("location"):
            params["jobLoc"] = query["location"]

        response = httpx.get(self.base_url, params=params, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        result = data.get("result") or data
        items = result.get("jobs") or result.get("data") or []
        if isinstance(data, list):
            items = data

        jobs: list[JobPosting] = []
        for item in items:
            title = item.get("title") or ""
            location = item.get("locationAddress") or ""
            url = item.get("url") or ""
            if not title or not url:
                continue

            job_type = (item.get("type") or "").lower()
            remote_flag = "remote" in job_type or _is_remote_job(title, location)

            # Parse salary from descriptionBreakdown if available
            breakdown = item.get("descriptionBreakdown") or {}
            salary_text = breakdown.get("salary") or ""
            salary_min, salary_max, currency = _parse_salary_text(salary_text)

            # Company name can be in owner.companyName or top-level
            owner = item.get("owner") or {}
            company = (
                item.get("companyName")
                or owner.get("companyName")
                or "Unknown"
            )

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("_id") or item.get("id") or ""),
                    url=url,
                    title=title,
                    company=company,
                    location=location or "Unknown",
                    remote_flag=remote_flag,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("createdAt")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class CareerJetSource(JobSource):
    """CareerJet affiliate API — large global job aggregator.

    Requires free affiliate ID from careerjet.com/partners.
    """

    name = "careerjet"
    base_url = "https://public.api.careerjet.net/search"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        affid = os.getenv("CAREERJET_AFFID")
        if not affid:
            return []

        params: dict = {
            "affid": affid,
            "locale_code": "en_US",
            "keywords": query.get("search") or "software engineer",
            "location": query.get("location") or "United States",
            "pagesize": 99,
            "page": 1,
            "sort": "date",
            "user_ip": "1.2.3.4",
            "user_agent": "Winnow/1.0",
        }

        response = httpx.get(self.base_url, params=params, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("jobs", [])

        jobs: list[JobPosting] = []
        for item in items:
            title = item.get("title") or ""
            url = item.get("url") or ""
            if not title or not url:
                continue

            location = ", ".join(
                p
                for p in [
                    item.get("locations") or item.get("location") or "",
                ]
                if p
            ) or "Unknown"

            salary_text = item.get("salary") or ""
            salary_min, salary_max, currency = _parse_salary_text(salary_text)

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(
                        item.get("id") or item.get("url") or ""
                    ),
                    url=url,
                    title=title,
                    company=item.get("company") or "Unknown",
                    location=location,
                    remote_flag=_is_remote_job(title, location),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("date")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class FindWorkSource(JobSource):
    """FindWork.dev - free API for tech/dev jobs.

    Requires free API key from findwork.dev.
    """

    name = "findwork"
    base_url = "https://findwork.dev/api/jobs/"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("FINDWORK_API_KEY")
        if not api_key:
            return []

        headers = {"Authorization": f"Token {api_key}"}
        params: dict = {
            "search": query.get("search") or "software",
            "location": query.get("location") or "",
        }

        response = httpx.get(
            self.base_url, headers=headers, params=params, timeout=30
        )
        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("results", [])

        jobs: list[JobPosting] = []
        for item in items:
            title = item.get("role") or ""
            url = item.get("url") or ""
            if not title or not url:
                continue

            location = item.get("location") or "Unknown"
            remote_flag = bool(item.get("remote")) or _is_remote_job(
                title, location
            )

            salary_text = item.get("salary") or ""
            salary_min, salary_max, currency = _parse_salary_text(salary_text)

            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or ""),
                    url=url,
                    title=title,
                    company=item.get("company_name") or "Unknown",
                    location=location,
                    remote_flag=remote_flag,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    description_text=item.get("text") or "",
                    posted_at=_parse_dt(item.get("date_posted")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class HimalayasSource(JobSource):
    """Himalayas - remote jobs board. Fetches 3 pages (60 jobs max)."""

    name = "himalayas"
    base_url = "https://himalayas.app/jobs/api"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for page in range(3):
            params = {"limit": 20, "offset": page * 20}
            response = httpx.get(self.base_url, params=params, timeout=30)
            if response.status_code != 200:
                break
            payload = response.json()
            items = payload.get("jobs", [])
            if not items:
                break
            for item in items:
                salary_min = None
                salary_max = None
                currency = None
                if item.get("minSalary"):
                    try:
                        salary_min = int(float(item["minSalary"]))
                    except (ValueError, TypeError):
                        pass
                if item.get("maxSalary"):
                    try:
                        salary_max = int(float(item["maxSalary"]))
                    except (ValueError, TypeError):
                        pass
                if salary_min or salary_max:
                    currency = item.get("currency") or "USD"

                # locationRestrictions is an array
                restrictions = item.get("locationRestrictions") or []
                location = ", ".join(restrictions) if restrictions else "Remote"

                jobs.append(
                    JobPosting(
                        source=self.name,
                        source_job_id=str(item.get("guid") or ""),
                        url=item.get("applicationLink") or "",
                        title=item.get("title") or "Untitled",
                        company=item.get("companyName") or "Unknown",
                        location=location,
                        remote_flag=True,
                        salary_min=salary_min,
                        salary_max=salary_max,
                        currency=currency,
                        description_text=item.get("description") or "",
                        posted_at=_parse_dt(item.get("pubDate")),
                        application_deadline=None,
                        hiring_manager_name=None,
                        hiring_manager_email=None,
                        hiring_manager_phone=None,
                    )
                )
        return jobs


def get_job_sources() -> list[JobSource]:
    configured = _split_list(
        os.getenv(
            "JOB_SOURCES",
            "remotive,themuse,greenhouse,lever,remoteok,adzuna,jooble,usajobs,joinrise,careerjet,findwork,jobicy,himalayas,manual,jsearch",
        )
    )
    available = {
        RemotiveSource.name: RemotiveSource(),
        TheMuseSource.name: TheMuseSource(),
        GreenhouseSource.name: GreenhouseSource(),
        LeverSource.name: LeverSource(),
        RemoteOkSource.name: RemoteOkSource(),
        AdzunaSource.name: AdzunaSource(),
        JoobleSource.name: JoobleSource(),
        USAJobsSource.name: USAJobsSource(),
        JSearchSource.name: JSearchSource(),
        JoinRiseSource.name: JoinRiseSource(),
        CareerJetSource.name: CareerJetSource(),
        FindWorkSource.name: FindWorkSource(),
        JobicySource.name: JobicySource(),
        HimalayasSource.name: HimalayasSource(),
        ManualListSource.name: ManualListSource(),
    }
    return [available[name] for name in configured if name in available]
