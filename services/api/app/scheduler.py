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


def main():
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

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    # Run the scheduler
    scheduler.run()


if __name__ == "__main__":
    main()
