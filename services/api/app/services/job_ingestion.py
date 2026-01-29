from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.job_sources import JobPosting, get_job_sources


def ingest_jobs(session: Session, query: dict) -> int:
    now = datetime.now(timezone.utc)
    new_count = 0
    for source in get_job_sources():
        try:
            postings = source.fetch_jobs(query)
        except Exception:
            continue
        for posting in postings:
            if not _is_recent_posting(posting.posted_at, now):
                continue
            description = _clean_text(posting.description_text)
            content_hash = _hash_posting(posting, description)
            exists = session.execute(
                select(Job.id).where(Job.content_hash == content_hash)
            ).scalar_one_or_none()
            if exists:
                continue
            legacy_hash = _hash_posting(posting, posting.description_text)
            legacy = session.execute(
                select(Job).where(Job.content_hash == legacy_hash)
            ).scalar_one_or_none()
            if legacy:
                legacy.description_text = description
                legacy.content_hash = content_hash
                session.add(legacy)
                continue
            job = Job(
                source=posting.source,
                source_job_id=posting.source_job_id,
                url=posting.url,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                remote_flag=posting.remote_flag,
                salary_min=posting.salary_min,
                salary_max=posting.salary_max,
                currency=posting.currency,
                description_text=description,
                content_hash=content_hash,
                posted_at=posting.posted_at,
                application_deadline=posting.application_deadline,
                hiring_manager_name=posting.hiring_manager_name,
                hiring_manager_email=posting.hiring_manager_email,
                hiring_manager_phone=posting.hiring_manager_phone,
            )
            session.add(job)
            new_count += 1
    session.commit()
    return new_count


def _hash_posting(posting: JobPosting, description_text: str) -> str:
    raw = "|".join(
        [
            posting.title or "",
            posting.company or "",
            posting.location or "",
            description_text or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clean_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_recent_posting(posted_at: datetime | None, now: datetime) -> bool:
    if posted_at is None:
        return False
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=7)
    return posted_at >= cutoff
