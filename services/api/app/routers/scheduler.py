"""Admin API endpoints for scheduler management."""

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job_run import JobRun
from app.models.user import User
from app.services.auth import require_admin_user
from app.services.queue import get_queue, get_redis_connection
from app.services.scheduler_config import get_scheduler_config

router = APIRouter(prefix="/api/admin/scheduler", tags=["admin-scheduler"])


class ScheduledTask(BaseModel):
    name: str
    cron: str
    description: str


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    ingest_cron: str
    default_search: str
    default_location: str
    job_sources: list[str]
    scheduled_tasks: list[ScheduledTask]


class SchedulerTriggerResponse(BaseModel):
    message: str
    job_id: str


class SchedulerRunResponse(BaseModel):
    id: int
    job_type: str
    status: str
    error_message: str | None
    finished_at: datetime | None
    jobs_ingested: int | None
    created_at: datetime
    updated_at: datetime


class IngestionProgressResponse(BaseModel):
    running: bool
    run_id: int | None = None
    completed_sources: int = 0
    total_sources: int = 0
    percent: int = 0
    jobs_so_far: int = 0


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
) -> SchedulerStatusResponse:
    """Get current scheduler configuration."""
    config = get_scheduler_config()
    job_sources = [
        s.strip()
        for s in os.getenv("JOB_SOURCES", "remotive,themuse").split(",")
        if s.strip()
    ]
    scheduled_tasks = [
        ScheduledTask(
            name="Job Ingestion",
            cron=config["ingest_cron"],
            description="Fetch new jobs from all configured sources",
        ),
        ScheduledTask(
            name="Introduction Expiration",
            cron="0 3 * * *",
            description="Expire stale introductions daily at 3am UTC",
        ),
        ScheduledTask(
            name="Outreach Processing",
            cron="*/15 * * * *",
            description="Process pending outreach messages every 15 minutes",
        ),
    ]
    return SchedulerStatusResponse(
        **config,
        job_sources=job_sources,
        scheduled_tasks=scheduled_tasks,
    )


@router.post("/trigger", response_model=SchedulerTriggerResponse)
def trigger_ingestion(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
) -> SchedulerTriggerResponse:
    """Manually trigger a job ingestion run."""
    queue = get_queue()

    # Import the function path for RQ
    job = queue.enqueue(
        "app.services.scheduled_jobs.scheduled_ingest_jobs",
    )

    return SchedulerTriggerResponse(
        message="Job ingestion triggered",
        job_id=job.id,
    )


@router.get("/progress", response_model=IngestionProgressResponse)
def get_ingestion_progress(
    session: Session = Depends(get_session),  # noqa: B008
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
) -> IngestionProgressResponse:
    """Get progress of the currently running ingestion job."""
    # Find the latest running ingestion run
    stmt = (
        select(JobRun)
        .where(JobRun.job_type == "scheduled_ingest", JobRun.status == "running")
        .order_by(JobRun.created_at.desc())
        .limit(1)
    )
    run = session.execute(stmt).scalar_one_or_none()
    if not run:
        return IngestionProgressResponse(running=False)

    # Read progress from Redis
    try:
        conn = get_redis_connection()
        raw = conn.get(f"ingestion:{run.id}:progress")
        if raw:
            data = json.loads(raw)
            total = data.get("total_sources", 0)
            completed = data.get("completed_sources", 0)
            percent = round((completed / total) * 100) if total > 0 else 0
            return IngestionProgressResponse(
                running=True,
                run_id=run.id,
                completed_sources=completed,
                total_sources=total,
                percent=percent,
                jobs_so_far=data.get("jobs_so_far", 0),
            )
    except Exception:
        pass

    # Running but no Redis data yet
    return IngestionProgressResponse(running=True, run_id=run.id)


@router.get("/runs", response_model=list[SchedulerRunResponse])
def get_scheduler_runs(
    limit: int = 20,
    session: Session = Depends(get_session),  # noqa: B008
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
) -> list[SchedulerRunResponse]:
    """Get recent scheduler run history."""
    stmt = (
        select(JobRun)
        .where(JobRun.job_type == "scheduled_ingest")
        .order_by(JobRun.created_at.desc())
        .limit(limit)
    )
    runs = session.execute(stmt).scalars().all()

    return [
        SchedulerRunResponse(
            id=run.id,
            job_type=run.job_type,
            status=run.status,
            error_message=run.error_message,
            finished_at=run.finished_at,
            jobs_ingested=run.jobs_ingested,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        for run in runs
    ]
