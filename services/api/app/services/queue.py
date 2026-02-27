import os

import redis
from rq import Queue

_redis_connection = None
_queues: dict[str, Queue] = {}

# Priority order (highest first). Workers check these in order so jobs on
# higher-priority queues are always processed before lower-priority ones.
QUEUE_NAMES = ["critical", "default", "bulk", "low"]


def get_redis_connection() -> redis.Redis:
    global _redis_connection
    if _redis_connection is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_connection = redis.from_url(redis_url)
    return _redis_connection


def get_queue(name: str = "default") -> Queue:
    if name not in _queues:
        _queues[name] = Queue(name, connection=get_redis_connection())
    return _queues[name]
