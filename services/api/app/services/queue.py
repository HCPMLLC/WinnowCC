import os

import redis
from rq import Queue, Retry

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

# Auto-purge failed jobs after 7 days
_FAILURE_TTL = 604800


class RetryQueue(Queue):
    """Queue subclass that injects retry and failure_ttl defaults."""

    def enqueue(self, *args, **kwargs):
        if "retry" not in kwargs:
            max_retries, intervals = _RETRY_POLICIES.get(
                self.name, (3, [10, 30, 60])
            )
            kwargs["retry"] = Retry(max=max_retries, interval=intervals)
        if "failure_ttl" not in kwargs:
            kwargs["failure_ttl"] = _FAILURE_TTL
        return super().enqueue(*args, **kwargs)


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
