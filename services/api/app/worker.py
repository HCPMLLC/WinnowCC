import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn

from dotenv import load_dotenv
from redis import Redis
from rq import SimpleWorker, Worker

logger = logging.getLogger(__name__)

# Load services/api/.env so DB_URL is available for jobs.
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(redis_url)


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread so pressure POSTs don't block health GETs."""

    daemon_threads = True


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        if self.path == "/_scale/pressure":
            # Hold the connection open for 55s to create Cloud Run concurrency pressure.
            # With --concurrency=1, this forces Cloud Run to spin up another instance.
            time.sleep(55)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"pressure_held"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress request logs


def _start_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = _ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    # Cloud Run requires a listening port for health checks
    threading.Thread(target=_start_health_server, daemon=True).start()

    # Pre-import heavy modules and warm up SQLAlchemy mappers so they
    # don't timeout on the first RQ job (Cloud Run cold-start issue).
    try:
        from sqlalchemy import select, text

        import app.models  # noqa: F401 — triggers pgvector/numpy import
        from app.db.session import get_session_factory
        from app.models.user import User

        session = get_session_factory()()
        session.execute(text("SELECT 1"))  # warm up connection pool
        session.execute(select(User).limit(1))  # configure all ORM mappers
        session.close()
    except Exception:
        pass

    from app.services.queue import QUEUE_NAMES

    def _mark_running_ingestions_failed(signum, frame):
        """On SIGTERM, mark any in-progress ingestion runs as failed before exit."""
        logger.info("SIGTERM received — marking in-progress ingestion runs as failed")
        try:
            from datetime import UTC, datetime

            from sqlalchemy import update

            from app.models.job_run import JobRun

            sess = get_session_factory()()
            result = sess.execute(
                update(JobRun)
                .where(
                    JobRun.job_type == "scheduled_ingest",
                    JobRun.status == "running",
                )
                .values(
                    status="failed",
                    error_message="Worker shutdown (SIGTERM) during ingestion",
                    finished_at=datetime.now(UTC),
                )
            )
            sess.commit()
            sess.close()
            if result.rowcount:
                logger.info(f"Marked {result.rowcount} running ingestion(s) as failed")
        except Exception:
            logger.exception("Failed to mark ingestion runs on shutdown")
        raise SystemExit(0)

    if os.name != "nt":
        signal.signal(signal.SIGTERM, _mark_running_ingestions_failed)

    worker_cls = SimpleWorker if os.name == "nt" else Worker
    worker = worker_cls(QUEUE_NAMES, connection=redis_conn)
    worker.work()
