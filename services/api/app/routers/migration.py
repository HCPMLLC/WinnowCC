"""Migration router — upload, detect, start, preview, rollback imports."""

import logging
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.migration import MigrationJob
from app.models.user import User
from app.services.auth import require_employer
from app.services.migration.import_engine import (
    get_preview,
    rollback_migration,
    run_migration,
)
from app.services.migration.platform_detector import detect_platform

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/migration",
    tags=["migration"],
)

UPLOAD_DIR = os.getenv("MIGRATION_UPLOAD_DIR", "/tmp/winnow_migrations")


@router.post("/upload")
async def upload_migration_file(
    file: UploadFile,
    source_platform: str = Query("auto"),
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Upload an export file for migration.

    Supports CSV, JSON, ZIP, and XLSX files.
    Detects the source platform and creates a migration job.
    """
    allowed_extensions = (".csv", ".json", ".zip", ".xlsx")
    if not file.filename or not any(
        file.filename.lower().endswith(ext) for ext in allowed_extensions
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Supported file types: {', '.join(allowed_extensions)}",
        )

    # Save uploaded file
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    dest = os.path.join(UPLOAD_DIR, f"{user.id}_{file_id}_{file.filename}")

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Detect platform
    detection = detect_platform(dest)

    platform = source_platform if source_platform != "auto" else detection["platform"]

    # Create migration job
    job = MigrationJob(
        user_id=user.id,
        source_platform=platform,
        source_platform_detected=detection["platform"],
        status="pending",
        source_file_path=dest,
        config_json={
            "original_filename": file.filename,
            "detection": detection,
        },
    )
    db.add(job)
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
def get_migration_status(
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Get migration job status and stats."""
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
def start_migration(
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Start processing a pending migration job."""
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

    result = run_migration(job_id, db)
    return result


@router.get("/{job_id}/preview")
def preview_migration(
    job_id: int,
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Preview imported entities for a migration job."""
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
def rollback(
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Rollback a migration — delete all imported entities."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    try:
        return rollback_migration(job_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{job_id}/errors")
def get_errors(
    job_id: int,
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """Get error log for a migration job."""
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
def migration_history(
    user: User = Depends(require_employer),
    db: Session = Depends(get_session),
):
    """List all migration jobs for the current user."""
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
