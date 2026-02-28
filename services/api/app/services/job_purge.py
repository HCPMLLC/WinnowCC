"""Purge old inactive jobs from the database.

A job is purgeable when ALL of these are true:
  1. is_active = False
  2. Inactive for PURGE_INACTIVE_DAYS+ (default 90)
  3. No Match with application_status set (nobody saved/applied)

Safety guardrails:
  - Saved/applied jobs are never purged
  - 90-day buffer (configurable via PURGE_INACTIVE_DAYS env var)
  - Batch cap of PURGE_BATCH_LIMIT (default 5000)
  - Snapshots job title/company into TailoredResume before deletion
"""

import logging
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.match import Match
from app.models.tailored_resume import TailoredResume

logger = logging.getLogger(__name__)

PURGE_INACTIVE_DAYS = int(os.getenv("PURGE_INACTIVE_DAYS", "90"))
PURGE_BATCH_LIMIT = int(os.getenv("PURGE_BATCH_LIMIT", "5000"))
DELETE_CHUNK_SIZE = 500


def get_purgeable_job_ids(session: Session, limit: int | None = None) -> list[int]:
    """Return IDs of jobs eligible for purging."""
    cutoff = datetime.now(UTC) - timedelta(days=PURGE_INACTIVE_DAYS)
    effective_limit = limit or PURGE_BATCH_LIMIT

    # Subquery: jobs that have at least one match with application_status set
    protected = (
        select(Match.job_id)
        .where(Match.application_status.is_not(None))
        .correlate(Job)
        .scalar_subquery()
    )

    stmt = (
        select(Job.id)
        .where(
            Job.is_active.is_(False),
            Job.ingested_at <= cutoff,
            ~Job.id.in_(protected),
        )
        .order_by(Job.ingested_at.asc())
        .limit(effective_limit)
    )

    return list(session.execute(stmt).scalars().all())


def snapshot_tailored_resumes(session: Session, job_ids: list[int]) -> int:
    """Copy job title/company into snapshot fields for affected TailoredResume rows."""
    if not job_ids:
        return 0

    stmt = (
        update(TailoredResume)
        .where(
            TailoredResume.job_id.in_(job_ids),
            TailoredResume.job_title_snapshot.is_(None),
        )
        .values(
            job_title_snapshot=select(Job.title).where(Job.id == TailoredResume.job_id).correlate(TailoredResume).scalar_subquery(),
            job_company_snapshot=select(Job.company).where(Job.id == TailoredResume.job_id).correlate(TailoredResume).scalar_subquery(),
        )
    )
    result = session.execute(stmt)
    return result.rowcount


def purge_jobs(session: Session, dry_run: bool = False) -> dict:
    """Identify and delete purgeable jobs.

    Returns dict with purge statistics.
    """
    job_ids = get_purgeable_job_ids(session)

    if dry_run:
        return {
            "dry_run": True,
            "purgeable_count": len(job_ids),
            "deleted_count": 0,
        }

    if not job_ids:
        return {
            "dry_run": False,
            "purgeable_count": 0,
            "deleted_count": 0,
        }

    # Snapshot before deletion
    snapshotted = snapshot_tailored_resumes(session, job_ids)
    logger.info("Snapshotted %d tailored resume rows before purge", snapshotted)

    # Delete in chunks (CASCADE handles matches, parsed details, etc.)
    total_deleted = 0
    for i in range(0, len(job_ids), DELETE_CHUNK_SIZE):
        chunk = job_ids[i : i + DELETE_CHUNK_SIZE]
        result = session.execute(delete(Job).where(Job.id.in_(chunk)))
        total_deleted += result.rowcount

    session.commit()
    logger.info("Purged %d inactive jobs", total_deleted)

    return {
        "dry_run": False,
        "purgeable_count": len(job_ids),
        "deleted_count": total_deleted,
        "snapshotted": snapshotted,
    }


def get_purgeable_count(session: Session) -> int:
    """Quick count of purgeable jobs for admin dashboard."""
    cutoff = datetime.now(UTC) - timedelta(days=PURGE_INACTIVE_DAYS)

    protected = (
        select(Match.job_id)
        .where(Match.application_status.is_not(None))
        .correlate(Job)
        .scalar_subquery()
    )

    stmt = select(func.count(Job.id)).where(
        Job.is_active.is_(False),
        Job.ingested_at <= cutoff,
        ~Job.id.in_(protected),
    )

    return session.execute(stmt).scalar() or 0


def backfill_snapshots(session: Session) -> int:
    """One-time backfill: populate snapshot fields for all existing TailoredResume rows
    that still have a linked job.
    """
    stmt = (
        update(TailoredResume)
        .where(
            TailoredResume.job_id.is_not(None),
            TailoredResume.job_title_snapshot.is_(None),
        )
        .values(
            job_title_snapshot=select(Job.title).where(Job.id == TailoredResume.job_id).correlate(TailoredResume).scalar_subquery(),
            job_company_snapshot=select(Job.company).where(Job.id == TailoredResume.job_id).correlate(TailoredResume).scalar_subquery(),
        )
    )
    result = session.execute(stmt)
    session.commit()
    return result.rowcount
