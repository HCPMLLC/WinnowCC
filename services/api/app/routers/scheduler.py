"""Admin API endpoints for scheduler management."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job_run import JobRun
from app.models.user import User
from app.services.auth import require_admin_user
from app.services.queue import get_queue
from app.services.scheduler_config import get_scheduler_config

router = APIRouter(prefix="/api/admin/scheduler", tags=["admin-scheduler"])


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    ingest_cron: str
    default_search: str
    default_location: str


class SchedulerTriggerResponse(BaseModel):
    message: str
    job_id: str


class SchedulerRunResponse(BaseModel):
    id: int
    job_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(
    admin: User = Depends(require_admin_user),
) -> SchedulerStatusResponse:
    """Get current scheduler configuration."""
    config = get_scheduler_config()
    return SchedulerStatusResponse(**config)


@router.post("/trigger", response_model=SchedulerTriggerResponse)
def trigger_ingestion(
    admin: User = Depends(require_admin_user),
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


@router.get("/runs", response_model=list[SchedulerRunResponse])
def get_scheduler_runs(
    limit: int = 20,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
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
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        for run in runs
    ]
