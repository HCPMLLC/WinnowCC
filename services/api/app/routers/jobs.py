"""Public job endpoints (authenticated)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.models.user import User
from app.schemas.jobs import JobParsedDetailResponse, JobResponse
from app.services.auth import get_current_user
from app.services.matching import _get_embedding_list, compute_cosine_similarity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}/similar", response_model=list[JobResponse])
def get_similar_jobs(
    job_id: int,
    limit: int = Query(5, ge=1, le=20),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Find jobs with the closest embedding to the given job."""
    job = session.execute(
        select(Job).where(Job.id == job_id)
    ).scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.embedding is None:
        return []

    # Try pgvector cosine distance operator first
    try:
        rows = session.execute(
            text(
                """
                SELECT id, embedding <=> cast(:emb as vector) AS distance
                FROM jobs
                WHERE id != :job_id AND embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT :lim
                """
            ),
            {"emb": str(list(job.embedding)), "job_id": job_id, "lim": limit},
        ).fetchall()
        similar_ids = [row[0] for row in rows]
    except Exception:
        logger.info("pgvector <=> not available, falling back to Python cosine sim")
        source_emb = _get_embedding_list(job.embedding)
        all_jobs = session.execute(
            select(Job.id, Job.embedding).where(
                Job.id != job_id, Job.embedding.is_not(None)
            )
        ).all()
        scored = []
        for jid, emb in all_jobs:
            emb_list = _get_embedding_list(emb)
            sim = compute_cosine_similarity(source_emb, emb_list)
            if sim is not None:
                scored.append((jid, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        similar_ids = [jid for jid, _ in scored[:limit]]

    if not similar_ids:
        return []

    jobs = session.execute(
        select(Job).where(Job.id.in_(similar_ids))
    ).scalars().all()
    jobs_by_id = {j.id: j for j in jobs}

    return [
        JobResponse.model_validate(jobs_by_id[jid])
        for jid in similar_ids
        if jid in jobs_by_id
    ]


@router.get("/{job_id}/parsed", response_model=JobParsedDetailResponse)
def get_parsed_detail(
    job_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get parsed details for a job posting."""
    parsed = session.execute(
        select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
    ).scalar_one_or_none()

    if not parsed:
        raise HTTPException(
            status_code=404, detail="No parsed details found for this job"
        )

    return parsed
