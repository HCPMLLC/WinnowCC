"""Scheduled job functions for RQ Scheduler."""

import logging
from datetime import UTC, date, datetime

from app.db.session import get_session_factory
from app.models.employer import EmployerJob
from app.models.job_run import JobRun
from app.services.job_ingestion import clear_progress, ingest_jobs
from app.services.scheduler_config import (
    get_scheduler_default_location,
    get_scheduler_default_search,
)

logger = logging.getLogger(__name__)


def scheduled_ingest_jobs() -> dict:
    """Scheduled job ingestion task.

    Fetches jobs from all configured sources using default search parameters
    and tracks the run in the job_runs table.

    Returns:
        dict with run_id, status, jobs_ingested, and error (if any)
    """
    session = get_session_factory()()
    run = None

    try:
        # Create job run record
        run = JobRun(
            job_type="scheduled_ingest",
            status="running",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        logger.info(f"Starting scheduled job ingestion (run_id={run.id})")

        # Build query from config
        query = {}
        search = get_scheduler_default_search()
        location = get_scheduler_default_location()
        if search:
            query["search"] = search
        if location:
            query["location"] = location

        # Run ingestion
        jobs_count = ingest_jobs(session, query, run_id=run.id)

        # Update run record
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.jobs_ingested = jobs_count
        session.commit()
        clear_progress(run.id)

        logger.info(
            f"Scheduled job ingestion completed (run_id={run.id}, jobs={jobs_count})"
        )

        return {
            "run_id": run.id,
            "status": "completed",
            "jobs_ingested": jobs_count,
            "error": None,
        }

    except Exception as e:
        logger.exception(f"Scheduled job ingestion failed: {e}")

        if run:
            run.status = "failed"
            run.finished_at = datetime.now(UTC)
            run.error_message = str(e)[:1000]  # Truncate long errors
            session.commit()
            clear_progress(run.id)

        return {
            "run_id": run.id if run else None,
            "status": "failed",
            "jobs_ingested": 0,
            "error": str(e),
        }

    finally:
        session.close()


def scheduled_freshness_check() -> dict:
    """Run freshness check on all distributions (P45).

    Runs every 5 minutes. Detects stale/stuck distributions and fixes them.
    """
    from app.services.freshness_monitor import run_freshness_check

    session = get_session_factory()()
    try:
        results = run_freshness_check(session)
        return {"status": "completed", **results}
    except Exception as e:
        logger.exception("Freshness check failed: %s", e)
        session.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        session.close()


def scheduled_purge_inactive_jobs() -> dict:
    """Scheduled task to purge old inactive jobs from the database.

    Runs weekly. Only deletes jobs that have been inactive for 90+ days
    and have no saved/applied matches.
    """
    from app.services.job_purge import purge_jobs

    session = get_session_factory()()
    try:
        result = purge_jobs(session)
        logger.info(
            "Scheduled purge completed: %d jobs deleted", result.get("deleted_count", 0)
        )
        return {"status": "completed", **result, "error": None}
    except Exception as e:
        logger.exception(f"Scheduled purge failed: {e}")
        session.rollback()
        return {"status": "failed", "deleted_count": 0, "error": str(e)}
    finally:
        session.close()


def scheduled_check_stale_jobs() -> dict:
    """Scheduled task to check for and mark stale job postings.

    A job is stale if last_seen_at > 30 days or posted_at > 45 days.
    """
    from app.services.job_fraud_detector import check_stale_jobs

    session = get_session_factory()()
    try:
        stale_count = check_stale_jobs(session)
        session.commit()

        logger.info(f"Stale job check completed: {stale_count} jobs marked stale")

        return {
            "status": "completed",
            "stale_count": stale_count,
            "error": None,
        }
    except Exception as e:
        logger.exception(f"Stale job check failed: {e}")
        session.rollback()
        return {
            "status": "failed",
            "stale_count": 0,
            "error": str(e),
        }
    finally:
        session.close()


def scheduled_archive_expired_jobs() -> dict:
    """Archive employer jobs whose close_date has passed.

    Runs daily. Finds active/paused jobs with close_date < today and
    marks them as archived with reason 'expired'.
    """
    from sqlalchemy import and_

    session = get_session_factory()()
    try:
        today = date.today()
        expired = (
            session.query(EmployerJob)
            .filter(
                and_(
                    EmployerJob.close_date < today,
                    EmployerJob.archived == False,  # noqa: E712
                    EmployerJob.status.in_(["active", "paused"]),
                )
            )
            .all()
        )

        count = 0
        expired_active_ids = []
        for job in expired:
            if job.status == "active":
                expired_active_ids.append(job.id)
            job.archived = True
            job.archived_at = datetime.now(UTC)
            job.archived_reason = "expired"
            job.status = "closed"
            count += 1

        if count:
            session.commit()

        # Remove expired active jobs from boards
        for job_id in expired_active_ids:
            try:
                process_removal(job_id)
            except Exception:
                logger.warning(
                    "Failed to auto-remove expired job %s from boards",
                    job_id,
                )

        logger.info("Archived %d expired employer jobs", count)
        return {"status": "completed", "archived_count": count, "error": None}

    except Exception as e:
        logger.exception("Failed to archive expired jobs: %s", e)
        session.rollback()
        return {"status": "failed", "archived_count": 0, "error": str(e)}
    finally:
        session.close()


def process_distribution(employer_job_id: int) -> dict:
    """Worker job: distribute an employer job to all active board connections.

    Enqueued when an employer job status changes to 'active'.
    """
    from app.services.distribution import distribute_job

    session = get_session_factory()()
    try:
        job = session.get(EmployerJob, employer_job_id)
        if not job:
            return {"status": "skipped", "reason": "job not found"}
        if job.status != "active":
            reason = f"job status is '{job.status}', not 'active'"
            return {"status": "skipped", "reason": reason}

        results = distribute_job(employer_job_id, board_types=None, session=session)
        logger.info(
            "Auto-distributed job %s to %d board(s)", employer_job_id, len(results)
        )
        return {"status": "completed", "job_id": employer_job_id, "results": results}
    except Exception as e:
        logger.exception("Auto-distribution failed for job %s: %s", employer_job_id, e)
        session.rollback()
        return {"status": "failed", "job_id": employer_job_id, "error": str(e)}
    finally:
        session.close()


def process_removal(employer_job_id: int) -> dict:
    """Worker job: remove an employer job from all boards.

    Enqueued when an employer job status changes to 'paused' or 'closed'.
    """
    from app.services.distribution import remove_from_boards

    session = get_session_factory()()
    try:
        results = remove_from_boards(employer_job_id, session=session)
        logger.info(
            "Auto-removed job %s from %d board(s)", employer_job_id, len(results)
        )
        return {"status": "completed", "job_id": employer_job_id, "results": results}
    except Exception as e:
        logger.exception("Auto-removal failed for job %s: %s", employer_job_id, e)
        session.rollback()
        return {"status": "failed", "job_id": employer_job_id, "error": str(e)}
    finally:
        session.close()


def process_distribution_update(employer_job_id: int) -> dict:
    """Worker job: push updates to all boards where this job is live.

    Enqueued when an active employer job's content fields are edited.
    """
    from app.services.distribution import update_distribution

    session = get_session_factory()()
    try:
        results = update_distribution(employer_job_id, session=session)
        logger.info("Auto-updated job %s on %d board(s)", employer_job_id, len(results))
        return {"status": "completed", "job_id": employer_job_id, "results": results}
    except Exception as e:
        logger.exception("Auto-update failed for job %s: %s", employer_job_id, e)
        session.rollback()
        return {"status": "failed", "job_id": employer_job_id, "error": str(e)}
    finally:
        session.close()


def scheduled_expire_introductions() -> dict:
    """Expire stale introduction requests past their 7-day window.

    Runs daily. Updates pending requests with expires_at < now to 'expired'.
    """
    from app.services.introductions import expire_stale_requests

    session = get_session_factory()()
    try:
        count = expire_stale_requests(session)
        session.commit()
        logger.info("Expired %d stale introduction requests", count)
        return {"status": "completed", "expired_count": count, "error": None}
    except Exception as e:
        logger.exception("Introduction expiration failed: %s", e)
        session.rollback()
        return {"status": "failed", "expired_count": 0, "error": str(e)}
    finally:
        session.close()


def scheduled_process_outreach() -> dict:
    """Process due outreach sequence emails.

    Runs every 15 minutes. Sends emails for active enrollments whose
    next_send_at has passed and updates enrollment state.
    """
    from app.services.outreach import process_due_outreach

    try:
        results = process_due_outreach()
        logger.info(
            "Outreach processing: %d sent, %d errors, %d completed",
            results.get("sent", 0),
            results.get("errors", 0),
            results.get("completed", 0),
        )
        return {"status": "completed", **results}
    except Exception as e:
        logger.exception("Outreach processing failed: %s", e)
        return {"status": "failed", "error": str(e)}


def scheduled_hard_delete_expired() -> dict:
    """Hard-delete files soft-deleted more than 30 days ago.

    Enforces the privacy policy promise of deletion within 30 days.
    Runs daily.
    """
    from datetime import timedelta

    from sqlalchemy import select as sa_select

    from app.models.resume_document import ResumeDocument
    from app.services.storage import delete_file

    session = get_session_factory()()
    try:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        expired = list(
            session.execute(
                sa_select(ResumeDocument).where(
                    ResumeDocument.deleted_at.isnot(None),
                    ResumeDocument.deleted_at < cutoff,
                )
            )
            .scalars()
            .all()
        )

        deleted = 0
        errors = 0
        for doc in expired:
            try:
                if doc.path:
                    delete_file(doc.path)
                session.delete(doc)
                deleted += 1
            except Exception as e:
                logger.warning("Failed to hard-delete resume doc %s: %s", doc.id, e)
                errors += 1

        if deleted:
            session.commit()

        logger.info("Hard-delete expired: %d deleted, %d errors", deleted, errors)
        return {
            "status": "completed",
            "deleted": deleted,
            "errors": errors,
        }

    except Exception as e:
        logger.exception("Hard-delete expired failed: %s", e)
        session.rollback()
        return {"status": "failed", "deleted": 0, "error": str(e)}
    finally:
        session.close()


def scheduled_sync_distribution_metrics() -> dict:
    """Sync metrics for all live job distributions across all employers.

    Runs every 15 minutes. Pulls impressions, clicks, applications
    from each board adapter and updates distribution records.
    """
    from sqlalchemy import select as sa_select

    from app.models.distribution import BoardConnection, JobDistribution
    from app.services.board_adapters import get_adapter

    session = get_session_factory()()
    try:
        stmt = sa_select(JobDistribution).where(JobDistribution.status == "live")
        distributions = list(session.execute(stmt).scalars().all())

        synced = 0
        errors = 0
        for dist in distributions:
            conn = session.get(BoardConnection, dist.board_connection_id)
            adapter = get_adapter(conn.board_type) if conn else None
            if not adapter or not conn:
                continue

            try:
                metrics = adapter.fetch_metrics(dist)
                dist.impressions = metrics.get("impressions", dist.impressions)
                dist.clicks = metrics.get("clicks", dist.clicks)
                dist.applications = metrics.get("applications", dist.applications)
                if "cost_spent" in metrics:
                    dist.cost_spent = metrics["cost_spent"]
                conn.last_sync_at = datetime.now(UTC)
                conn.last_sync_status = "success"
                synced += 1
            except Exception as e:
                logger.warning("Metrics sync failed for dist %s: %s", dist.id, e)
                if conn:
                    conn.last_sync_status = "failed"
                    conn.last_sync_error = str(e)[:1000]
                errors += 1

        if synced or errors:
            session.commit()

        logger.info("Distribution metrics sync: %d synced, %d errors", synced, errors)
        return {"status": "completed", "synced": synced, "errors": errors}

    except Exception as e:
        logger.exception("Distribution metrics sync failed: %s", e)
        session.rollback()
        return {"status": "failed", "synced": 0, "error": str(e)}
    finally:
        session.close()
