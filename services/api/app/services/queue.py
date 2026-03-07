import logging
import os
import threading

import redis
from rq import Queue, Retry

logger = logging.getLogger(__name__)

_redis_connection = None
_queues: dict[str, Queue] = {}

# Priority order (highest first). Workers check these in order so jobs on
# higher-priority queues are always processed before lower-priority ones.
QUEUE_NAMES = ["critical", "default", "bulk", "low"]

# Per-queue retry policies: (max_retries, backoff_intervals)
_RETRY_POLICIES: dict[str, tuple[int, list[int]]] = {
    "critical": (3, [5, 15, 30]),
    "default": (3, [10, 30, 60]),
    "bulk": (2, [30, 120]),
    "low": (2, [60, 300]),
}

# Auto-purge failed jobs after 2 days
_FAILURE_TTL = 172800


def _wake_worker() -> None:
    """Fire-and-forget ping to the worker's health endpoint.

    On Cloud Run the worker service may be slow to pick up new jobs if
    its instances are cold.  Hitting its health endpoint encourages
    Cloud Run to keep the instance warm.

    Set WORKER_HEALTH_URL to the worker's internal Cloud Run URL, e.g.
    https://winnow-worker-xxxxx-uc.a.run.app
    For authenticated services, also set WORKER_HEALTH_TOKEN (or use
    a Google ID token via metadata server).
    """
    worker_url = os.getenv("WORKER_HEALTH_URL")
    if not worker_url:
        return
    try:
        import urllib.request

        req = urllib.request.Request(worker_url, method="GET")
        token = os.getenv("WORKER_HEALTH_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        elif os.getenv("K_SERVICE"):
            # Running on Cloud Run — fetch ID token from metadata server
            try:
                meta_url = (
                    "http://metadata.google.internal/computeMetadata/v1/"
                    f"instance/service-accounts/default/identity?audience={worker_url}"
                )
                meta_req = urllib.request.Request(
                    meta_url, headers={"Metadata-Flavor": "Google"}
                )
                with urllib.request.urlopen(meta_req, timeout=3) as resp:
                    id_token = resp.read().decode()
                req.add_header("Authorization", f"Bearer {id_token}")
            except Exception:
                pass  # Fall through and try without auth
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        logger.debug("Worker wake ping failed (non-fatal)", exc_info=True)


class RetryQueue(Queue):
    """Queue subclass that injects retry and failure_ttl defaults."""

    def enqueue(self, *args, **kwargs):
        if "retry" not in kwargs:
            max_retries, intervals = _RETRY_POLICIES.get(self.name, (3, [10, 30, 60]))
            kwargs["retry"] = Retry(max=max_retries, interval=intervals)
        if "failure_ttl" not in kwargs:
            kwargs["failure_ttl"] = _FAILURE_TTL
        result = super().enqueue(*args, **kwargs)
        # Wake the worker in a background thread (non-blocking)
        threading.Thread(target=_wake_worker, daemon=True).start()
        return result


def get_redis_connection() -> redis.Redis:
    global _redis_connection
    if _redis_connection is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_connection = redis.from_url(redis_url)
    return _redis_connection


def get_queue(name: str = "default") -> RetryQueue:
    if name not in _queues:
        _queues[name] = RetryQueue(name, connection=get_redis_connection())
    return _queues[name]
