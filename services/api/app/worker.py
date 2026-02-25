import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from rq import SimpleWorker, Worker

# Load services/api/.env so DB_URL is available for jobs.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(redis_url)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format, *args):
        pass  # suppress request logs


def _start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    # Cloud Run requires a listening port for health checks
    threading.Thread(target=_start_health_server, daemon=True).start()

    # Pre-import heavy modules and warm up SQLAlchemy mappers so they
    # don't timeout on the first RQ job (Cloud Run cold-start issue).
    try:
        import app.models  # noqa: F401 — triggers pgvector/numpy import
        from sqlalchemy import select, text
        from app.db.session import get_session_factory
        from app.models.user import User
        session = get_session_factory()()
        session.execute(text("SELECT 1"))  # warm up connection pool
        session.execute(select(User).limit(1))  # configure all ORM mappers
        session.close()
    except Exception:
        pass

    worker_cls = SimpleWorker if os.name == "nt" else Worker
    worker = worker_cls(["default"], connection=redis_conn)
    worker.work()
