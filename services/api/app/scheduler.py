"""Entry point for RQ Scheduler process.

Usage:
    cd services/api
    .\.venv\Scripts\Activate.ps1
    $env:SCHEDULER_ENABLED="true"
    python -m app.scheduler
"""

import logging
import os
import sys
import threading
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


def main():
    # Cloud Run requires a listening port for health checks
    threading.Thread(target=_start_health_server, daemon=True).start()

    config = get_scheduler_config()
    logger.info(f"Scheduler configuration: {config}")

    if not get_scheduler_enabled():
        logger.error("Scheduler is disabled. Set SCHEDULER_ENABLED=true to enable.")
        sys.exit(1)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_conn = Redis.from_url(redis_url)

    scheduler = Scheduler(connection=redis_conn, queue_name="default")

    # Clear existing scheduled jobs to avoid duplicates on restart
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") == "ingest":
            scheduler.cancel(job)
            logger.info(f"Cancelled existing scheduled job: {job.id}")

    # Get cron expression
    cron_expr = get_scheduler_ingest_cron()

    # Schedule the job ingestion
    job = scheduler.cron(
        cron_string=cron_expr,
        func="app.services.scheduled_jobs:scheduled_ingest_jobs",
        queue_name="default",
        meta={"scheduled_job_type": "ingest"},
    )

    logger.info(f"Scheduled job ingestion registered: {job.id}")
    logger.info(f"Cron schedule: {cron_expr}")

    # Schedule introduction expiration (daily at 3am UTC)
    intro_job = scheduler.cron(
        cron_string="0 3 * * *",
        func="app.services.scheduled_jobs:scheduled_expire_introductions",
        queue_name="default",
        meta={"scheduled_job_type": "expire_introductions"},
    )
    logger.info(f"Scheduled introduction expiration registered: {intro_job.id}")

    # Schedule outreach processing (every 15 minutes)
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") == "outreach":
            scheduler.cancel(job)
            logger.info(f"Cancelled existing outreach job: {job.id}")

    outreach_job = scheduler.cron(
        cron_string="*/15 * * * *",
        func="app.services.scheduled_jobs:scheduled_process_outreach",
        queue_name="default",
        meta={"scheduled_job_type": "outreach"},
    )
    logger.info(f"Scheduled outreach processing registered: {outreach_job.id}")

    # Schedule stale job check (daily at 2am UTC)
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") == "stale_check":
            scheduler.cancel(job)
            logger.info(f"Cancelled existing stale check job: {job.id}")

    stale_job = scheduler.cron(
        cron_string="0 2 * * *",
        func="app.services.scheduled_jobs:scheduled_check_stale_jobs",
        queue_name="default",
        meta={"scheduled_job_type": "stale_check"},
    )
    logger.info(f"Scheduled stale job check registered: {stale_job.id}")

    # Schedule inactive job purge (weekly on Sunday at 4am UTC)
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") == "job_purge":
            scheduler.cancel(job)
            logger.info(f"Cancelled existing job purge: {job.id}")

    purge_job = scheduler.cron(
        cron_string="0 4 * * 0",
        func="app.services.scheduled_jobs:scheduled_purge_inactive_jobs",
        queue_name="default",
        meta={"scheduled_job_type": "job_purge"},
    )
    logger.info(f"Scheduled job purge registered: {purge_job.id}")

    # Schedule hard-delete of expired soft-deleted files (daily at 5am UTC)
    for job in scheduler.get_jobs():
        if hasattr(job, "meta") and job.meta.get("scheduled_job_type") == "hard_delete":
            scheduler.cancel(job)
            logger.info(f"Cancelled existing hard-delete job: {job.id}")

    hard_delete_job = scheduler.cron(
        cron_string="0 5 * * *",
        func="app.services.scheduled_jobs:scheduled_hard_delete_expired",
        queue_name="default",
        meta={"scheduled_job_type": "hard_delete"},
    )
    logger.info(f"Scheduled hard-delete registered: {hard_delete_job.id}")

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    # Run the scheduler
    scheduler.run()


if __name__ == "__main__":
    main()
