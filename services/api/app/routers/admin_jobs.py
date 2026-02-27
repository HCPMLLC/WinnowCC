"""Admin endpoints for job quality management and reparsing."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.models.user import User
from app.schemas.jobs import AdminJobListItem, JobQualityListItem, PaginatedJobsResponse
from app.services.auth import require_admin_user

router = APIRouter(prefix="/api/admin/jobs", tags=["admin-jobs"])

_ADMIN_SORT_COLUMNS = {
    "title": Job.title,
    "company": Job.company,
    "location": Job.location,
    "posted_at": Job.posted_at,
    "application_deadline": Job.application_deadline,
    "hiring_manager_name": Job.hiring_manager_name,
    "source": Job.source,
    "ingested_at": Job.ingested_at,
}


@router.get("/all", response_model=PaginatedJobsResponse)
def list_all_jobs(
    sort_by: str = Query("ingested_at", enum=list(_ADMIN_SORT_COLUMNS)),
    sort_dir: str = Query("desc", enum=["asc", "desc"]),
    group_by: str | None = Query(None, enum=["company", "location", "source"]),
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """List all ingested jobs with sorting, search, and pagination."""
    stmt = select(Job)

    # Text search on title + company
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Job.title.ilike(pattern), Job.company.ilike(pattern)))

    # Total count (before pagination)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(count_stmt).scalar() or 0

    # Sorting — group_by takes priority as primary sort if provided
    col = _ADMIN_SORT_COLUMNS.get(sort_by, Job.ingested_at)
    direction = asc if sort_dir == "asc" else desc

    if group_by and group_by in _ADMIN_SORT_COLUMNS:
        group_col = _ADMIN_SORT_COLUMNS[group_by]
        stmt = stmt.order_by(asc(group_col), direction(col))
    else:
        stmt = stmt.order_by(direction(col))

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    rows = session.execute(stmt).scalars().all()
    items = [AdminJobListItem.model_validate(r) for r in rows]

    return PaginatedJobsResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.post("/{job_id}/reparse")
def reparse_job(
    job_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Re-run parser and fraud detector on a single job."""
    from app.services.job_fraud_detector import JobFraudDetector
    from app.services.job_parser import JobParserService

    job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    parser = JobParserService()
    fraud_detector = JobFraudDetector()

    parsed = parser.parse(session, job)
    fraud_detector.evaluate(session, job, parsed)
    session.commit()

    return {
        "status": "reparsed",
        "job_id": job_id,
        "quality_score": parsed.posting_quality_score,
        "fraud_score": parsed.fraud_score,
    }


@router.post("/reparse-all")
def reparse_all_jobs(
    admin: User = Depends(require_admin_user),
):
    """Enqueue batch reparse of all active jobs via RQ."""
    try:
        from app.services.queue import enqueue

        result = enqueue("app.services.job_pipeline.reparse_all_jobs")
        return {"status": "queued", "job_id": str(result.id) if result else None}
    except Exception:
        # If RQ is not available, return an error
        raise HTTPException(
            status_code=503,
            detail="Queue not available. Run synchronously via /reparse endpoint.",
        ) from None


