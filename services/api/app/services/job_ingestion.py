from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.job_sources import JobPosting, get_job_sources

logger = logging.getLogger(__name__)


def _update_progress(run_id: int | None, completed: int, total: int, jobs: int) -> None:
    """Write ingestion progress to Redis so the admin UI can poll it."""
    if run_id is None:
        return
    try:
        from app.services.queue import get_redis_connection

        conn = get_redis_connection()
        key = f"ingestion:{run_id}:progress"
        conn.set(
            key,
            json.dumps(
                {
                    "completed_sources": completed,
                    "total_sources": total,
                    "jobs_so_far": jobs,
                }
            ),
            ex=600,  # auto-expire after 10 min
        )
    except Exception:
        logger.debug("Failed to write ingestion progress to Redis", exc_info=True)


def clear_progress(run_id: int) -> None:
    """Remove the progress key from Redis after ingestion finishes."""
    try:
        from app.services.queue import get_redis_connection

        conn = get_redis_connection()
        conn.delete(f"ingestion:{run_id}:progress")
    except Exception:
        logger.debug("Failed to clear ingestion progress from Redis", exc_info=True)


def ingest_jobs(session: Session, query: dict, *, run_id: int | None = None) -> int:
    now = datetime.now(UTC)
    new_count = 0
    new_jobs: list[Job] = []  # Track new jobs for post-commit parsing
    sources = get_job_sources()
    total_sources = len(sources)
    completed_sources = 0
    logger.info(
        "Starting ingestion from %d sources with query=%s",
        total_sources,
        query,
    )
    _update_progress(run_id, 0, total_sources, 0)
    for source in sources:
        try:
            postings = source.fetch_jobs(query)
            logger.info("Source %s returned %d postings", source.name, len(postings))
        except Exception:
            logger.exception("Source %s failed", source.name)
            completed_sources += 1
            _update_progress(run_id, completed_sources, total_sources, new_count)
            continue
        source_new = 0
        source_stale = 0
        source_dup = 0
        for posting in postings:
            if not _is_recent_posting(posting.posted_at, now):
                source_stale += 1
                continue
            description = _clean_text(posting.description_text)
            description_html = _get_description_html(posting.description_text)
            content_hash = _hash_posting(posting, description)
            exists = session.execute(
                select(Job.id).where(
                    or_(
                        Job.content_hash == content_hash,
                        (Job.source == posting.source)
                        & (Job.source_job_id == posting.source_job_id),
                    )
                )
            ).scalars().first()
            if exists:
                source_dup += 1
                continue
            legacy_hash = _hash_posting(posting, posting.description_text)
            legacy = session.execute(
                select(Job).where(Job.content_hash == legacy_hash)
            ).scalars().first()
            if legacy:
                legacy.description_text = description
                legacy.description_html = description_html
                legacy.content_hash = content_hash
                session.add(legacy)
                source_dup += 1
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
                description_html=description_html,
                content_hash=content_hash,
                posted_at=posting.posted_at,
                application_deadline=posting.application_deadline,
                hiring_manager_name=posting.hiring_manager_name,
                hiring_manager_email=posting.hiring_manager_email,
                hiring_manager_phone=posting.hiring_manager_phone,
            )
            session.add(job)
            new_jobs.append(job)
            source_new += 1
            new_count += 1
        logger.info(
            "Source %s: %d new, %d stale, %d duplicate",
            source.name,
            source_new,
            source_stale,
            source_dup,
        )
        completed_sources += 1
        _update_progress(run_id, completed_sources, total_sources, new_count)
    session.commit()

    # Parse new jobs with regex+taxonomy to create JobParsedDetail records
    # and queue embedding generation. This runs after commit so job IDs exist.
    if new_jobs:
        _parse_new_jobs(session, new_jobs)

    logger.info("Ingestion complete: %d new jobs total", new_count)
    return new_count


def _parse_new_jobs(session: Session, jobs: list[Job]) -> None:
    """Run regex+taxonomy parser on newly ingested jobs and queue embeddings."""
    from app.services.job_parser import JobParserService

    parser = JobParserService()
    parsed_count = 0
    low_skill_jobs: list[int] = []
    for job in jobs:
        try:
            detail = parser.parse(session, job)
            parsed_count += 1
            # Track jobs with few skills for LLM enrichment
            total_skills = len(detail.required_skills or []) + len(
                detail.preferred_skills or []
            )
            if total_skills < 3:
                low_skill_jobs.append(job.id)
            if parsed_count % 50 == 0:
                session.commit()
        except Exception:
            logger.debug("Failed to parse job %s during ingestion", job.id, exc_info=True)
    session.commit()
    logger.info("Parsed %d / %d new jobs during ingestion", parsed_count, len(jobs))

    # Queue embedding generation and LLM skill enrichment
    try:
        from app.services.queue import get_queue

        q = get_queue()
        for job in jobs:
            try:
                q.enqueue("app.services.job_pipeline.embed_job", job.id)
            except Exception:
                logger.debug("Failed to queue embedding for job %s", job.id)
        for job_id in low_skill_jobs:
            try:
                q.enqueue(
                    "app.services.job_pipeline.parse_board_job_skills", job_id
                )
            except Exception:
                logger.debug("Failed to queue LLM skill parse for job %s", job_id)
        if low_skill_jobs:
            logger.info(
                "Queued %d jobs for LLM skill enrichment", len(low_skill_jobs)
            )
    except Exception:
        logger.debug("Queue not available for post-ingestion tasks", exc_info=True)


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
    """Strip HTML tags and normalize whitespace for plain text storage."""
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _contains_html(value: str) -> bool:
    """Check if text contains HTML tags."""
    if not value:
        return False
    html_pattern = re.compile(r"<(?:p|div|ul|ol|li|br|h[1-6]|strong|em|span|a)\b", re.I)
    return bool(html_pattern.search(value))


def _get_description_html(raw_description: str) -> str | None:
    """Return HTML if the raw description contains HTML tags, else None."""
    if _contains_html(raw_description):
        return raw_description
    return None


def _is_recent_posting(posted_at: datetime | None, now: datetime) -> bool:
    if posted_at is None:
        return False
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    cutoff = now - timedelta(days=7)
    return posted_at >= cutoff
