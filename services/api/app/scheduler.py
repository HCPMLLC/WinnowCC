"""Entry point for RQ Scheduler process.

Usage:
    cd services/api
    .\.venv\Scripts\Activate.ps1
    $env:SCHEDULER_ENABLED="true"
    python -m app.scheduler
"""

import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

# Load services/api/.env so configuration is available
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

from redis import Redis  # noqa: E402
from rq_scheduler import Scheduler  # noqa: E402

from app.services.scheduler_config import (  # noqa: E402
    get_scheduler_config,
    get_scheduler_enabled,
    get_scheduler_ingest_cron,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Track whether we should truly exit (e.g. user Ctrl+C or real Cloud Run shutdown)
_shutdown_requested = False


def _handle_sigterm(signum, frame):
    """Handle SIGTERM gracefully — only exit on second signal."""
    global _shutdown_requested
    if _shutdown_requested:
        logger.info("Second SIGTERM received, forcing exit.")
        sys.exit(0)
    _shutdown_requested = True
    logger.info("SIGTERM received, will shut down after current scheduler cycle.")


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


def _register_cron_jobs(scheduler: Scheduler) -> None:
    """Register all cron jobs, clearing duplicates first."""
    # Map of job_type -> (cron_string, func, queue_name)
    cron_expr = get_scheduler_ingest_cron()
    jobs_to_schedule = [
        (
            "ingest",
            cron_expr,
            "app.services.scheduled_jobs:scheduled_ingest_jobs",
            "default",
        ),
        (
            "expire_introductions",
            "0 3 * * *",
            "app.services.scheduled_jobs:scheduled_expire_introductions",
            "default",
        ),
        (
            "outreach",
            "*/15 * * * *",
            "app.services.scheduled_jobs:scheduled_process_outreach",
            "default",
        ),
        (
            "stale_check",
            "0 2 * * *",
            "app.services.scheduled_jobs:scheduled_check_stale_jobs",
            "default",
        ),
        (
            "job_purge",
            "0 4 * * 0",
            "app.services.scheduled_jobs:scheduled_purge_inactive_jobs",
            "default",
        ),
        (
            "hard_delete",
            "0 5 * * *",
            "app.services.scheduled_jobs:scheduled_hard_delete_expired",
            "default",
        ),
        (
            "weekly_digest",
            "0 7 * * 0",
            "app.services.scheduled_jobs:scheduled_send_weekly_digests",
            "low",
        ),
        (
            "promote_imports",
            "*/2 * * * *",
            "app.services.scheduled_jobs:scheduled_promote_queued_imports",
            "default",
        ),
    ]

    # Cancel all existing scheduled jobs to avoid duplicates
    job_types = {j[0] for j in jobs_to_schedule}
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") in job_types:
            scheduler.cancel(job)
            logger.info(
                f"Cancelled existing job: {job.meta['scheduled_job_type']} ({job.id})"
            )

    # Register all cron jobs
    for job_type, cron_string, func, queue_name in jobs_to_schedule:
        registered = scheduler.cron(
            cron_string=cron_string,
            func=func,
            queue_name=queue_name,
            meta={"scheduled_job_type": job_type},
        )
        logger.info(f"Registered {job_type}: {registered.id} (cron: {cron_string})")


def main():
    global _shutdown_requested

    # Intercept SIGTERM before rq_scheduler can register its own handler
    signal.signal(signal.SIGTERM, _handle_sigterm)

    # Cloud Run requires a listening port for health checks
    threading.Thread(target=_start_health_server, daemon=True).start()

    config = get_scheduler_config()
    logger.info(f"Scheduler configuration: {config}")

    if not get_scheduler_enabled():
        logger.error("Scheduler is disabled. Set SCHEDULER_ENABLED=true to enable.")
        sys.exit(1)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Restart loop: if scheduler.run() exits (e.g. transient signal, Redis blip),
    # reconnect and restart instead of letting the process die.
    while not _shutdown_requested:
        try:
            redis_conn = Redis.from_url(redis_url)
            redis_conn.ping()
            logger.info("Redis connection established.")

            scheduler = Scheduler(connection=redis_conn, queue_name="default")
            _register_cron_jobs(scheduler)

            logger.info("Scheduler running. Will auto-restart if interrupted.")

            # Re-apply our SIGTERM handler since Scheduler.__init__ or run()
            # may override it with its own
            signal.signal(signal.SIGTERM, _handle_sigterm)

            scheduler.run()

            # scheduler.run() exited — rq_scheduler caught a signal internally
            if _shutdown_requested:
                logger.info("Shutdown requested, exiting.")
                break
            logger.warning("Scheduler exited unexpectedly, restarting in 5s...")
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt, exiting.")
            break
        except Exception:
            logger.exception("Scheduler crashed, restarting in 10s...")
            time.sleep(10)
            continue

        time.sleep(5)

    logger.info("Scheduler process stopped.")


if __name__ == "__main__":
    main()
