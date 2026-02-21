"""Freshness monitor — detects and fixes stale/stuck distributions."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.distribution import (
    BoardConnection,
    DistributionEvent,
    JobDistribution,
)
from app.models.employer import EmployerJob
from app.services.board_adapters import get_adapter

logger = logging.getLogger(__name__)

# Distributions stuck in 'pending' for longer than this are retried.
PENDING_TIMEOUT_MINUTES = 30

# Maximum retry attempts for failed distributions.
MAX_RETRIES = 3

# Base delay for exponential backoff (minutes).
BACKOFF_BASE_MINUTES = 5


def run_freshness_check(session: Session) -> dict:
    """Run all freshness checks. Called by the scheduler every 5 minutes.

    Returns dict with counts of actions taken.
    """
    results = {
        "stale_removed": 0,
        "outdated_synced": 0,
        "pending_retried": 0,
        "failed_retried": 0,
        "errors": 0,
    }

    results["stale_removed"] = _remove_stale(session)
    results["outdated_synced"] = _sync_outdated(session)
    results["pending_retried"] = _retry_pending(session)
    results["failed_retried"] = _retry_failed(session)

    if any(v for k, v in results.items() if k != "errors"):
        session.commit()

    logger.info("Freshness check results: %s", results)
    return results


def _remove_stale(session: Session) -> int:
    """Remove distributions whose parent job is no longer active."""
    stmt = (
        select(JobDistribution)
        .join(EmployerJob, JobDistribution.employer_job_id == EmployerJob.id)
        .where(
            JobDistribution.status == "live",
            EmployerJob.status.notin_(["active"]),
        )
    )
    stale = list(session.execute(stmt).scalars().all())
    count = 0
    for dist in stale:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        try:
            if adapter:
                adapter.remove_job(dist)
            dist.status = "removed"
            dist.removed_at = datetime.now(UTC)
            _log_event(
                session,
                dist.id,
                "auto_removed",
                {
                    "reason": "parent_job_inactive",
                },
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to auto-remove dist %s: %s", dist.id, e)
    return count


def _sync_outdated(session: Session) -> int:
    """Push updates for distributions where the job was edited more recently."""
    stmt = (
        select(JobDistribution)
        .join(EmployerJob, JobDistribution.employer_job_id == EmployerJob.id)
        .where(
            JobDistribution.status == "live",
            EmployerJob.status == "active",
            EmployerJob.updated_at > JobDistribution.updated_at,
        )
    )
    outdated = list(session.execute(stmt).scalars().all())
    count = 0
    for dist in outdated:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        if not adapter:
            continue
        try:
            job = session.get(EmployerJob, dist.employer_job_id)
            adapter.update_job(job, dist)
            _log_event(
                session,
                dist.id,
                "auto_synced",
                {
                    "reason": "job_updated",
                },
            )
            count += 1
        except Exception as e:
            logger.warning("Failed to sync dist %s: %s", dist.id, e)
    return count


def _retry_pending(session: Session) -> int:
    """Retry distributions stuck in pending state."""
    cutoff = datetime.now(UTC) - timedelta(minutes=PENDING_TIMEOUT_MINUTES)
    stmt = select(JobDistribution).where(
        and_(
            JobDistribution.status == "pending",
            JobDistribution.submitted_at < cutoff,
        )
    )
    pending = list(session.execute(stmt).scalars().all())
    count = 0
    for dist in pending:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        if not adapter:
            continue
        job = session.get(EmployerJob, dist.employer_job_id)
        if not job or job.status != "active":
            dist.status = "removed"
            continue
        try:
            result = adapter.submit_job(job, conn)
            dist.status = result.get("status", "pending")
            dist.external_job_id = result.get("external_id")
            if result.get("status") == "live":
                dist.live_at = datetime.now(UTC)
            _log_event(
                session,
                dist.id,
                "pending_retry",
                {
                    "new_status": dist.status,
                },
            )
            count += 1
        except Exception as e:
            logger.warning("Pending retry failed for dist %s: %s", dist.id, e)
    return count


def _retry_failed(session: Session) -> int:
    """Retry failed distributions with exponential backoff (max 3 attempts)."""
    stmt = select(JobDistribution).where(
        JobDistribution.status == "failed",
    )
    failed = list(session.execute(stmt).scalars().all())
    count = 0
    for dist in failed:
        # Count previous retries
        retry_stmt = select(DistributionEvent).where(
            DistributionEvent.distribution_id == dist.id,
            DistributionEvent.event_type.in_(
                ["failed_retry", "pending_retry", "submitted"]
            ),
        )
        attempts = session.execute(retry_stmt).scalars().all()
        if len(attempts) >= MAX_RETRIES:
            continue

        # Check backoff timing
        delay = timedelta(minutes=BACKOFF_BASE_MINUTES * (2 ** len(attempts)))
        if dist.updated_at and datetime.now(UTC) - dist.updated_at < delay:
            continue

        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        if not adapter:
            continue
        job = session.get(EmployerJob, dist.employer_job_id)
        if not job or job.status != "active":
            dist.status = "removed"
            continue
        try:
            result = adapter.submit_job(job, conn)
            dist.status = result.get("status", "pending")
            dist.external_job_id = result.get("external_id")
            dist.error_message = None
            if result.get("status") == "live":
                dist.live_at = datetime.now(UTC)
            _log_event(
                session,
                dist.id,
                "failed_retry",
                {
                    "attempt": len(attempts) + 1,
                    "new_status": dist.status,
                },
            )
            count += 1
        except Exception as e:
            dist.error_message = str(e)[:1000]
            _log_event(
                session,
                dist.id,
                "failed_retry",
                {
                    "attempt": len(attempts) + 1,
                    "error": str(e)[:500],
                },
            )
            logger.warning(
                "Failed retry for dist %s (attempt %d): %s",
                dist.id,
                len(attempts) + 1,
                e,
            )
    return count


def _log_event(
    session: Session,
    distribution_id: int,
    event_type: str,
    event_data: dict,
) -> None:
    event = DistributionEvent(
        distribution_id=distribution_id,
        event_type=event_type,
        event_data=event_data,
    )
    session.add(event)
