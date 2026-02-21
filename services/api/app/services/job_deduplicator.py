"""Job deduplicator — detects duplicate job postings across boards."""

import hashlib
import logging
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job

logger = logging.getLogger(__name__)

# Similarity threshold for title + company + location matching.
SIMILARITY_THRESHOLD = 0.85


def find_duplicates(job_id: int, session: Session) -> list[dict]:
    """Find jobs that are duplicates of the given job.

    Uses content hashing and title/company/location similarity.
    Returns list of dicts with duplicate job info.
    """
    job = session.get(Job, job_id)
    if not job:
        return []

    content_hash = _content_hash(job)

    # Find by exact content hash first
    stmt = select(Job).where(
        Job.id != job_id,
        Job.is_active.is_(True),
    )
    candidates = list(session.execute(stmt).scalars().all())

    duplicates = []
    for candidate in candidates:
        cand_hash = _content_hash(candidate)

        # Exact hash match
        if cand_hash == content_hash:
            duplicates.append(
                {
                    "job_id": candidate.id,
                    "title": candidate.title,
                    "company": candidate.company,
                    "source": candidate.source,
                    "similarity": 1.0,
                    "match_type": "exact_content",
                }
            )
            continue

        # Fuzzy match on title + company + location
        similarity = _compute_similarity(job, candidate)
        if similarity >= SIMILARITY_THRESHOLD:
            duplicates.append(
                {
                    "job_id": candidate.id,
                    "title": candidate.title,
                    "company": candidate.company,
                    "source": candidate.source,
                    "similarity": round(similarity, 3),
                    "match_type": "fuzzy",
                }
            )

    return sorted(duplicates, key=lambda d: d["similarity"], reverse=True)


def deduplicate_results(job_ids: list[int], session: Session) -> list[dict]:
    """Given a list of job IDs, group duplicates together.

    Returns list of dicts, each with a primary job and its duplicates.
    """
    if not job_ids:
        return []

    jobs = []
    for jid in job_ids:
        job = session.get(Job, jid)
        if job:
            jobs.append(job)

    seen: set[int] = set()
    groups: list[dict] = []

    for job in jobs:
        if job.id in seen:
            continue
        seen.add(job.id)

        group = {
            "primary_job_id": job.id,
            "title": job.title,
            "company": job.company,
            "also_posted_on": [],
        }

        for other in jobs:
            if other.id in seen:
                continue
            sim = _compute_similarity(job, other)
            if sim >= SIMILARITY_THRESHOLD:
                seen.add(other.id)
                group["also_posted_on"].append(
                    {
                        "job_id": other.id,
                        "source": other.source,
                        "similarity": round(sim, 3),
                    }
                )

        groups.append(group)

    return groups


def _content_hash(job: Job) -> str:
    """Generate a content hash for deduplication."""
    text = "|".join(
        (s or "").strip().lower() for s in [job.title, job.company, job.location]
    )
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _compute_similarity(job_a: Job, job_b: Job) -> float:
    """Compute similarity between two jobs (0.0 to 1.0)."""
    title_sim = _text_similarity(job_a.title or "", job_b.title or "")
    company_sim = _text_similarity(job_a.company or "", job_b.company or "")
    location_sim = _text_similarity(job_a.location or "", job_b.location or "")

    # Weighted average: title and company matter most
    return 0.4 * title_sim + 0.4 * company_sim + 0.2 * location_sim


def _text_similarity(a: str, b: str) -> float:
    """Compute text similarity using SequenceMatcher."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
