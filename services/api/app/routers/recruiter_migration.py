"""Recruiter migration router — upload, detect, start, preview, rollback imports."""

import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel
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


def _run_migration_worker(migration_job_id: int) -> None:
    """RQ worker entry point for CRM migration jobs."""
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        run_recruiter_migration(migration_job_id, session)
    finally:
        session.close()


def _process_resume_archive_sync(
    job: MigrationJob,
    user: User,
    profile: RecruiterProfile,
    db: Session,
) -> dict:
    """Process a small resume ZIP synchronously within the HTTP request.

    For archives with ≤50 files this completes in seconds, avoiding the
    dependency on the background RQ worker picking up the job.
    """
    from app.services.batch_upload import (
        create_upload_batch_from_zip,
        process_batch_resume_file,
    )

    job.status = "importing"
    job.started_at = datetime.now(UTC)
    db.commit()

    try:
        result = create_upload_batch_from_zip(
            user_id=user.id,
            owner_profile_id=profile.id,
            zip_stored_path=job.source_file_path,
            session=db,
            enqueue_workers=False,
        )
        batch_id = result["batch_id"]

        job.stats_json = {"batch_id": batch_id, "status": "processing"}
        db.commit()

        # Process each file inline instead of via RQ
        from app.models.upload_batch import UploadBatchFile

        batch_files = (
            db.execute(
                select(UploadBatchFile)
                .where(UploadBatchFile.batch_id == batch_id)
                .order_by(UploadBatchFile.file_index)
            )
            .scalars()
            .all()
        )

        for bf in batch_files:
            try:
                process_batch_resume_file(bf.id, batch_id, profile.id)
            except Exception:
                logger.warning(
                    "Sync resume process failed for file %s", bf.original_filename,
                    exc_info=True,
                )

        # Finalize
        from app.services.batch_upload import _finalize_batch

        _finalize_batch(db, batch_id, "completed")

        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        job.stats_json = {"batch_id": batch_id, "status": "completed"}
        db.commit()

        return {
            "job_id": job.id,
            "status": "completed",
            "message": f"Successfully processed {len(batch_files)} resume files.",
        }

    except Exception as exc:
        logger.exception("Sync resume archive processing failed for job %d", job.id)
        job.status = "failed"
        job.error_log = [{"error": str(exc)[:500], "fatal": True}]
        job.updated_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Resume processing failed: {exc}",
        ) from None


@router.get("/upload-url")
def get_signed_upload_url(
    filename: str = Query(...),
    user: User = Depends(require_recruiter),
):
    """Get a signed GCS URL for direct browser upload.

    Used for large files (1+ GB) that exceed Cloud Run's
    32 MB request body limit. Returns None fields when GCS
    is disabled (local dev falls back to direct upload).
    """
    from app.services.storage import generate_signed_upload_url

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{user.id}_{file_id}_{filename}"
    result = generate_signed_upload_url(
        "staging/migration_zips/", safe_name,
    )
    if not result:
        return {
            "signed_url": None,
            "gcs_path": None,
            "message": "Direct upload not available; "
            "use standard upload endpoint.",
        }
    return {
        "signed_url": result["url"],
        "gcs_path": result["gcs_path"],
    }


class RegisterUploadRequest(BaseModel):
    gcs_path: str
    filename: str


