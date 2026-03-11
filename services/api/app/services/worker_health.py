"""
Worker health and queue depth monitoring.
Provides queue stats for the admin dashboard and alerting.
"""

import logging
import os
from datetime import UTC, datetime

import redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)

# Queue names used by Winnow (must match what queue.py uses)
QUEUE_NAMES = [
    "critical",
    "default",
    "bulk",
    "low",
]


def get_redis_connection():
    """Get the Redis connection used by RQ."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


def get_queue_stats() -> dict:
    """
    Return stats for each RQ queue.

    Returns dict like:
    {
        "queues": [
            {"name": "default", "pending": 5, "started": 1, ...},
            ...
        ],
        "total_pending": 12,
        "total_failed": 2,
        "redis_connected": true,
        "checked_at": "2026-02-08T..."
    }
    """
    try:
        conn = get_redis_connection()
        conn.ping()
    except Exception as e:
        logger.error("Redis connection failed: %s", e)
        return {
            "queues": [],
            "total_pending": -1,
            "total_failed": -1,
            "redis_connected": False,
            "checked_at": datetime.now(UTC).isoformat(),
            "error": str(e),
        }

    queues_data = []
    total_pending = 0
    total_failed = 0

    for name in QUEUE_NAMES:
        try:
            q = Queue(name, connection=conn)
            pending = q.count
            started = q.started_job_registry.count
            failed = q.failed_job_registry.count
            deferred = q.deferred_job_registry.count

            queues_data.append(
                {
                    "name": name,
                    "pending": pending,
                    "started": started,
                    "failed": failed,
                    "deferred": deferred,
                }
            )

            total_pending += pending
            total_failed += failed
        except Exception as e:
            queues_data.append(
                {
                    "name": name,
                    "error": str(e),
                }
            )

    from app.services.queue import QUEUE_DEPTH_DROP, QUEUE_DEPTH_WARN

    if total_pending >= QUEUE_DEPTH_DROP:
        pressure = "critical"
    elif total_pending >= QUEUE_DEPTH_WARN:
        pressure = "elevated"
    else:
        pressure = "normal"

    return {
        "queues": queues_data,
        "total_pending": total_pending,
        "total_failed": total_failed,
        "pressure": pressure,
        "redis_connected": True,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def get_failed_jobs(queue_name: str = "default", limit: int = 20) -> list[dict]:
    """
    Return recent failed jobs for a queue.
    Useful for the admin dashboard to see what's breaking.
    """
    try:
        conn = get_redis_connection()
        q = Queue(queue_name, connection=conn)
        failed_registry = q.failed_job_registry
        job_ids = failed_registry.get_job_ids(0, limit)

        failed = []
        for job_id in job_ids:
            try:
                job = Job.fetch(job_id, connection=conn)
                failed.append(
                    {
                        "job_id": job_id,
                        "func_name": (job.func_name if job.func_name else "unknown"),
                        "enqueued_at": (
                            str(job.enqueued_at) if job.enqueued_at else None
                        ),
                        "ended_at": (str(job.ended_at) if job.ended_at else None),
                        "exc_info": (str(job.exc_info)[:500] if job.exc_info else None),
                    }
                )
            except Exception:
                failed.append(
                    {"job_id": job_id, "error": "Could not fetch job details"}
                )

        return failed
    except Exception as e:
        return [{"error": str(e)}]