@router.get("/flagged", response_model=list[JobQualityListItem])
def get_flagged_jobs(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """List jobs with fraud_score >= 40 for admin review."""
    stmt = (
        select(JobParsedDetail, Job)
        .join(Job, JobParsedDetail.job_id == Job.id)
        .where(JobParsedDetail.fraud_score >= 40)
        .order_by(JobParsedDetail.fraud_score.desc())
        .limit(100)
    )
    results = session.execute(stmt).all()

    items = []
    for parsed, job in results:
        items.append(
            JobQualityListItem(
                job_id=job.id,
                title=job.title,
                company=job.company,
                fraud_score=parsed.fraud_score,
                posting_quality_score=parsed.posting_quality_score,
                is_likely_fraudulent=parsed.is_likely_fraudulent,
                red_flags=parsed.red_flags,
                is_stale=parsed.is_stale,
                parsed_at=parsed.parsed_at,
            )
        )
    return items


@router.post("/{job_id}/fraud-override")
def fraud_override(
    job_id: int,
    body: dict,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Admin sets is_likely_fraudulent manually.

    Body: {"is_fraudulent": true/false}
    """
    is_fraudulent = body.get("is_fraudulent")
    if is_fraudulent is None:
        raise HTTPException(status_code=400, detail="is_fraudulent field required")

    parsed = session.execute(
        select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
    ).scalar_one_or_none()
    if not parsed:
        raise HTTPException(status_code=404, detail="Parsed detail not found for job")

    job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    parsed.is_likely_fraudulent = bool(is_fraudulent)
    job.is_active = not bool(is_fraudulent)
    session.commit()

    return {
        "job_id": job_id,
        "is_likely_fraudulent": parsed.is_likely_fraudulent,
        "is_active": job.is_active,
    }


@router.get("/stats")
def job_stats(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Aggregate job pipeline statistics."""
    total = session.execute(select(func.count(Job.id))).scalar() or 0
    active = (
        session.execute(
            select(func.count(Job.id)).where(Job.is_active.is_(True))
        ).scalar()
        or 0
    )
    by_source = dict(
        session.execute(
            select(Job.source, func.count(Job.id)).group_by(Job.source)
        ).all()
    )

    fraud_counts = session.execute(
        select(
            func.count(JobParsedDetail.id).filter(
                JobParsedDetail.is_likely_fraudulent.is_(True)
            ),
            func.count(JobParsedDetail.id).filter(JobParsedDetail.is_stale.is_(True)),
        )
    ).one()

    ingested_7d = (
        session.execute(
            select(func.count(Job.id)).where(
                Job.ingested_at >= datetime.now(UTC) - timedelta(days=7)
            )
        ).scalar()
        or 0
    )

    return {
        "total_jobs": total,
        "active_jobs": active,
        "inactive_jobs": total - active,
        "by_source": by_source,
        "fraudulent": fraud_counts[0] or 0,
        "stale": fraud_counts[1] or 0,
        "ingested_last_7_days": ingested_7d,
    }


@router.get("/quality")
def job_quality_summary(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Quality score distribution across parsed jobs."""
    buckets = session.execute(
        select(
            func.count(case((JobParsedDetail.posting_quality_score >= 80, 1))).label(
                "high"
            ),
            func.count(
                case(
                    (
                        (JobParsedDetail.posting_quality_score >= 50)
                        & (JobParsedDetail.posting_quality_score < 80),
                        1,
                    )
                )
            ).label("medium"),
            func.count(case((JobParsedDetail.posting_quality_score < 50, 1))).label(
                "low"
            ),
        )
    ).one()

    avg_quality = session.execute(
        select(func.avg(JobParsedDetail.posting_quality_score))
    ).scalar()
    avg_fraud = session.execute(select(func.avg(JobParsedDetail.fraud_score))).scalar()

    return {
        "quality_distribution": {
            "high_80_plus": buckets[0] or 0,
            "medium_50_79": buckets[1] or 0,
            "low_below_50": buckets[2] or 0,
        },
        "avg_quality_score": round(avg_quality or 0, 1),
        "avg_fraud_score": round(avg_fraud or 0, 1),
    }


@router.post("/embeddings/backfill")
def backfill_embeddings(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Enqueue background job to embed all jobs without embeddings."""
    from app.services.job_pipeline import embed_all_jobs
    from app.services.queue import get_queue

    count = session.execute(
        select(func.count(Job.id)).where(Job.embedding.is_(None))
    ).scalar()
    get_queue("low").enqueue(embed_all_jobs)
    return {"status": "queued", "jobs_without_embeddings": count}


@router.get("/embeddings/status")
def embedding_status(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Return counts of embedded vs non-embedded jobs and profiles."""
    jobs_total = session.execute(select(func.count(Job.id))).scalar()
    jobs_embedded = session.execute(
        select(func.count(Job.id)).where(Job.embedding.isnot(None))
    ).scalar()
    profiles_total = session.execute(select(func.count(CandidateProfile.id))).scalar()
    profiles_embedded = session.execute(
        select(func.count(CandidateProfile.id)).where(
            CandidateProfile.embedding.isnot(None)
        )
    ).scalar()
    return {
        "jobs_embedded": jobs_embedded,
        "jobs_total": jobs_total,
        "profiles_embedded": profiles_embedded,
        "profiles_total": profiles_total,
    }
