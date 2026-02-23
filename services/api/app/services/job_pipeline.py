from __future__ import annotations

import logging

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.services.embedding import (
    generate_embedding,
    prepare_job_text,
    prepare_profile_text,
)
from app.services.job_ingestion import ingest_jobs
from app.services.matching import compute_matches
from app.services.tailor import create_tailored_docs

logger = logging.getLogger(__name__)


def ingest_jobs_job(query: dict) -> int:
    session = get_session_factory()()
    try:
        return ingest_jobs(session, query)
    finally:
        session.close()


def match_jobs_job(user_id: int, profile_version: int) -> int:
    session = get_session_factory()()
    try:
        matches = compute_matches(session, user_id, profile_version)
        return len(matches)
    finally:
        session.close()


def tailor_job(user_id: int, job_id: int, profile_version: int) -> int:
    session = get_session_factory()()
    try:
        tailored = create_tailored_docs(session, user_id, job_id, profile_version)
        return tailored.id
    finally:
        session.close()


def embed_job(job_id: int) -> bool:
    """Generate and store embedding for a single job."""
    session = get_session_factory()()
    try:
        job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.warning("embed_job: job %s not found", job_id)
            return False
        text = prepare_job_text(job)
        job.embedding = generate_embedding(text)
        session.commit()
        logger.info("embed_job: embedded job %s", job_id)
        return True
    except Exception:
        session.rollback()
        logger.exception("embed_job: failed for job %s", job_id)
        return False
    finally:
        session.close()


def embed_profile(user_id: int, profile_version: int) -> bool:
    """Generate and store embedding for a candidate profile."""
    session = get_session_factory()()
    try:
        profile = session.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id == user_id,
                CandidateProfile.version == profile_version,
            )
        ).scalar_one_or_none()
        if profile is None:
            logger.warning(
                "embed_profile: profile not found for user=%s version=%s",
                user_id,
                profile_version,
            )
            return False
        text = prepare_profile_text(profile.profile_json)
        profile.embedding = generate_embedding(text)
        session.commit()
        logger.info(
            "embed_profile: embedded profile user=%s version=%s",
            user_id,
            profile_version,
        )
        return True
    except Exception:
        session.rollback()
        logger.exception(
            "embed_profile: failed for user=%s version=%s", user_id, profile_version
        )
        return False
    finally:
        session.close()


def embed_all_jobs() -> int:
    """Batch backfill embeddings for all jobs where embedding IS NULL."""
    session = get_session_factory()()
    try:
        jobs = (
            session.execute(
                select(Job).where(Job.embedding.is_(None))
            )
            .scalars()
            .all()
        )
        count = 0
        for job in jobs:
            try:
                text = prepare_job_text(job)
                job.embedding = generate_embedding(text)
                count += 1
                if count % 50 == 0:
                    session.commit()
                    logger.info("embed_all_jobs: embedded %s jobs so far", count)
            except Exception:
                logger.exception("embed_all_jobs: failed for job %s", job.id)
        session.commit()
        logger.info("embed_all_jobs: finished, embedded %s jobs total", count)
        return count
    except Exception:
        session.rollback()
        logger.exception("embed_all_jobs: batch failed")
        return 0
    finally:
        session.close()


def refresh_candidates_for_profile(user_id: int) -> None:
    """Placeholder for future candidate-refresh logic after profile update."""
    pass
