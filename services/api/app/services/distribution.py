"""Distribution service — orchestrates job distribution to external boards."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.distribution import BoardConnection, DistributionEvent, JobDistribution
from app.models.employer import EmployerJob, EmployerProfile
from app.services.board_adapters import get_adapter

logger = logging.getLogger(__name__)


def distribute_job(
    employer_job_id: int,
    board_types: list[str] | None,
    session: Session,
) -> list[dict]:
    """Distribute a job to specified boards (or all active connections).

    Returns a list of dicts with per-board results.
    """
    job = session.get(EmployerJob, employer_job_id)
    if not job:
        raise ValueError(f"Job {employer_job_id} not found")

    employer = session.get(EmployerProfile, job.employer_id)

    # Get active board connections
    stmt = select(BoardConnection).where(
        BoardConnection.employer_id == job.employer_id,
        BoardConnection.is_active.is_(True),
    )
    if board_types:
        stmt = stmt.where(BoardConnection.board_type.in_(board_types))

    connections = list(session.execute(stmt).scalars().all())
    if not connections:
        return []

    results = []
    for conn in connections:
        result = _submit_to_board(job, conn, employer, session)
        results.append(result)

    session.commit()
    return results


def _submit_to_board(
    job: EmployerJob,
    connection: BoardConnection,
    employer: EmployerProfile | None,
    session: Session,
) -> dict:
    """Submit a single job to a single board. Creates distribution record + events."""
    adapter = get_adapter(connection.board_type)
    board_name = connection.board_name

    # Check for existing distribution
    stmt = select(JobDistribution).where(
        JobDistribution.employer_job_id == job.id,
        JobDistribution.board_connection_id == connection.id,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing and existing.status in ("live", "pending"):
        return {
            "board": board_name,
            "board_type": connection.board_type,
            "status": "already_distributed",
            "distribution_id": existing.id,
        }

    if not adapter:
        return {
            "board": board_name,
            "board_type": connection.board_type,
            "status": "failed",
            "error": f"No adapter for board type '{connection.board_type}'",
        }

    try:
        result = adapter.submit_job(job, connection)
        now = datetime.now(UTC)

        if existing:
            # Re-distribute a previously removed/failed distribution
            existing.external_job_id = result.get("external_id")
            existing.status = result.get("status", "pending")
            existing.submitted_at = now
            existing.feed_payload = result.get("payload")
            existing.error_message = None
            existing.removed_at = None
            if result.get("status") == "live":
                existing.live_at = now
            dist = existing
        else:
            dist = JobDistribution(
                employer_job_id=job.id,
                board_connection_id=connection.id,
                external_job_id=result.get("external_id"),
                status=result.get("status", "pending"),
                submitted_at=now,
                feed_payload=result.get("payload"),
            )
            if result.get("status") == "live":
                dist.live_at = now
            session.add(dist)
            session.flush()

        # Log event
        event = DistributionEvent(
            distribution_id=dist.id,
            event_type="submitted",
            event_data={
                "board_type": connection.board_type,
                "external_id": result.get("external_id"),
                "status": result.get("status"),
            },
        )
        session.add(event)

        return {
            "board": board_name,
            "board_type": connection.board_type,
            "status": result.get("status", "pending"),
            "distribution_id": dist.id,
            "external_id": result.get("external_id"),
        }
    except Exception as e:
        logger.exception("Failed to submit job %s to %s", job.id, board_name)
        # Create failed distribution record
        if existing:
            existing.status = "failed"
            existing.error_message = str(e)[:1000]
            dist = existing
        else:
            dist = JobDistribution(
                employer_job_id=job.id,
                board_connection_id=connection.id,
                status="failed",
                error_message=str(e)[:1000],
                submitted_at=datetime.now(UTC),
            )
            session.add(dist)
            session.flush()

        event = DistributionEvent(
            distribution_id=dist.id,
            event_type="error",
            event_data={"error": str(e)[:1000]},
        )
        session.add(event)

        return {
            "board": board_name,
            "board_type": connection.board_type,
            "status": "failed",
            "error": str(e)[:500],
        }


def update_distribution(employer_job_id: int, session: Session) -> list[dict]:
    """Push updates to all boards where this job is live."""
    job = session.get(EmployerJob, employer_job_id)
    if not job:
        return []

    stmt = select(JobDistribution).where(
        JobDistribution.employer_job_id == employer_job_id,
        JobDistribution.status == "live",
    )
    distributions = list(session.execute(stmt).scalars().all())

    results = []
    for dist in distributions:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        if not adapter or not conn:
            continue

        try:
            result = adapter.update_job(job, dist)
            dist.feed_payload = result.get("payload")
            event = DistributionEvent(
                distribution_id=dist.id,
                event_type="updated",
                event_data={"status": result.get("status")},
            )
            session.add(event)
            results.append({"board": conn.board_name, "status": "updated"})
        except Exception as e:
            logger.exception("Failed to update distribution %s", dist.id)
            event = DistributionEvent(
                distribution_id=dist.id,
                event_type="error",
                event_data={"error": str(e)[:1000]},
            )
            session.add(event)
            board = conn.board_name
            results.append({"board": board, "status": "error", "error": str(e)[:500]})

    session.commit()
    return results


def remove_from_boards(employer_job_id: int, session: Session) -> list[dict]:
    """Remove a job from all boards."""
    stmt = select(JobDistribution).where(
        JobDistribution.employer_job_id == employer_job_id,
        JobDistribution.status.in_(["live", "pending"]),
    )
    distributions = list(session.execute(stmt).scalars().all())

    results = []
    now = datetime.now(UTC)
    for dist in distributions:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None

        try:
            if adapter:
                adapter.remove_job(dist)
            dist.status = "removed"
            dist.removed_at = now
            event = DistributionEvent(
                distribution_id=dist.id,
                event_type="removed",
                event_data={"board_type": conn.board_type if conn else "unknown"},
            )
            session.add(event)
            bname = conn.board_name if conn else "unknown"
            results.append({"board": bname, "status": "removed"})
        except Exception as e:
            logger.exception("Failed to remove distribution %s", dist.id)
            bname = conn.board_name if conn else "unknown"
            results.append({"board": bname, "status": "error", "error": str(e)[:500]})

    session.commit()
    return results


def sync_metrics(employer_job_id: int, session: Session) -> list[dict]:
    """Pull latest metrics from all boards for a job."""
    stmt = select(JobDistribution).where(
        JobDistribution.employer_job_id == employer_job_id,
        JobDistribution.status == "live",
    )
    distributions = list(session.execute(stmt).scalars().all())

    results = []
    for dist in distributions:
        conn = session.get(BoardConnection, dist.board_connection_id)
        adapter = get_adapter(conn.board_type) if conn else None
        if not adapter or not conn:
            continue

        try:
            metrics = adapter.fetch_metrics(dist)
            dist.impressions = metrics.get("impressions", dist.impressions)
            dist.clicks = metrics.get("clicks", dist.clicks)
            dist.applications = metrics.get("applications", dist.applications)
            if "cost_spent" in metrics:
                dist.cost_spent = metrics["cost_spent"]

            conn.last_sync_at = datetime.now(UTC)
            conn.last_sync_status = "success"

            event = DistributionEvent(
                distribution_id=dist.id,
                event_type="metrics_synced",
                event_data=metrics,
            )
            session.add(event)
            results.append(
                {"board": conn.board_name, "status": "synced", "metrics": metrics}
            )
        except Exception as e:
            logger.exception("Failed to sync metrics for distribution %s", dist.id)
            if conn:
                conn.last_sync_status = "failed"
                conn.last_sync_error = str(e)[:1000]
            bname = conn.board_name if conn else "unknown"
            results.append({"board": bname, "status": "error"})

    session.commit()
    return results


def sync_all_metrics(employer_id: int, session: Session) -> list[dict]:
    """Pull metrics for all active distributions for an employer."""
    stmt = (
        select(JobDistribution)
        .join(BoardConnection)
        .where(
            BoardConnection.employer_id == employer_id,
            JobDistribution.status == "live",
        )
    )
    distributions = list(session.execute(stmt).scalars().all())

    job_ids = {d.employer_job_id for d in distributions}
    results = []
    for job_id in job_ids:
        results.extend(sync_metrics(job_id, session))
    return results
