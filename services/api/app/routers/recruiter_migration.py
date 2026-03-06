"""Recruiter migration router — upload, detect, start, preview, rollback imports."""

import logging
import os
import tempfile
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

    # Read file bytes and write to temp for platform detection
    contents = await file.read()
    file_id = uuid.uuid4().hex[:12]
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(file.filename)[1],
        prefix=f"{user.id}_{file_id}_",
    )
    try:
        tmp.write(contents)
        tmp.close()

        detection = detect_platform(tmp.name)
        platform = (
            source_platform if source_platform != "auto" else detection["platform"]
        )

        # For resume archives, stage to cloud storage so async workers
        # can access the file even after this container restarts.
        # CRM imports (Bullhorn, etc.) run synchronously and use a local path.
        if platform == "resume_archive" or detection["platform"] == "resume_archive":
            from app.services.storage import upload_bytes

            unique_name = f"{user.id}_{file_id}_{file.filename}"
            stored_path = upload_bytes(contents, "staging/migration_zips/", unique_name)
        else:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            local_dest = os.path.join(
                UPLOAD_DIR, f"{user.id}_{file_id}_{file.filename}"
            )
            with open(local_dest, "wb") as f:
                f.write(contents)
            stored_path = local_dest
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    job = MigrationJob(
        user_id=user.id,
        source_platform=platform,
        source_platform_detected=detection["platform"],
        status="pending",
        source_file_path=stored_path,
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
    """Get recruiter migration job status and stats, including queue info."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    result = {
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

    # Add queue info for resume archive imports
    if job.source_platform == "resume_archive" and job.status in (
        "queued",
        "importing",
    ):
        from app.services.batch_upload import get_import_queue_info

        result.update(get_import_queue_info(db, job.id))

        # If importing but no batch created yet, the expand_zip_batch_job
        # hasn't been picked up by a worker. Detect stale state.
        if job.status == "importing" and not job.stats_json:
            from datetime import timedelta

            age = datetime.now(UTC) - (job.started_at or job.created_at)
            if age > timedelta(minutes=5):
                result["worker_stale"] = True
                result["stale_minutes"] = int(age.total_seconds() / 60)

    return result


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

        from app.models.upload_batch import UploadBatch
        from app.services.batch_upload import (
            expand_zip_batch_job,
            get_import_queue_info,
        )
        from app.services.queue import get_queue

        # System-wide gate: only 1 large ZIP import at a time
        active_import = db.execute(
            select(MigrationJob).where(
                MigrationJob.status == "importing",
                MigrationJob.source_platform == "resume_archive",
                MigrationJob.id != job.id,
            )
        ).scalar_one_or_none()

        active_batch = None
        if not active_import:
            active_batch = db.execute(
                select(UploadBatch).where(
                    UploadBatch.batch_type == "recruiter_resume_zip",
                    UploadBatch.status.in_(["pending", "processing"]),
                )
            ).scalar_one_or_none()

        if active_import or active_batch:
            # Another large import is active — queue this one
            job.status = "queued"
            job.queued_at = datetime.now(UTC)
            db.commit()

            queue_info = get_import_queue_info(db, job.id)
            return {
                "job_id": job_id,
                "status": "queued",
                "message": "Another import is in progress. "
                "Your import has been queued.",
                **queue_info,
            }

        # No active import — start immediately
        job.status = "importing"
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            queue = get_queue("low")
            queue.enqueue(
                expand_zip_batch_job,
                user_id=user.id,
                owner_profile_id=profile.id,
                zip_stored_path=job.source_file_path,
                migration_job_id=job.id,
                job_timeout="30m",
            )
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
