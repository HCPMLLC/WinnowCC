"""
Admin observability endpoints.
Provides queue stats, failed jobs, and system health overview.
"""

import logging
import os
import platform
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.worker_health import get_failed_jobs, get_queue_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/observability", tags=["admin-observability"])


def _verify_admin(admin_token: str = Query(..., alias="admin_token")):
    """Verify admin access via token."""
    expected = os.environ.get("ADMIN_TOKEN", "")
    if admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health")
def system_health(
    _=Depends(_verify_admin),  # noqa: B008
    db: Session = Depends(get_session),  # noqa: B008
):
    """
    Comprehensive system health check.
    Returns status of: API, database, Redis, and queue depths.
    """
    health: dict = {
        "api": {"status": "ok"},
        "checked_at": datetime.now(UTC).isoformat(),
    }

    # Database check
    try:
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        health["database"] = {"status": "ok"}
    except Exception as e:
        health["database"] = {"status": "error", "detail": str(e)[:200]}

    # Redis + queue stats
    queue_stats = get_queue_stats()
    health["redis"] = {
        "status": "ok" if queue_stats["redis_connected"] else "error",
    }
    health["queues"] = queue_stats

    # System info
    health["system"] = {
        "python_version": platform.python_version(),
        "environment": os.environ.get("ENV", "dev"),
    }

    return health


@router.get("/queues")
def queue_overview(_=Depends(_verify_admin)):  # noqa: B008
    """Return queue depths and stats for all RQ queues."""
    return get_queue_stats()


@router.get("/queues/{queue_name}/failed")
def failed_jobs(
    queue_name: str,
    limit: int = Query(default=20, le=100),  # noqa: B008
    _=Depends(_verify_admin),  # noqa: B008
):
    """Return recent failed jobs for a specific queue."""
    return get_failed_jobs(queue_name, limit)


@router.post("/queues/{queue_name}/retry-all")
def retry_failed_jobs(
    queue_name: str,
    _=Depends(_verify_admin),  # noqa: B008
):
    """
    Retry all failed jobs in a queue.
    Moves them from the failed registry back to the queue.
    """
    from rq import Queue

    from app.services.worker_health import get_redis_connection

    try:
        conn = get_redis_connection()
        q = Queue(queue_name, connection=conn)
        failed_registry = q.failed_job_registry
        job_ids = failed_registry.get_job_ids()
        retried = 0

        for job_id in job_ids:
            try:
                failed_registry.requeue(job_id)
                retried += 1
            except Exception:
                pass

        return {
            "queue": queue_name,
            "retried": retried,
            "total_failed": len(job_ids),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
