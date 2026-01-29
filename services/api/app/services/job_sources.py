from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Iterable

import httpx


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
                    posted_at=_parse_dt(item.get("updated_at") or item.get("created_at")),
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
                    posted_at=_parse_dt(item.get("createdAt") or item.get("created_at")),
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
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp = timestamp / 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
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


class ArbeitnowSource(JobSource):
    name = "arbeitnow"
    base_url = "https://arbeitnow.com/api/job-board-api"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        response = httpx.get(self.base_url, timeout=30)
        if response.status_code != 200:
            return []
        payload = response.json()
        jobs = []
        for item in payload.get("data", []):
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("slug") or item.get("url") or ""),
                    url=item.get("url") or "",
                    title=item.get("title") or "Untitled",
                    company=item.get("company_name") or "Unknown",
                    location=item.get("location") or "Unknown",
                    remote_flag=bool(item.get("remote")),
                    salary_min=None,
                    salary_max=None,
                    currency=None,
                    description_text=item.get("description") or "",
                    posted_at=_parse_dt(item.get("created_at") or item.get("posted_at")),
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
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id")),
                    url=item.get("redirect_url") or "",
                    title=item.get("title") or "Untitled",
                    company=(item.get("company") or {}).get("display_name") or "Unknown",
                    location=(item.get("location") or {}).get("display_name") or "Unknown",
                    remote_flag=False,
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
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or item.get("link") or ""),
                    url=item.get("link") or "",
                    title=item.get("title") or "Untitled",
                    company=item.get("company") or "Unknown",
                    location=item.get("location") or "Unknown",
                    remote_flag=False,
                    salary_min=None,
                    salary_max=None,
                    currency=None,
                    description_text=item.get("snippet") or "",
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
        params = {"Keyword": query.get("search") or "", "LocationName": query.get("location") or ""}
        response = httpx.get(
            "https://data.usajobs.gov/api/search", headers=headers, params=params, timeout=30
        )
        if response.status_code != 200:
            return []
        data = response.json()
        jobs = []
        for item in data.get("SearchResult", {}).get("SearchResultItems", []):
            matched = item.get("MatchedObjectDescriptor", {})
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(matched.get("PositionID") or ""),
                    url=matched.get("PositionURI", [""])[0],
                    title=matched.get("PositionTitle") or "Untitled",
                    company=matched.get("OrganizationName") or "US Government",
                    location=(matched.get("PositionLocation") or [{}])[0].get(
                        "LocationName", "Unknown"
                    ),
                    remote_flag=False,
                    salary_min=None,
                    salary_max=None,
                    currency="USD",
                    description_text=matched.get("UserArea", {}).get("Details", {}).get(
                        "JobSummary", ""
                    ),
                    posted_at=_parse_dt(matched.get("PublicationStartDate")),
                    application_deadline=_parse_dt(matched.get("ApplicationCloseDate")),
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class ZipRecruiterSource(JobSource):
    name = "ziprecruiter"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("ZIPRECRUITER_API_KEY")
        if not api_key:
            return []
        params = {
            "api_key": api_key,
            "search": query.get("search") or "",
            "location": query.get("location") or "",
        }
        response = httpx.get("https://api.ziprecruiter.com/jobs/v1", params=params, timeout=30)
        if response.status_code != 200:
            return []
        data = response.json()
        jobs = []
        for item in data.get("jobs", []):
            jobs.append(
                JobPosting(
                    source=self.name,
                    source_job_id=str(item.get("id") or ""),
                    url=item.get("url") or "",
                    title=item.get("name") or "Untitled",
                    company=item.get("hiring_company", {}).get("name") or "Unknown",
                    location=item.get("location") or "Unknown",
                    remote_flag=False,
                    salary_min=None,
                    salary_max=None,
                    currency=item.get("salary_currency"),
                    description_text=item.get("snippet") or "",
                    posted_at=_parse_dt(item.get("posted_time") or item.get("posted_at")),
                    application_deadline=None,
                    hiring_manager_name=None,
                    hiring_manager_email=None,
                    hiring_manager_phone=None,
                )
            )
        return jobs


class BuiltInSource(JobSource):
    name = "builtin"

    def fetch_jobs(self, query: dict) -> list[JobPosting]:
        api_key = os.getenv("BUILTIN_API_KEY")
        if not api_key:
            return []
        return []


def get_job_sources() -> list[JobSource]:
    configured = _split_list(
        os.getenv(
            "JOB_SOURCES",
            "remotive,themuse,greenhouse,lever,remoteok,arbeitnow,adzuna,jooble,usajobs,ziprecruiter,builtin,manual",
        )
    )
    available = {
        RemotiveSource.name: RemotiveSource(),
        TheMuseSource.name: TheMuseSource(),
        GreenhouseSource.name: GreenhouseSource(),
        LeverSource.name: LeverSource(),
        RemoteOkSource.name: RemoteOkSource(),
        ArbeitnowSource.name: ArbeitnowSource(),
        AdzunaSource.name: AdzunaSource(),
        JoobleSource.name: JoobleSource(),
        USAJobsSource.name: USAJobsSource(),
        ZipRecruiterSource.name: ZipRecruiterSource(),
        BuiltInSource.name: BuiltInSource(),
        ManualListSource.name: ManualListSource(),
    }
    return [available[name] for name in configured if name in available]