@router.post("/register-upload")
def register_gcs_upload(
    body: RegisterUploadRequest,
    user: User = Depends(require_recruiter),
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Register a file uploaded directly to GCS via signed URL.

    Uses lightweight filename-based detection to avoid downloading
    the full file (which can be 1+ GB and would OOM the API container).
    Full detection runs in the background worker if needed.
    """
    from app.services.storage import is_gcs_path

    if not is_gcs_path(body.gcs_path):
        raise HTTPException(400, "Invalid GCS path")

    # Lightweight detection by filename pattern — avoids downloading
    # the multi-GB file into the API container's limited memory.
    fname = body.filename.lower()
    if "attachments" in fname and fname.endswith(".zip"):
        detection = {
            "platform": "recruitcrm_attachments",
            "confidence": 0.90,
            "evidence": [
                "Filename pattern matches Recruit CRM attachments export"
            ],
            "entity_types_found": ["resumes"],
            "row_count": 0,  # Will be determined by background worker
            "field_mapping": {},
        }
    elif (
        fname.endswith(".zip")
        and ("csv-data-export" in fname or "csv_data_export" in fname)
    ):
        detection = {
            "platform": "recruitcrm",
            "confidence": 0.85,
            "evidence": [
                "Filename pattern matches Recruit CRM CSV data export"
            ],
            "entity_types_found": [
                "candidates", "companies", "contacts", "jobs", "assignments",
            ],
            "row_count": 0,
            "field_mapping": {},
        }
    elif fname.endswith(".zip"):
        detection = {
            "platform": "resume_archive",
            "confidence": 0.70,
            "evidence": ["ZIP file uploaded via signed URL"],
            "entity_types_found": ["resumes"],
            "row_count": 0,
            "field_mapping": {},
        }
    else:
        raise HTTPException(
            400,
            "Signed URL upload only supports ZIP files. "
            "Use the standard upload for CSV/JSON/XLSX.",
        )

    platform = detection["platform"]

    job = MigrationJob(
        user_id=user.id,
        source_platform=platform,
        source_platform_detected=detection["platform"],
        status="pending",
        source_file_path=body.gcs_path,
        config_json={
            "original_filename": body.filename,
            "detection": detection,
            "recruiter_profile_id": profile.id,
        },
    )
    db.add(job)
    db.flush()

    activity = RecruiterActivity(
        recruiter_profile_id=profile.id,
        user_id=user.id,
        activity_type="migration_started",
        subject=f"Started migration from {platform}",
        activity_metadata={
            "migration_job_id": job.id,
            "platform": platform,
            "file_name": body.filename,
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

    # Stream file to disk in chunks (supports multi-GB uploads)
    file_id = uuid.uuid4().hex[:12]
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    local_dest = os.path.join(
        UPLOAD_DIR, f"{user.id}_{file_id}_{file.filename}"
    )
    try:
        with open(local_dest, "wb") as f:
            while True:
                chunk = await file.read(8 * 1024 * 1024)  # 8 MB
                if not chunk:
                    break
                f.write(chunk)

        detection = detect_platform(local_dest)
        platform = (
            source_platform if source_platform != "auto" else detection["platform"]
        )

        # For resume archives, stage to cloud storage so async workers
        # can access the file even after this container restarts.
        # CRM imports and attachments use the local path directly.
        if platform == "resume_archive" or detection["platform"] == "resume_archive":
            from app.services.storage import upload_bytes

            unique_name = f"{user.id}_{file_id}_{file.filename}"
            with open(local_dest, "rb") as f:
                contents = f.read()
            stored_path = upload_bytes(
                contents, "staging/migration_zips/", unique_name
            )
            del contents
            try:
                os.unlink(local_dest)
            except OSError:
                pass
        else:
            stored_path = local_dest
    except Exception:
        try:
            os.unlink(local_dest)
        except OSError:
            pass
        raise

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

    # Add queue info for resume archive and attachments imports
    resume_platforms = ("resume_archive", "recruitcrm_attachments")
    if job.source_platform in resume_platforms and job.status in (
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

    # For attachments imports, expose batch_id from stats for frontend polling
    if (
        job.source_platform_detected == "recruitcrm_attachments"
        and job.stats_json
        and job.stats_json.get("batch_id")
    ):
        result["batch_id"] = job.stats_json["batch_id"]

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

    # Recruit CRM attachments ZIP — requires prior CSV import
    if job.source_platform_detected == "recruitcrm_attachments":
        prior = db.execute(
            select(MigrationJob).where(
                MigrationJob.user_id == user.id,
                MigrationJob.source_platform_detected == "recruitcrm",
                MigrationJob.status == "completed",
            ).order_by(MigrationJob.completed_at.desc())
        ).scalar_one_or_none()
        if not prior:
            raise HTTPException(
                status_code=400,
                detail="Import your Recruit CRM CSV data export first, "
                "then upload the attachments ZIP.",
            )

        job.status = "importing"
        job.started_at = datetime.now(UTC)
        job.config_json = {
            **(job.config_json or {}),
            "csv_migration_job_id": prior.id,
        }
        db.commit()

        try:
            from app.services.migration.recruitcrm_orchestrator import (
                stage_attachments_job,
            )
            from app.services.queue import get_queue

            queue = get_queue("default")
            queue.enqueue(
                stage_attachments_job,
                migration_job_id=job.id,
                job_timeout="60m",
            )
        except Exception:
            logger.exception(
                "Failed to enqueue attachments migration job %d", job_id
            )
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
            "message": "Extracting and staging resume files. "
            "You'll receive an email when processing is complete.",
        }

    # Resume archives — agency tier only
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

        detection = (job.config_json or {}).get("detection", {})
        file_count = detection.get("row_count", 0)

        # Small archives (≤50 files): process synchronously so the user
        # sees immediate results without depending on the background worker.
        SYNC_THRESHOLD = 50
        if file_count <= SYNC_THRESHOLD:
            return _process_resume_archive_sync(job, user, profile, db)

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

        # No active import — start immediately (async for large archives)
        job.status = "importing"
        job.started_at = datetime.now(UTC)
        db.commit()

        try:
            queue = get_queue("default")
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

    # Recruit CRM multi-CSV ZIP — use dedicated orchestrator
    if job.source_platform_detected == "recruitcrm" and (
        job.source_file_path or ""
    ).lower().endswith(".zip"):
        from app.services.migration.recruitcrm_orchestrator import (
            run_recruitcrm_zip_migration,
        )

        try:
            result = run_recruitcrm_zip_migration(job.id, db)
        except Exception:
            logger.exception("RecruitCRM ZIP migration %d failed", job_id)
            db.refresh(job)
            return {
                "job_id": job_id,
                "status": job.status,
                "stats": job.stats_json,
                "errors": job.error_log,
            }
        return result

    # Enqueue CRM import to worker so the POST returns immediately
    # and the frontend can poll for progress with % counter.
    job.status = "importing"
    job.started_at = datetime.now(UTC)
    db.commit()

    try:
        from app.services.queue import get_queue

        queue = get_queue("default")
        queue.enqueue(
            _run_migration_worker,
            migration_job_id=job_id,
            job_timeout="30m",
        )
    except Exception:
        logger.warning("Queue unavailable, running migration %d synchronously", job_id)
        return run_recruiter_migration(job_id, db)

    return {"job_id": job_id, "status": "importing"}


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


@router.post("/{job_id}/cancel")
def cancel_recruiter_migration(
    job_id: int,
    user: User = Depends(require_recruiter),
    db: Session = Depends(get_session),
):
    """Cancel a stuck or in-progress migration job so it can be retried."""
    job = db.execute(
        select(MigrationJob).where(
            MigrationJob.id == job_id,
            MigrationJob.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found")

    if job.status in ("completed", "rolled_back"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel a {job.status} job",
        )

    # Cancel any associated upload batch
    if job.stats_json and job.stats_json.get("batch_id"):
        from app.models.upload_batch import UploadBatch

        batch = db.execute(
            select(UploadBatch).where(
                UploadBatch.batch_id == job.stats_json["batch_id"],
            )
        ).scalar_one_or_none()
        if batch and batch.status in ("pending", "processing"):
            batch.status = "cancelled"

    old_status = job.status
    job.status = "failed"
    job.error_log = [
        {"error": f"Cancelled by user (was {old_status})", "cancelled": True}
    ]
    job.updated_at = datetime.now(UTC)
    db.commit()

    return {
        "job_id": job_id,
        "status": "failed",
        "message": "Migration cancelled. You can start a new migration.",
    }


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
            "started_at": j.started_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]


@router.post("/repair-contacts")
def repair_contact_names(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Repair migrated contacts: split 'name' → first_name/last_name.

    Fixes contacts that were imported with a combined 'name' field
    instead of separate first_name/last_name fields.
    """
    from app.models.recruiter_client import RecruiterClient

    clients = (
        db.execute(
            select(RecruiterClient).where(
                RecruiterClient.recruiter_profile_id == profile.id,
                RecruiterClient.contacts.isnot(None),
            )
        )
        .scalars()
        .all()
    )

    repaired = 0
    for client in clients:
        contacts = client.contacts
        if not contacts:
            continue
        changed = False
        for entry in contacts:
            # Split combined "name" into first_name / last_name
            if "name" in entry and "first_name" not in entry:
                parts = (entry.pop("name") or "").split(" ", 1)
                entry["first_name"] = parts[0] if parts else ""
                entry["last_name"] = parts[1] if len(parts) > 1 else ""
                changed = True
            # Rename "title" to keep it but ensure role is present
            if "title" in entry and "role" not in entry:
                entry["role"] = entry.pop("title")
                changed = True
        if changed:
            # Force SQLAlchemy to detect JSONB mutation
            client.contacts = list(contacts)
            repaired += 1

    db.commit()
    return {"repaired_clients": repaired}
