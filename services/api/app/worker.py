import os
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from rq import SimpleWorker, Worker

# Load services/api/.env so DB_URL is available for jobs.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(redis_url)

if __name__ == "__main__":
    worker_cls = SimpleWorker if os.name == "nt" else Worker
    worker = worker_cls(["default"], connection=redis_conn)
    worker.work()
