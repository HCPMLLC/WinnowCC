"""Recruiter migration router — upload, detect, start, preview, rollback imports."""

import logging
import os
import shutil
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.migration import MigrationJob
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_activity import RecruiterActivity
from app.models.user import User
from app.services.auth import get_recruiter_profile, require_recruiter
from app.services.migration.import_engine import get_preview
from app.services.migration.platform_detector import detect_platform
from app.services.migration.recruiter_import_engine import (
    rollback_recruiter_migration,
    run_recruiter_migration,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/recruiter/migration",
    tags=["recruiter-migration"],
)

UPLOAD_DIR = os.getenv("MIGRATION_UPLOAD_DIR", "/tmp/winnow_migrations")


@router.post("/upload")
async def upload_recruiter_migration_file(
    file: UploadFile,
    source_platform: str = Query("auto"),
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Upload an export file for recruiter CRM migration.

    Supports CSV, JSON, ZIP, and XLSX files from Bullhorn, Recruit CRM,
    CATSOne, Zoho Recruit, or generic CSV exports.
    """
    allowed_extensions = (".csv", ".json", ".zip", ".xlsx")
    if not file.filename or not any(
        file.filename.lower().endswith(ext) for ext in allowed_extensions
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Supported file types: {', '.join(allowed_extensions)}",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    dest = os.path.join(UPLOAD_DIR, f"{user.id}_{file_id}_{file.filename}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    detection = detect_platform(dest)
    platform = source_platform if source_platform != "auto" else detection["platform"]

    job = MigrationJob(
        user_id=user.id,
        source_platform=platform,
        source_platform_detected=detection["platform"],
        status="pending",
        source_file_path=dest,
        config_json={
            "original_filename": file.filename,
            "detection": detection,
            "recruiter_profile_id": profile.id,
        },
    )
    db.add(job)
    db.flush()

    # Log activity
    activity = RecruiterActivity(
        recruiter_profile_id=profile.id,
        user_id=user.id,
        activity_type="migration_started",
        subject=f"Started migration from {platform}",
        activity_metadata={
            "migration_job_id": job.id,
            "platform": platform,
            "file_name": file.filename,
        },
    )
    db.add(activity)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.id,
        "detected_platform": detection["platform"],
        "confidence": detection["confidence"],
        "evidence": detection["evidence"],
        "entity_types_found": detection["entity_types_found"],
        "row_count": detection["row_count"],
        "status": "pending",
    }


@router.get("/{job_id}")
def get_recruiter_migration_status(
    job_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Get recruiter migration job status and stats."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    return {
        "id": job.id,
        "source_platform": job.source_platform,
        "source_platform_detected": job.source_platform_detected,
        "status": job.status,
        "stats": job.stats_json,
        "errors": job.error_log,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
    }


@router.post("/{job_id}/start")
def start_recruiter_migration(
    job_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Start processing a pending recruiter migration job."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")
    if job.status not in ("pending", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start job in {job.status} status",
        )

    # Resume archives — agency tier only, processed async via RQ
    if job.source_platform_detected == "resume_archive":
        profile = db.execute(
            select(RecruiterProfile).where(
                RecruiterProfile.user_id == user.id,
            )
        ).scalar_one_or_none()
        if not profile or profile.subscription_tier != "agency":
            raise HTTPException(
                status_code=403,
                detail="Bulk resume archive import is available on the Agency plan. "
                "Upgrade at /recruiter/pricing to unlock this feature.",
            )

        from app.services.migration.resume_migration_engine import (
            run_resume_migration,
        )
        from app.services.queue import get_queue

        job.status = "importing"
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            queue = get_queue("low")
            queue.enqueue(run_resume_migration, job_id, job_timeout="4h")
        except Exception:
            logger.exception("Failed to enqueue resume migration job %d", job_id)
            job.status = "failed"
            job.error_log = [
                {"error": "Failed to enqueue job. Is Redis running?", "fatal": True}
            ]
            db.commit()
            raise HTTPException(
                status_code=503,
                detail="Queue not available. Ensure Redis is running.",
            ) from None

        return {
            "job_id": job_id,
            "status": "importing",
            "message": "Resume migration queued for background processing. "
            "You'll receive an email when it's complete.",
        }

    return run_recruiter_migration(job_id, db)


@router.get("/{job_id}/preview")
def preview_recruiter_migration(
    job_id: int,
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Preview imported entities for a recruiter migration job."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    return get_preview(job_id, db, limit)


@router.post("/{job_id}/rollback")
def rollback_recruiter(
    job_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Rollback a recruiter migration — delete all imported entities."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    try:
        return rollback_recruiter_migration(job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{job_id}/errors")
def get_recruiter_migration_errors(
    job_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Get error log for a recruiter migration job."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    return {"job_id": job.id, "errors": job.error_log or []}


@router.get("/history/list")
def recruiter_migration_history(
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """List all migration jobs for the current recruiter."""
    jobs = (
        db.execute(
            select(MigrationJob)
            .where(MigrationJob.user_id == user.id)
            .order_by(MigrationJob.created_at.desc())
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": j.id,
            "source_platform": j.source_platform,
            "status": j.status,
            "stats": j.stats_json,
            "created_at": j.created_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]
