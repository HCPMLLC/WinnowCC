"""Admin recruiter management router."""

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.user import User
from app.schemas.admin_recruiters import (
    AdminRecruiterClientResponse,
    AdminRecruiterJobResponse,
    AdminRecruiterResponse,
    DeleteRecruitersRequest,
    DeleteRecruitersResponse,
    RecruiterTierOverrideRequest,
    RecruiterTierOverrideResponse,
)
from app.services.auth import require_admin_user
from app.services.cascade_delete import cascade_delete_user

router = APIRouter(prefix="/api/admin/recruiters", tags=["admin-recruiters"])


def _require_admin_token(x_admin_token: str | None = Header(None)):
    """Verify admin access via ADMIN_TOKEN header (no cookie needed)."""
    expected = os.getenv("ADMIN_TOKEN", "")
    if not expected or not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return True


# ── Static /jobs/* routes MUST come before /{recruiter_id}/* routes ──


@router.get("/jobs/duplicate-report")
def duplicate_report(
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Report duplicate recruiter jobs (same title + company)."""
    from sqlalchemy import literal_column

    # Find (title, company) groups with more than one job
    stmt = (
        select(
            func.lower(RecruiterJob.title).label("title_lc"),
            func.lower(
                func.coalesce(
                    RecruiterJob.client_company_name,
                    literal_column("''"),
                )
            ).label("company_lc"),
            func.count(RecruiterJob.id).label("cnt"),
            func.array_agg(RecruiterJob.id).label("ids"),
        )
        .group_by("title_lc", "company_lc")
        .having(func.count(RecruiterJob.id) > 1)
        .order_by(func.count(RecruiterJob.id).desc())
    )
    rows = session.execute(stmt).all()

    total_dupes = sum(r.cnt - 1 for r in rows)
    total_jobs = session.execute(
        select(func.count(RecruiterJob.id))
    ).scalar()
    missing_sol = session.execute(
        select(func.count(RecruiterJob.id)).where(
            RecruiterJob.job_id_external.is_(None)
        )
    ).scalar()

    groups = [
        {
            "title": r.title_lc,
            "company": r.company_lc,
            "count": r.cnt,
            "job_ids": sorted(r.ids),
        }
        for r in rows[:50]  # top 50 groups
    ]

    return {
        "total_jobs": total_jobs,
        "missing_solicitation_number": missing_sol,
        "duplicate_groups": len(rows),
        "total_duplicate_rows": total_dupes,
        "top_groups": groups,
    }


@router.post("/jobs/deduplicate")
def deduplicate_recruiter_jobs(
    dry_run: bool = Query(default=True),
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Remove duplicate recruiter jobs, keeping the oldest in each group.

    Duplicates are identified by matching solicitation number (job_id_external)
    within the same recruiter profile, falling back to title + company name.

    Pass dry_run=false to actually delete.
    """
    from sqlalchemy import literal_column

    deleted_ids: list[int] = []

    # --- Pass 1: duplicates by job_id_external (strongest signal) ---
    ext_stmt = (
        select(
            RecruiterJob.recruiter_profile_id,
            func.lower(RecruiterJob.job_id_external).label("ext_lc"),
            func.min(RecruiterJob.id).label("keep_id"),
            func.array_agg(RecruiterJob.id).label("all_ids"),
        )
        .where(RecruiterJob.job_id_external.isnot(None))
        .group_by(
            RecruiterJob.recruiter_profile_id,
            func.lower(RecruiterJob.job_id_external),
        )
        .having(func.count(RecruiterJob.id) > 1)
    )
    for row in session.execute(ext_stmt).all():
        dupes = [i for i in sorted(row.all_ids) if i != row.keep_id]
        deleted_ids.extend(dupes)

    # --- Pass 2: duplicates by title + company (no external ID) ---
    title_stmt = (
        select(
            RecruiterJob.recruiter_profile_id,
            func.lower(RecruiterJob.title).label("title_lc"),
            func.lower(
                func.coalesce(
                    RecruiterJob.client_company_name,
                    literal_column("''"),
                )
            ).label("company_lc"),
            func.min(RecruiterJob.id).label("keep_id"),
            func.array_agg(RecruiterJob.id).label("all_ids"),
        )
        .where(RecruiterJob.job_id_external.is_(None))
        .group_by(
            RecruiterJob.recruiter_profile_id,
            func.lower(RecruiterJob.title),
            "company_lc",
        )
        .having(func.count(RecruiterJob.id) > 1)
    )
    for row in session.execute(title_stmt).all():
        dupes = [i for i in sorted(row.all_ids) if i != row.keep_id]
        deleted_ids.extend(dupes)

    # Deduplicate the list itself (a job could appear in both passes)
    deleted_ids = sorted(set(deleted_ids))

    actually_deleted: list[int] = []
    errors: list[str] = []

    if not dry_run and deleted_ids:
        import logging

        from sqlalchemy import text

        log = logging.getLogger(__name__)
        log.info("Dedup: deleting %d recruiter jobs: %s", len(deleted_ids), deleted_ids)

        # FK cleanup and delete tables — one job at a time
        # DB-level ON DELETE CASCADE / SET NULL handles all FK references.
        # Just delete the recruiter_jobs rows directly.
        for jid in deleted_ids:
            try:
                session.execute(
                    text("DELETE FROM recruiter_jobs WHERE id = :jid"),
                    {"jid": jid},
                )
                session.commit()
                actually_deleted.append(jid)
            except Exception as e:
                session.rollback()
                errors.append(f"Job {jid}: {e}")
                log.exception("Dedup: failed to delete job %d", jid)

    result: dict = {
        "dry_run": dry_run,
        "duplicates_found": len(deleted_ids),
    }
    if dry_run:
        result["would_delete_ids"] = deleted_ids
    else:
        result["deleted_ids"] = actually_deleted
        if errors:
            result["errors"] = errors
    return result


@router.post("/jobs/backfill-required-fields")
def admin_backfill_required_fields(
    batch_size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> dict:
    """Synchronously re-parse recruiter jobs missing required fields.

    Processes up to ``batch_size`` jobs inline (no worker needed).
    Returns how many were filled.  Call repeatedly until remaining=0.
    """
    import logging

    from sqlalchemy import or_

    from app.services.job_pipeline import backfill_recruiter_job_fields

    log = logging.getLogger(__name__)

    missing = (
        session.execute(
            select(RecruiterJob.id).where(
                or_(
                    RecruiterJob.job_id_external.is_(None),
                    RecruiterJob.closes_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    batch = missing[:batch_size]
    filled = 0
    errors = 0
    for jid in batch:
        try:
            if backfill_recruiter_job_fields(jid):
                filled += 1
        except Exception:
            log.debug("backfill failed for job %s", jid)
            errors += 1

    return {
        "total_missing": len(missing),
        "processed": len(batch),
        "filled": filled,
        "errors": errors,
        "remaining": max(0, len(missing) - len(batch)),
    }


@router.post("/jobs/backfill-from-migration")
def backfill_from_migration(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> dict:
    """Backfill job_id_external and closes_at from migration_entity_map.

    Reads the raw CSV data stored during the Recruit CRM import and
    updates recruiter_jobs that are missing these fields.
    """
    import logging
    from datetime import datetime as _dt

    from app.models.migration import MigrationEntityMap

    log = logging.getLogger(__name__)

    # Find all migration-mapped recruiter jobs
    rows = session.execute(
        select(MigrationEntityMap).where(
            MigrationEntityMap.source_entity_type == "job",
            MigrationEntityMap.winnow_entity_type == "recruiter_job",
            MigrationEntityMap.winnow_entity_id.isnot(None),
            MigrationEntityMap.raw_data.isnot(None),
        )
    ).scalars().all()

    updated = 0
    skipped = 0
    no_data = 0

    for em in rows:
        raw = em.raw_data or {}
        sol_num = (
            raw.get("Solicitation Number")
            or raw.get("Solicitation #")
            or raw.get("Job ID")
            or ""
        ).strip() or None
        close_str = (raw.get("Close Date") or "").strip()

        close_date = None
        if close_str:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                try:
                    close_date = _dt.strptime(close_str, fmt)
                    break
                except ValueError:
                    continue

        if not sol_num and not close_date:
            no_data += 1
            continue

        job = session.get(RecruiterJob, em.winnow_entity_id)
        if not job:
            skipped += 1
            continue

        changed = False
        if sol_num and not job.job_id_external:
            job.job_id_external = sol_num
            changed = True
        if close_date and not job.closes_at:
            job.closes_at = close_date
            changed = True

        if changed:
            updated += 1
        else:
            skipped += 1

    session.commit()
    log.info(
        "Migration backfill: %d updated, %d skipped, %d no data",
        updated, skipped, no_data,
    )

    return {
        "migration_rows": len(rows),
        "updated": updated,
        "skipped": skipped,
        "no_data_in_csv": no_data,
    }


# ── Static non-jobs routes ──


@router.get("", response_model=list[AdminRecruiterResponse])
def list_recruiters(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterResponse]:
    """List all recruiters with profile data, counts, and usage."""
    # Subquery: pipeline candidate count per recruiter
    pipeline_sq = (
        select(
            RecruiterPipelineCandidate.recruiter_profile_id,
            func.count(RecruiterPipelineCandidate.id).label("cnt"),
        )
        .group_by(RecruiterPipelineCandidate.recruiter_profile_id)
        .subquery()
    )

    # Subquery: jobs count per recruiter
    jobs_sq = (
        select(
            RecruiterJob.recruiter_profile_id,
            func.count(RecruiterJob.id).label("cnt"),
        )
        .group_by(RecruiterJob.recruiter_profile_id)
        .subquery()
    )

    # Subquery: clients count per recruiter
    clients_sq = (
        select(
            RecruiterClient.recruiter_profile_id,
            func.count(RecruiterClient.id).label("cnt"),
        )
        .group_by(RecruiterClient.recruiter_profile_id)
        .subquery()
    )

    stmt = (
        select(
            RecruiterProfile,
            User,
            func.coalesce(pipeline_sq.c.cnt, 0).label("pipeline_count"),
            func.coalesce(jobs_sq.c.cnt, 0).label("jobs_count"),
            func.coalesce(clients_sq.c.cnt, 0).label("clients_count"),
        )
        .join(User, RecruiterProfile.user_id == User.id)
        .outerjoin(
            pipeline_sq,
            RecruiterProfile.id == pipeline_sq.c.recruiter_profile_id,
        )
        .outerjoin(
            jobs_sq,
            RecruiterProfile.id == jobs_sq.c.recruiter_profile_id,
        )
        .outerjoin(
            clients_sq,
            RecruiterProfile.id == clients_sq.c.recruiter_profile_id,
        )
        .order_by(RecruiterProfile.company_name.asc())
    )

    rows = session.execute(stmt).all()

    return [
        AdminRecruiterResponse(
            id=rp.id,
            user_id=user.id,
            email=user.email,
            company_name=rp.company_name,
            company_type=rp.company_type,
            company_website=rp.company_website,
            subscription_tier=rp.subscription_tier,
            subscription_status=rp.subscription_status,
            billing_interval=rp.billing_interval,
            billing_exempt=rp.billing_exempt,
            seats_purchased=rp.seats_purchased,
            seats_used=rp.seats_used,
            is_trial_active=rp.is_trial_active,
            trial_days_remaining=rp.trial_days_remaining,
            candidate_briefs_used=rp.candidate_briefs_used,
            salary_lookups_used=rp.salary_lookups_used,
            job_uploads_used=rp.job_uploads_used,
            intro_requests_used=rp.intro_requests_used,
            resume_imports_used=rp.resume_imports_used,
            outreach_enrollments_used=rp.outreach_enrollments_used,
            pipeline_count=pipeline_count,
            jobs_count=jobs_count,
            clients_count=clients_count,
            created_at=rp.created_at,
        )
        for rp, user, pipeline_count, jobs_count, clients_count in rows
    ]


@router.post("/delete", response_model=DeleteRecruitersResponse)
def delete_recruiters(
    payload: DeleteRecruitersRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> DeleteRecruitersResponse:
    """Delete one or more recruiters and all their associated data."""
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    deleted_count = 0
    for user_id in payload.user_ids:
        if cascade_delete_user(session, user_id):
            deleted_count += 1

    session.commit()

    return DeleteRecruitersResponse(
        deleted_count=deleted_count,
        message=f"Successfully deleted {deleted_count} recruiter(s).",
    )


# ── Dynamic /{recruiter_id}/* routes ──


@router.get(
    "/{recruiter_id}/jobs",
    response_model=list[AdminRecruiterJobResponse],
)
def list_recruiter_jobs(
    recruiter_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterJobResponse]:
    """List all job orders for a specific recruiter."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    stmt = (
        select(RecruiterJob)
        .where(RecruiterJob.recruiter_profile_id == recruiter_id)
        .order_by(RecruiterJob.created_at.desc())
    )
    jobs = session.execute(stmt).scalars().all()

    return [
        AdminRecruiterJobResponse(
            id=j.id,
            title=j.title,
            status=j.status,
            client_company_name=j.client_company_name,
            location=j.location,
            priority=j.priority,
            positions_to_fill=j.positions_to_fill,
            positions_filled=j.positions_filled,
            created_at=j.created_at,
        )
        for j in jobs
    ]


@router.get(
    "/{recruiter_id}/clients",
    response_model=list[AdminRecruiterClientResponse],
)
def list_recruiter_clients(
    recruiter_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminRecruiterClientResponse]:
    """List all clients for a specific recruiter."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    stmt = (
        select(RecruiterClient)
        .where(RecruiterClient.recruiter_profile_id == recruiter_id)
        .order_by(RecruiterClient.company_name.asc())
    )
    clients = session.execute(stmt).scalars().all()

    return [
        AdminRecruiterClientResponse(
            id=c.id,
            company_name=c.company_name,
            industry=c.industry,
            contact_name=c.contact_name,
            contact_email=c.contact_email,
            status=c.status,
            contract_type=c.contract_type,
            fee_percentage=c.fee_percentage,
            created_at=c.created_at,
        )
        for c in clients
    ]


@router.post(
    "/{recruiter_id}/tier-override",
    response_model=RecruiterTierOverrideResponse,
)
def override_recruiter_tier(
    recruiter_id: int,
    body: RecruiterTierOverrideRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> RecruiterTierOverrideResponse:
    """Override a recruiter's subscription tier (admin only)."""
    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    valid_tiers = {"trial", "solo", "team", "agency"}
    if body.subscription_tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid tier. Must be one of: "
                + ", ".join(sorted(valid_tiers))
            ),
        )

    recruiter.subscription_tier = body.subscription_tier
    recruiter.subscription_status = body.subscription_status
    if body.billing_exempt is not None:
        recruiter.billing_exempt = body.billing_exempt
    # Clear trial dates if moving from trial to a paid tier
    if body.subscription_tier != "trial":
        recruiter.trial_started_at = None
        recruiter.trial_ends_at = None
    session.commit()

    return RecruiterTierOverrideResponse(
        id=recruiter.id,
        subscription_tier=recruiter.subscription_tier,
        subscription_status=recruiter.subscription_status,
        billing_exempt=recruiter.billing_exempt,
    )


@router.post("/{recruiter_id}/prioritize-reparse")
def prioritize_reparse(
    recruiter_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> dict:
    """Move pending LLM reparses for this recruiter to front of low queue."""
    from app.models.candidate_profile import CandidateProfile
    from app.services.queue import get_queue
    from app.services.recruiter_llm_reparse import recruiter_llm_reparse_job

    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    # Find profiles with pending LLM reparse for this recruiter
    pending_profiles = (
        session.execute(
            select(CandidateProfile)
            .where(
                CandidateProfile.profile_json["sourced_by_user_id"].astext
                == str(recruiter.user_id),
                CandidateProfile.llm_parse_status == "pending",
            )
        )
        .scalars()
        .all()
    )

    low_q = get_queue("low")
    queued = 0
    for cp in pending_profiles:
        if cp.resume_document_id:
            low_q.enqueue(
                recruiter_llm_reparse_job,
                cp.id,
                cp.resume_document_id,
                job_timeout="10m",
                at_front=True,
            )
            queued += 1

    return {"queued": queued}


@router.post("/{recruiter_id}/refresh-matches")
def refresh_matches(
    recruiter_id: int,
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Enqueue candidate matching for all active jobs of this recruiter."""
    from app.services.job_pipeline import populate_recruiter_job_candidates
    from app.services.queue import get_queue

    recruiter = session.get(RecruiterProfile, recruiter_id)
    if recruiter is None:
        raise HTTPException(status_code=404, detail="Recruiter not found.")

    active_jobs = (
        session.execute(
            select(RecruiterJob.id).where(
                RecruiterJob.recruiter_profile_id == recruiter_id,
                RecruiterJob.status.in_(("active", "draft")),
            )
        )
        .scalars()
        .all()
    )

    q = get_queue()
    for job_id in active_jobs:
        q.enqueue(populate_recruiter_job_candidates, job_id)

    return {"queued": len(active_jobs)}


@router.post("/jobs/{job_id}/score-candidate/{candidate_profile_id}")
def score_single_candidate(
    job_id: int,
    candidate_profile_id: int,
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Score a single candidate against a recruiter job (diagnostic)."""
    from app.models.candidate_profile import CandidateProfile
    from app.services.matching import _score_posted_job

    job = session.get(RecruiterJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    cp = session.get(CandidateProfile, candidate_profile_id)
    if cp is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    result = _score_posted_job(job, cp.profile_json or {})
    return {
        "candidate_profile_id": candidate_profile_id,
        "recruiter_job_id": job_id,
        "match_score": result.match_score,
        "reasons": result.reasons,
    }


@router.post("/jobs/{job_id}/refresh-sync")
def refresh_job_candidates_sync(
    job_id: int,
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Enqueue populate_recruiter_job_candidates to the worker."""
    from app.services.job_pipeline import populate_recruiter_job_candidates
    from app.services.queue import get_queue

    job = session.get(RecruiterJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    get_queue().enqueue(
        populate_recruiter_job_candidates, job_id, job_timeout="30m",
    )

    return {"job_id": job_id, "status": "enqueued"}


@router.get("/jobs/{job_id}/match-count")
def get_job_match_count(
    job_id: int,
    session: Session = Depends(get_session),
    _admin: bool = Depends(_require_admin_token),
) -> dict:
    """Return count of cached candidate matches for a recruiter job."""
    from app.models.recruiter_job_candidate import RecruiterJobCandidate

    count = session.execute(
        select(func.count(RecruiterJobCandidate.id)).where(
            RecruiterJobCandidate.recruiter_job_id == job_id
        )
    ).scalar() or 0

    # Check if specific candidate is in results
    from app.models.recruiter_job_candidate import (
        RecruiterJobCandidate as RJC2,
    )

    all_matches = session.execute(
        select(RJC2.candidate_profile_id, RJC2.match_score)
        .where(RJC2.recruiter_job_id == job_id)
        .order_by(RJC2.match_score.desc())
    ).all()
    top5 = [
        {"id": r[0], "score": r[1]} for r in all_matches[:5]
    ]
    bottom5 = [
        {"id": r[0], "score": r[1]} for r in all_matches[-5:]
    ]

    return {
        "job_id": job_id,
        "candidates_matched": count,
        "top5": top5,
        "bottom5": bottom5,
    }
