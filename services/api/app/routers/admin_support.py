"""Admin support dashboard router.

Provides system health, user lookup, billing diagnostics, queue monitoring,
feature usage analytics, audit trail, and quick admin actions.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_trust import CandidateTrust
from app.models.daily_usage_counter import DailyUsageCounter
from app.models.employer import EmployerJob, EmployerProfile
from app.models.employer_compliance_log import EmployerComplianceLog
from app.models.job_run import JobRun
from app.models.recruiter import RecruiterProfile
from app.models.resume_document import ResumeDocument
from app.models.sieve_conversation import SieveConversation
from app.models.trust_audit_log import TrustAuditLog
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.schemas.admin_support import (
    ActionResponse,
    AuditLogResponse,
    BillingIssuesResponse,
    BillingIssueUser,
    FeatureUsageResponse,
    OverviewResponse,
    QueueMonitorResponse,
    TierOverrideRequest,
    UserLookupResult,
)
from app.services.auth import require_admin_user
from app.services.billing import CANDIDATE_PLAN_LIMITS
from app.services.worker_health import get_failed_jobs, get_queue_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/support", tags=["admin-support"])


# ---------------------------------------------------------------------------
# Endpoint 1: GET /overview
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=OverviewResponse)
def overview(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    # --- System health ---
    api_status = {"status": "ok"}

    try:
        db.execute(text("SELECT 1")).fetchone()
        db_status = {"status": "ok"}
    except Exception as exc:
        db_status = {"status": "error", "detail": str(exc)[:200]}

    queue_stats = get_queue_stats()
    redis_status = {
        "status": "ok" if queue_stats.get("redis_connected") else "error"
    }

    total_pending = queue_stats.get("total_pending", 0)
    total_failed = queue_stats.get("total_failed", 0)
    queues_dict = {}
    for qdata in queue_stats.get("queues", []):
        name = qdata.get("name", "unknown")
        queues_dict[name] = qdata

    # --- Platform stats ---
    role_counts = {
        (k or "unknown"): v
        for k, v in db.execute(
            select(User.role, func.count()).group_by(User.role)
        ).all()
    }
    total_users = sum(role_counts.values())

    now = datetime.now(UTC)
    users_7d = db.scalar(
        select(func.count()).select_from(User).where(
            User.created_at >= now - timedelta(days=7)
        )
    ) or 0
    users_30d = db.scalar(
        select(func.count()).select_from(User).where(
            User.created_at >= now - timedelta(days=30)
        )
    ) or 0

    # --- Billing stats ---
    candidate_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(Candidate.plan_tier, func.count())
            .group_by(Candidate.plan_tier)
        ).all()
    }
    employer_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(
                EmployerProfile.subscription_tier, func.count()
            ).group_by(EmployerProfile.subscription_tier)
        ).all()
    }
    recruiter_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(
                RecruiterProfile.subscription_tier, func.count()
            ).group_by(RecruiterProfile.subscription_tier)
        ).all()
    }

    # --- Alerts ---
    alerts = []

    if total_failed > 0:
        alerts.append({
            "type": "queue_failure",
            "severity": "error",
            "message": f"{total_failed} failed queue job(s)",
            "action_url": "/admin/support/queues",
        })

    past_due_count = db.scalar(
        select(func.count()).select_from(Candidate).where(
            Candidate.subscription_status == "past_due"
        )
    ) or 0
    past_due_count += db.scalar(
        select(func.count()).select_from(EmployerProfile).where(
            EmployerProfile.subscription_status == "past_due"
        )
    ) or 0
    past_due_count += db.scalar(
        select(func.count()).select_from(RecruiterProfile).where(
            RecruiterProfile.subscription_status == "past_due"
        )
    ) or 0

    if past_due_count > 0:
        alerts.append({
            "type": "past_due",
            "severity": "warning",
            "message": f"{past_due_count} subscription(s) past due",
            "action_url": "/admin/support/billing",
        })

    trust_pending = db.scalar(
        select(func.count()).select_from(CandidateTrust).where(
            CandidateTrust.status.in_(["soft_quarantine", "hard_quarantine"])
        )
    ) or 0
    if trust_pending > 0:
        alerts.append({
            "type": "trust_queue",
            "severity": "warning",
            "message": f"{trust_pending} candidate(s) in trust quarantine",
            "action_url": "/admin/trust",
        })

    return {
        "system_health": {
            "api": api_status,
            "database": db_status,
            "redis": redis_status,
            "queues": {
                "redis_connected": queue_stats.get("redis_connected", False),
                "total_pending": total_pending,
                "total_failed": total_failed,
                "queues": queues_dict,
            },
        },
        "platform_stats": {
            "total_users": total_users,
            "users_by_role": role_counts,
            "users_created_last_7d": users_7d,
            "users_created_last_30d": users_30d,
        },
        "billing_stats": {
            "candidates_by_tier": candidate_tiers,
            "employers_by_tier": employer_tiers,
            "recruiters_by_tier": recruiter_tiers,
        },
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# Endpoint 2: GET /user-lookup
# ---------------------------------------------------------------------------


@router.get("/user-lookup", response_model=list[UserLookupResult])
def user_lookup(
    q: str = Query(..., min_length=1),  # noqa: B008
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    # Search by ID or email
    users: list[User] = []
    if q.isdigit():
        user = db.get(User, int(q))
        if user:
            users = [user]
    else:
        users = list(
            db.scalars(
                select(User)
                .where(User.email.ilike(f"%{q}%"))
                .limit(20)
            ).all()
        )

    today = date.today()
    first_of_month = today.replace(day=1)
    results = []

    for user in users:
        # Candidate info
        candidate = db.scalar(
            select(Candidate).where(Candidate.user_id == user.id)
        )
        candidate_info = None
        if candidate:
            from app.models.match import Match

            match_count = db.scalar(
                select(func.count()).select_from(Match).where(
                    Match.user_id == user.id
                )
            ) or 0
            trust_record = db.scalar(
                select(CandidateTrust).join(
                    ResumeDocument,
                    CandidateTrust.resume_document_id == ResumeDocument.id,
                ).where(ResumeDocument.user_id == user.id)
            )
            candidate_info = {
                "plan_tier": candidate.plan_tier,
                "subscription_status": candidate.subscription_status,
                "match_count": match_count,
                "trust_status": trust_record.status if trust_record else None,
            }

        # Employer info
        employer = db.scalar(
            select(EmployerProfile).where(EmployerProfile.user_id == user.id)
        )
        employer_info = None
        if employer:
            active_jobs = db.scalar(
                select(func.count()).select_from(EmployerJob).where(
                    EmployerJob.employer_id == employer.id,
                    EmployerJob.status == "active",
                )
            ) or 0
            employer_info = {
                "company_name": employer.company_name,
                "subscription_tier": employer.subscription_tier,
                "subscription_status": employer.subscription_status,
                "active_jobs": active_jobs,
            }

        # Recruiter info
        recruiter = db.scalar(
            select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
        )
        recruiter_info = None
        if recruiter:
            recruiter_info = {
                "company_name": recruiter.company_name,
                "subscription_tier": recruiter.subscription_tier,
                "subscription_status": recruiter.subscription_status,
                "seats_purchased": recruiter.seats_purchased,
                "seats_used": recruiter.seats_used,
            }

        # Usage
        usage_row = db.scalar(
            select(UsageCounter).where(
                UsageCounter.user_id == user.id,
                UsageCounter.period_start == first_of_month,
            )
        )
        daily_rows = db.execute(
            select(DailyUsageCounter.counter_name, DailyUsageCounter.count).where(
                DailyUsageCounter.user_id == user.id,
                DailyUsageCounter.date == today,
            )
        ).all()

        usage_info = {
            "monthly_match_refreshes": usage_row.match_refreshes if usage_row else 0,
            "monthly_tailor_requests": usage_row.tailor_requests if usage_row else 0,
            "daily_counters": {row[0]: row[1] for row in daily_rows},
        }

        # Recent activity — job runs via resume_documents
        job_runs = db.execute(
            select(JobRun)
            .join(ResumeDocument, JobRun.resume_document_id == ResumeDocument.id)
            .where(ResumeDocument.user_id == user.id)
            .order_by(JobRun.created_at.desc())
            .limit(10)
        ).scalars().all()

        activity: list[dict] = []
        for jr in job_runs:
            activity.append({
                "type": "job_run",
                "detail": f"{jr.job_type} (#{jr.id})",
                "status": jr.status,
                "created_at": jr.created_at,
            })

        # Trust audit entries
        trust_audits = db.execute(
            select(TrustAuditLog)
            .join(CandidateTrust, TrustAuditLog.trust_id == CandidateTrust.id)
            .join(
                ResumeDocument,
                CandidateTrust.resume_document_id == ResumeDocument.id,
            )
            .where(ResumeDocument.user_id == user.id)
            .order_by(TrustAuditLog.created_at.desc())
            .limit(5)
        ).scalars().all()

        for ta in trust_audits:
            activity.append({
                "type": "trust_audit",
                "detail": f"{ta.action}: {ta.prev_status} -> {ta.new_status}",
                "status": ta.new_status,
                "created_at": ta.created_at,
            })

        activity.sort(key=lambda a: a["created_at"], reverse=True)

        results.append({
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_admin": user.is_admin,
                "created_at": user.created_at,
                "onboarding_completed": user.onboarding_completed_at is not None,
                "mfa_required": user.mfa_required,
            },
            "candidate": candidate_info,
            "employer": employer_info,
            "recruiter": recruiter_info,
            "usage": usage_info,
            "recent_activity": activity,
        })

    return results


# ---------------------------------------------------------------------------
# Endpoint 3: GET /billing-issues
# ---------------------------------------------------------------------------


@router.get("/billing-issues", response_model=BillingIssuesResponse)
def billing_issues(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    past_due: list[dict] = []
    near_limits: list[dict] = []
    tier_mismatches: list[dict] = []

    # --- Past due across segments ---
    for row in db.execute(
        select(
            Candidate.user_id,
            User.email,
            Candidate.plan_tier,
            Candidate.subscription_status,
        )
        .join(User, Candidate.user_id == User.id)
        .where(Candidate.subscription_status == "past_due")
    ).all():
        past_due.append(BillingIssueUser(
            user_id=row[0], email=row[1], segment="candidate",
            tier=row[2] or "free", subscription_status=row[3],
        ).model_dump())

    for row in db.execute(
        select(
            EmployerProfile.user_id,
            User.email,
            EmployerProfile.subscription_tier,
            EmployerProfile.subscription_status,
        )
        .join(User, EmployerProfile.user_id == User.id)
        .where(EmployerProfile.subscription_status == "past_due")
    ).all():
        past_due.append(BillingIssueUser(
            user_id=row[0], email=row[1], segment="employer",
            tier=row[2], subscription_status=row[3],
        ).model_dump())

    for row in db.execute(
        select(
            RecruiterProfile.user_id,
            User.email,
            RecruiterProfile.subscription_tier,
            RecruiterProfile.subscription_status,
        )
        .join(User, RecruiterProfile.user_id == User.id)
        .where(RecruiterProfile.subscription_status == "past_due")
    ).all():
        past_due.append(BillingIssueUser(
            user_id=row[0], email=row[1], segment="recruiter",
            tier=row[2], subscription_status=row[3],
        ).model_dump())

    # --- Near limits (candidates daily counters >= 80% of tier limit) ---
    today = date.today()
    daily_rows = db.execute(
        select(
            DailyUsageCounter.user_id,
            User.email,
            Candidate.plan_tier,
            DailyUsageCounter.counter_name,
            DailyUsageCounter.count,
        )
        .join(User, DailyUsageCounter.user_id == User.id)
        .outerjoin(Candidate, Candidate.user_id == User.id)
        .where(DailyUsageCounter.date == today)
    ).all()

    for row in daily_rows:
        uid, email, tier, counter_name, count = row
        tier = tier or "free"
        tier_limits = CANDIDATE_PLAN_LIMITS.get(tier, {})
        limit = tier_limits.get(counter_name)
        if limit and isinstance(limit, int) and limit > 0 and count >= limit * 0.8:
            near_limits.append(BillingIssueUser(
                user_id=uid, email=email, segment="candidate",
                tier=tier, subscription_status=None,
                detail=f"{counter_name}: {count}/{limit}",
            ).model_dump())

    # --- Tier mismatches (plan_tier is paid but subscription canceled/past_due) ---
    for row in db.execute(
        select(
            Candidate.user_id,
            User.email,
            Candidate.plan_tier,
            Candidate.subscription_status,
        )
        .join(User, Candidate.user_id == User.id)
        .where(
            Candidate.plan_tier.in_(["starter", "pro"]),
            Candidate.subscription_status.in_(["canceled", "unpaid", None]),
        )
    ).all():
        tier_mismatches.append(BillingIssueUser(
            user_id=row[0], email=row[1], segment="candidate",
            tier=row[2] or "free", subscription_status=row[3],
            detail="Paid tier but subscription not active",
        ).model_dump())

    return {
        "past_due": past_due,
        "near_limits": near_limits,
        "tier_mismatches": tier_mismatches,
    }


# ---------------------------------------------------------------------------
# Endpoint 4: GET /queue-monitor
# ---------------------------------------------------------------------------


@router.get("/queue-monitor", response_model=QueueMonitorResponse)
def queue_monitor(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
):
    stats = get_queue_stats()
    queues = []

    for qdata in stats.get("queues", []):
        qname = qdata.get("name", "unknown")
        failed_count = qdata.get("failed", 0)
        failed_jobs = []
        if failed_count > 0:
            raw_failed = get_failed_jobs(qname, 10)
            for fj in raw_failed:
                failed_jobs.append({
                    "job_id": fj.get("job_id", ""),
                    "func_name": fj.get("func_name"),
                    "error": fj.get("exc_info") or fj.get("error"),
                    "enqueued_at": fj.get("enqueued_at"),
                    "ended_at": fj.get("ended_at"),
                })

        queues.append({
            "name": qname,
            "pending": qdata.get("pending", 0),
            "started": qdata.get("started", 0),
            "failed": failed_count,
            "deferred": qdata.get("deferred", 0),
            "failed_jobs": failed_jobs,
        })

    return {
        "redis_connected": stats.get("redis_connected", False),
        "queues": queues,
    }


# ---------------------------------------------------------------------------
# Endpoint 5: GET /feature-usage
# ---------------------------------------------------------------------------


@router.get("/feature-usage", response_model=FeatureUsageResponse)
def feature_usage(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    today = date.today()
    first_of_month = today.replace(day=1)
    period_str = today.strftime("%Y-%m")

    # Monthly totals from UsageCounter
    monthly = db.execute(
        select(
            func.coalesce(func.sum(UsageCounter.match_refreshes), 0),
            func.coalesce(func.sum(UsageCounter.tailor_requests), 0),
        ).where(UsageCounter.period_start == first_of_month)
    ).one()

    # Daily usage summary by counter_name
    daily_summary_rows = db.execute(
        select(
            DailyUsageCounter.counter_name,
            func.sum(DailyUsageCounter.count),
            func.count(func.distinct(DailyUsageCounter.user_id)),
        )
        .where(DailyUsageCounter.date == today)
        .group_by(DailyUsageCounter.counter_name)
    ).all()

    daily_usage_summary = {}
    for counter_name, total, unique_users in daily_summary_rows:
        daily_usage_summary[counter_name] = {
            "total": total,
            "unique_users": unique_users,
        }

    # Top 10 users by total monthly usage
    top_users_rows = db.execute(
        select(
            UsageCounter.user_id,
            User.email,
            (UsageCounter.match_refreshes + UsageCounter.tailor_requests).label(
                "total"
            ),
        )
        .join(User, UsageCounter.user_id == User.id)
        .where(UsageCounter.period_start == first_of_month)
        .order_by(
            (UsageCounter.match_refreshes + UsageCounter.tailor_requests).desc()
        )
        .limit(10)
    ).all()

    top_users = [
        {"user_id": r[0], "email": r[1], "total_usage": r[2]}
        for r in top_users_rows
    ]

    # Sieve stats
    now = datetime.now(UTC)
    total_conversations = db.scalar(
        select(func.count(func.distinct(SieveConversation.user_id)))
    ) or 0
    total_messages = db.scalar(
        select(func.count()).select_from(SieveConversation)
    ) or 0
    active_sieve_7d = db.scalar(
        select(func.count(func.distinct(SieveConversation.user_id))).where(
            SieveConversation.created_at >= now - timedelta(days=7)
        )
    ) or 0

    return {
        "period": period_str,
        "total_match_refreshes": monthly[0],
        "total_tailor_requests": monthly[1],
        "daily_usage_summary": daily_usage_summary,
        "top_users": top_users,
        "sieve_stats": {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "active_users_7d": active_sieve_7d,
        },
    }


# ---------------------------------------------------------------------------
# Endpoint 6: GET /audit-log
# ---------------------------------------------------------------------------


@router.get("/audit-log", response_model=AuditLogResponse)
def audit_log(
    page: int = Query(1, ge=1),  # noqa: B008
    page_size: int = Query(50, ge=1, le=200),  # noqa: B008
    source: str = Query("all"),  # noqa: B008
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    entries: list[dict] = []
    offset = (page - 1) * page_size

    # Trust audit entries
    if source in ("all", "trust"):
        trust_rows = db.execute(
            select(
                TrustAuditLog.id,
                TrustAuditLog.action,
                TrustAuditLog.actor_type,
                TrustAuditLog.details,
                TrustAuditLog.created_at,
                User.email,
            )
            .join(CandidateTrust, TrustAuditLog.trust_id == CandidateTrust.id)
            .join(
                ResumeDocument,
                CandidateTrust.resume_document_id == ResumeDocument.id,
            )
            .outerjoin(User, ResumeDocument.user_id == User.id)
            .order_by(TrustAuditLog.created_at.desc())
        ).all()

        for r in trust_rows:
            entries.append({
                "id": r[0],
                "source": "trust",
                "action": r[1],
                "actor": r[2],
                "user_email": r[5],
                "details": r[3],
                "created_at": r[4],
            })

    # Employer compliance entries
    if source in ("all", "compliance"):
        compliance_rows = db.execute(
            select(
                EmployerComplianceLog.id,
                EmployerComplianceLog.event_type,
                EmployerComplianceLog.event_data,
                EmployerComplianceLog.created_at,
                User.email,
            )
            .outerjoin(User, EmployerComplianceLog.user_id == User.id)
            .order_by(EmployerComplianceLog.created_at.desc())
        ).all()

        for r in compliance_rows:
            entries.append({
                "id": r[0],
                "source": "compliance",
                "action": r[1],
                "actor": None,
                "user_email": r[4],
                "details": r[2],
                "created_at": r[3],
            })

    # Sort combined and paginate in Python
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    total = len(entries)
    entries = entries[offset : offset + page_size]

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Endpoint 7: Quick Actions
# ---------------------------------------------------------------------------


@router.post("/actions/tier-override", response_model=ActionResponse)
def tier_override(
    body: TierOverrideRequest,
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    if body.segment == "candidate":
        candidate = db.scalar(
            select(Candidate).where(Candidate.user_id == body.user_id)
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        candidate.plan_tier = body.tier
        db.commit()
        return {"success": True, "message": f"Candidate tier set to {body.tier}"}

    elif body.segment == "employer":
        employer = db.scalar(
            select(EmployerProfile).where(EmployerProfile.user_id == body.user_id)
        )
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        employer.subscription_tier = body.tier
        db.commit()
        return {"success": True, "message": f"Employer tier set to {body.tier}"}

    elif body.segment == "recruiter":
        recruiter = db.scalar(
            select(RecruiterProfile).where(RecruiterProfile.user_id == body.user_id)
        )
        if not recruiter:
            raise HTTPException(status_code=404, detail="Recruiter not found")
        recruiter.subscription_tier = body.tier
        db.commit()
        return {"success": True, "message": f"Recruiter tier set to {body.tier}"}

    raise HTTPException(status_code=400, detail="Invalid segment")


@router.post("/actions/retry-queue/{queue_name}", response_model=ActionResponse)
def retry_queue(
    queue_name: str,
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
):
    from rq import Queue

    from app.services.worker_health import get_redis_connection

    try:
        conn = get_redis_connection()
        q = Queue(queue_name, connection=conn)
        failed_registry = q.failed_job_registry
        job_ids = failed_registry.get_job_ids()
        retried = 0
        for job_id in job_ids:
            try:
                failed_registry.requeue(job_id)
                retried += 1
            except Exception:
                pass
        return {
            "success": True,
            "message": f"Retried {retried}/{len(job_ids)} failed jobs in {queue_name}",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/actions/reparse/{user_id}", response_model=ActionResponse)
def reparse_resume(
    user_id: int,
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    doc = db.scalar(
        select(ResumeDocument)
        .where(ResumeDocument.user_id == user_id)
        .order_by(ResumeDocument.created_at.desc())
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No resume found for user")

    try:
        from rq import Queue

        from app.services.worker_health import get_redis_connection

        conn = get_redis_connection()
        q = Queue("parse", connection=conn)
        q.enqueue("app.worker.parse_resume", doc.id, user_id)
        return {"success": True, "message": f"Re-parse enqueued for user {user_id}"}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to enqueue: {exc}"
        ) from exc


@router.post("/actions/clear-daily-counters/{user_id}", response_model=ActionResponse)
def clear_daily_counters(
    user_id: int,
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = date.today()
    result = db.execute(
        text(
            "DELETE FROM daily_usage_counters WHERE user_id = :uid AND date = :d"
        ),
        {"uid": user_id, "d": today},
    )
    db.commit()
    return {
        "success": True,
        "message": f"Cleared {result.rowcount} daily counter(s) for user {user_id}",
    }


@router.post(
    "/actions/reset-monthly-usage/{user_id}", response_model=ActionResponse
)
def reset_monthly_usage(
    user_id: int,
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    first_of_month = date.today().replace(day=1)
    row = db.scalar(
        select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.period_start == first_of_month,
        )
    )
    if row:
        row.match_refreshes = 0
        row.tailor_requests = 0
        db.commit()
        return {"success": True, "message": f"Monthly usage reset for user {user_id}"}

    return {"success": True, "message": "No usage record found for current period"}
