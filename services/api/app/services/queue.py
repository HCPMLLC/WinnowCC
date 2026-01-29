import os

import redis
from rq import Queue

_redis_connection = None
_queue = None


def get_redis_connection() -> redis.Redis:
    global _redis_connection
    if _redis_connection is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_connection = redis.from_url(redis_url)
    return _redis_connection


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue("default", connection=get_redis_connection())
    return _queue
