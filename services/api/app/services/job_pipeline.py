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
            session.execute(select(Job).where(Job.embedding.is_(None))).scalars().all()
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


def populate_recruiter_job_candidates(job_id: int) -> None:
    """Background job: compute and cache candidate matches for a recruiter job."""
    from sqlalchemy import delete as sa_delete

    from app.models.recruiter import RecruiterProfile
    from app.models.recruiter_job import RecruiterJob
    from app.models.recruiter_job_candidate import RecruiterJobCandidate
    from app.services.matching import find_top_candidates_for_recruiter_job

    session = get_session_factory()()
    try:
        job = session.get(RecruiterJob, job_id)
        if not job:
            logger.warning(
                "populate_recruiter_job_candidates: job %s not found", job_id
            )
            return
        rp = session.get(RecruiterProfile, job.recruiter_profile_id)
        if not rp:
            logger.warning(
                "populate_recruiter_job_candidates: recruiter profile %s not found",
                job.recruiter_profile_id,
            )
            return

        results = find_top_candidates_for_recruiter_job(session, job, rp.user_id)

        # Delete old cached rows
        session.execute(
            sa_delete(RecruiterJobCandidate).where(
                RecruiterJobCandidate.recruiter_job_id == job_id
            )
        )

        inserted = 0
        for r in results:
            if r["match_score"] <= 50:
                continue
            session.add(
                RecruiterJobCandidate(
                    recruiter_job_id=job_id,
                    candidate_profile_id=r["id"],
                    match_score=r["match_score"],
                    matched_skills=r.get("matched_skills"),
                )
            )
            inserted += 1

        session.commit()
        logger.info(
            "populate_recruiter_job_candidates: job %s — %s candidates cached",
            job_id,
            inserted,
        )
    except Exception:
        session.rollback()
        logger.exception("populate_recruiter_job_candidates: failed for job %s", job_id)
    finally:
        session.close()


def sync_recruiter_job_to_jobs(job_id: int) -> None:
    """Sync recruiter job to the main jobs table for cross-segment visibility."""
    pass


def deactivate_recruiter_job_proxy(job_id: int) -> None:
    """Deactivate the proxy job entry when a recruiter job goes inactive."""
    pass
