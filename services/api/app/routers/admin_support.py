"""Admin support dashboard router.

Provides system health, user lookup, billing diagnostics, queue monitoring,
feature usage analytics, audit trail, and quick admin actions.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_trust import CandidateTrust
from app.models.daily_usage_counter import DailyUsageCounter
from app.models.employer import EmployerJob, EmployerProfile
from app.models.employer_compliance_log import EmployerComplianceLog
from app.models.job_run import JobRun
from app.models.match import Match
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.resume_document import ResumeDocument
from app.models.sieve_conversation import SieveConversation
from app.models.tailored_resume import TailoredResume
from app.models.trust_audit_log import TrustAuditLog
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.schemas.admin_support import (
    ActionResponse,
    AuditLogResponse,
    BillingIssuesResponse,
    BillingIssueUser,
    CandidateKpis,
    EmployerKpis,
    FeatureUsageResponse,
    KpiDashboardResponse,
    MatchDiagnosticsResponse,
    MonthlyDataPoint,
    OverallKpis,
    OverviewResponse,
    QueueMonitorResponse,
    RecruiterKpis,
    TierOverrideRequest,
    TrendData,
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
    redis_status = {"status": "ok" if queue_stats.get("redis_connected") else "error"}

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
    users_7d = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= now - timedelta(days=7))
        )
        or 0
    )
    users_30d = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= now - timedelta(days=30))
        )
        or 0
    )

    # --- Billing stats ---
    candidate_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(Candidate.plan_tier, func.count()).group_by(Candidate.plan_tier)
        ).all()
    }
    employer_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(EmployerProfile.subscription_tier, func.count()).group_by(
                EmployerProfile.subscription_tier
            )
        ).all()
    }
    recruiter_tiers = {
        (k or "free"): v
        for k, v in db.execute(
            select(RecruiterProfile.subscription_tier, func.count()).group_by(
                RecruiterProfile.subscription_tier
            )
        ).all()
    }

    # --- Alerts ---
    alerts = []

    if total_failed > 0:
        alerts.append(
            {
                "type": "queue_failure",
                "severity": "error",
                "message": f"{total_failed} failed queue job(s)",
                "action_url": "/admin/support/queues",
            }
        )

    past_due_count = (
        db.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(Candidate.subscription_status == "past_due")
        )
        or 0
    )
    past_due_count += (
        db.scalar(
            select(func.count())
            .select_from(EmployerProfile)
            .where(EmployerProfile.subscription_status == "past_due")
        )
        or 0
    )
    past_due_count += (
        db.scalar(
            select(func.count())
            .select_from(RecruiterProfile)
            .where(RecruiterProfile.subscription_status == "past_due")
        )
        or 0
    )

    if past_due_count > 0:
        alerts.append(
            {
                "type": "past_due",
                "severity": "warning",
                "message": f"{past_due_count} subscription(s) past due",
                "action_url": "/admin/support/billing",
            }
        )

    trust_pending = (
        db.scalar(
            select(func.count())
            .select_from(CandidateTrust)
            .where(CandidateTrust.status.in_(["soft_quarantine", "hard_quarantine"]))
        )
        or 0
    )
    if trust_pending > 0:
        alerts.append(
            {
                "type": "trust_queue",
                "severity": "warning",
                "message": f"{trust_pending} candidate(s) in trust quarantine",
                "action_url": "/admin/trust",
            }
        )

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
            db.scalars(select(User).where(User.email.ilike(f"%{q}%")).limit(20)).all()
        )

    today = date.today()
    first_of_month = today.replace(day=1)
    results = []

    for user in users:
        # Candidate info
        candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.id))
        candidate_info = None
        if candidate:
            from app.models.match import Match

            match_count = (
                db.scalar(
                    select(func.count())
                    .select_from(Match)
                    .where(Match.user_id == user.id)
                )
                or 0
            )
            trust_record = db.scalar(
                select(CandidateTrust)
                .join(
                    ResumeDocument,
                    CandidateTrust.resume_document_id == ResumeDocument.id,
                )
                .where(
                    ResumeDocument.user_id == user.id,
                    ResumeDocument.deleted_at.is_(None),
                )
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
            active_jobs = (
                db.scalar(
                    select(func.count())
                    .select_from(EmployerJob)
                    .where(
                        EmployerJob.employer_id == employer.id,
                        EmployerJob.status == "active",
                    )
                )
                or 0
            )
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
        job_runs = (
            db.execute(
                select(JobRun)
                .join(ResumeDocument, JobRun.resume_document_id == ResumeDocument.id)
                .where(
                    ResumeDocument.user_id == user.id,
                    ResumeDocument.deleted_at.is_(None),
                )
                .order_by(JobRun.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        activity: list[dict] = []
        for jr in job_runs:
            activity.append(
                {
                    "type": "job_run",
                    "detail": f"{jr.job_type} (#{jr.id})",
                    "status": jr.status,
                    "created_at": jr.created_at,
                }
            )

        # Trust audit entries
        trust_audits = (
            db.execute(
                select(TrustAuditLog)
                .join(CandidateTrust, TrustAuditLog.trust_id == CandidateTrust.id)
                .join(
                    ResumeDocument,
                    CandidateTrust.resume_document_id == ResumeDocument.id,
                )
                .where(
                    ResumeDocument.user_id == user.id,
                    ResumeDocument.deleted_at.is_(None),
                )
                .order_by(TrustAuditLog.created_at.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )

        for ta in trust_audits:
            activity.append(
                {
                    "type": "trust_audit",
                    "detail": f"{ta.action}: {ta.prev_status} -> {ta.new_status}",
                    "status": ta.new_status,
                    "created_at": ta.created_at,
                }
            )

        activity.sort(key=lambda a: a["created_at"], reverse=True)

        results.append(
            {
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
            }
        )

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
        past_due.append(
            BillingIssueUser(
                user_id=row[0],
                email=row[1],
                segment="candidate",
                tier=row[2] or "free",
                subscription_status=row[3],
            ).model_dump()
        )

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
        past_due.append(
            BillingIssueUser(
                user_id=row[0],
                email=row[1],
                segment="employer",
                tier=row[2],
                subscription_status=row[3],
            ).model_dump()
        )

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
        past_due.append(
            BillingIssueUser(
                user_id=row[0],
                email=row[1],
                segment="recruiter",
                tier=row[2],
                subscription_status=row[3],
            ).model_dump()
        )

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
            near_limits.append(
                BillingIssueUser(
                    user_id=uid,
                    email=email,
                    segment="candidate",
                    tier=tier,
                    subscription_status=None,
                    detail=f"{counter_name}: {count}/{limit}",
                ).model_dump()
            )

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
        tier_mismatches.append(
            BillingIssueUser(
                user_id=row[0],
                email=row[1],
                segment="candidate",
                tier=row[2] or "free",
                subscription_status=row[3],
                detail="Paid tier but subscription not active",
            ).model_dump()
        )

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
                failed_jobs.append(
                    {
                        "job_id": fj.get("job_id", ""),
                        "func_name": fj.get("func_name"),
                        "error": fj.get("exc_info") or fj.get("error"),
                        "enqueued_at": fj.get("enqueued_at"),
                        "ended_at": fj.get("ended_at"),
                    }
                )

        queues.append(
            {
                "name": qname,
                "pending": qdata.get("pending", 0),
                "started": qdata.get("started", 0),
                "failed": failed_count,
                "deferred": qdata.get("deferred", 0),
                "failed_jobs": failed_jobs,
            }
        )

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
        .order_by((UsageCounter.match_refreshes + UsageCounter.tailor_requests).desc())
        .limit(10)
    ).all()

    top_users = [
        {"user_id": r[0], "email": r[1], "total_usage": r[2]} for r in top_users_rows
    ]

    # Sieve stats
    now = datetime.now(UTC)
    total_conversations = (
        db.scalar(select(func.count(func.distinct(SieveConversation.user_id)))) or 0
    )
    total_messages = db.scalar(select(func.count()).select_from(SieveConversation)) or 0
    active_sieve_7d = (
        db.scalar(
            select(func.count(func.distinct(SieveConversation.user_id))).where(
                SieveConversation.created_at >= now - timedelta(days=7)
            )
        )
        or 0
    )

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
                (CandidateTrust.resume_document_id == ResumeDocument.id)
                & ResumeDocument.deleted_at.is_(None),
            )
            .outerjoin(User, ResumeDocument.user_id == User.id)
            .order_by(TrustAuditLog.created_at.desc())
        ).all()

        for r in trust_rows:
            entries.append(
                {
                    "id": r[0],
                    "source": "trust",
                    "action": r[1],
                    "actor": r[2],
                    "user_email": r[5],
                    "details": r[3],
                    "created_at": r[4],
                }
            )

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
            entries.append(
                {
                    "id": r[0],
                    "source": "compliance",
                    "action": r[1],
                    "actor": None,
                    "user_email": r[4],
                    "details": r[2],
                    "created_at": r[3],
                }
            )

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
        .where(ResumeDocument.user_id == user_id, ResumeDocument.active())
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
        text("DELETE FROM daily_usage_counters WHERE user_id = :uid AND date = :d"),
        {"uid": user_id, "d": today},
    )
    db.commit()
    return {
        "success": True,
        "message": f"Cleared {result.rowcount} daily counter(s) for user {user_id}",
    }


@router.post("/actions/reset-monthly-usage/{user_id}", response_model=ActionResponse)
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


# ---------------------------------------------------------------------------
# Endpoint 8: GET /match-diagnostics
# ---------------------------------------------------------------------------


@router.get("/match-diagnostics", response_model=MatchDiagnosticsResponse)
def match_diagnostics(
    email: str = Query(..., min_length=1),  # noqa: B008
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    from app.models.candidate_profile import CandidateProfile
    from app.models.job import Job
    from app.models.match import Match

    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Profile
    profile = db.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    pj = profile.profile_json if profile else None
    prefs = (pj.get("preferences") or {}) if isinstance(pj, dict) else {}
    skills = (pj.get("skills") or []) if isinstance(pj, dict) else []
    target_titles = prefs.get("target_titles") or []

    # Ingest query that would be built
    ingest_query = None
    if pj:
        from app.services.resume_parse_job import _build_ingest_query_from_profile

        ingest_query = _build_ingest_query_from_profile(pj)

    # Matches
    total_matches = (
        db.scalar(
            select(func.count()).select_from(Match).where(Match.user_id == user.id)
        )
        or 0
    )
    cutoff = datetime.now(UTC) - timedelta(days=14)
    recent_matches = (
        db.scalar(
            select(func.count())
            .select_from(Match)
            .join(Job, Match.job_id == Job.id)
            .where(
                Match.user_id == user.id,
                Job.posted_at.is_not(None),
                Job.posted_at >= cutoff,
                Job.is_active.is_not(False),
            )
        )
        or 0
    )

    # Recent jobs in DB
    total_recent_jobs = (
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.posted_at.is_not(None),
                Job.posted_at >= cutoff,
                Job.is_active.is_not(False),
            )
        )
        or 0
    )

    # Trust
    trust_record = db.scalar(
        select(CandidateTrust)
        .join(ResumeDocument, CandidateTrust.resume_document_id == ResumeDocument.id)
        .where(
            ResumeDocument.user_id == user.id,
            ResumeDocument.deleted_at.is_(None),
        )
        .order_by(CandidateTrust.id.desc())
        .limit(1)
    )

    # Diagnosis
    diagnosis: list[str] = []
    if not user.onboarding_completed_at:
        diagnosis.append("Onboarding not completed.")
    if profile is None:
        diagnosis.append("No candidate profile. Resume may not have been parsed.")
    elif not skills:
        diagnosis.append("Profile has 0 skills. Match scores will be very low.")
    if not target_titles:
        diagnosis.append(
            "No target titles in preferences. Ingestion query uses fallback."
        )
    if trust_record is None:
        diagnosis.append("No trust record. User hasn't uploaded a resume.")
    elif trust_record.status != "allowed":
        diagnosis.append(f"Trust status is '{trust_record.status}' (not allowed).")
    if total_recent_jobs == 0:
        diagnosis.append("0 recent jobs in database. Job ingestion may not be running.")
    if total_matches > 0 and recent_matches == 0:
        diagnosis.append(
            f"{total_matches} total matches but 0 within display window. "
            "Matches are stale — user needs to refresh."
        )
    if total_matches == 0 and profile is not None:
        diagnosis.append("0 match records. User may have never refreshed matches.")
    if not diagnosis:
        diagnosis.append("No issues detected.")

    return {
        "user_id": user.id,
        "email": user.email,
        "has_profile": profile is not None,
        "profile_version": profile.version if profile else None,
        "skills_count": len(skills),
        "target_titles": target_titles,
        "ingest_query": ingest_query,
        "total_matches": total_matches,
        "recent_matches": recent_matches,
        "total_recent_jobs": total_recent_jobs,
        "trust_status": trust_record.status if trust_record else None,
        "diagnosis": diagnosis,
    }


# ---------------------------------------------------------------------------
# Endpoint: GET /kpi-dashboard  (founder-only summary dashboard)
# ---------------------------------------------------------------------------


@router.get("/kpi-dashboard", response_model=KpiDashboardResponse)
def kpi_dashboard(
    admin: User = Depends(require_admin_user),  # noqa: ARG001, B008
    db: Session = Depends(get_session),  # noqa: B008
):
    """Aggregate KPI summary across all three user segments with 12-month trends."""
    now = datetime.now(UTC)
    one_year_ago = now - timedelta(days=365)

    # ------------------------------------------------------------------ #
    # Overall                                                              #
    # ------------------------------------------------------------------ #
    role_counts: dict[str, int] = {
        (k or "unknown"): v
        for k, v in db.execute(
            select(User.role, func.count()).group_by(User.role)
        ).all()
    }
    total_users = sum(role_counts.values())
    new_7d = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= now - timedelta(days=7))
        )
        or 0
    )
    new_30d = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= now - timedelta(days=30))
        )
        or 0
    )

    # ------------------------------------------------------------------ #
    # Candidates                                                           #
    # ------------------------------------------------------------------ #
    cand_by_tier: dict[str, int] = {
        (t or "free"): c
        for t, c in db.execute(
            select(Candidate.plan_tier, func.count()).group_by(Candidate.plan_tier)
        ).all()
    }
    total_cands = sum(cand_by_tier.values()) or 1  # avoid div-zero

    cands_with_resume = (
        db.scalar(
            select(func.count(func.distinct(ResumeDocument.user_id))).where(
                ResumeDocument.deleted_at.is_(None)
            )
        )
        or 0
    )
    resume_upload_rate = cands_with_resume / total_cands

    match_count, avg_score_raw = db.execute(
        select(func.count(), func.avg(Match.match_score)).select_from(Match)
    ).one()
    total_matches = match_count or 0
    avg_match_score = float(avg_score_raw or 0)
    avg_matches_per_cand = total_matches / total_cands

    funnel: dict[str, int] = {
        s: c
        for s, c in db.execute(
            select(Match.application_status, func.count())
            .where(Match.application_status.isnot(None))
            .group_by(Match.application_status)
        ).all()
    }

    tailor_total = db.scalar(select(func.count()).select_from(TailoredResume)) or 0

    sieve_users = (
        db.scalar(select(func.count(func.distinct(SieveConversation.user_id)))) or 0
    )
    sieve_rate = sieve_users / total_cands

    cand_onboarded = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "candidate",
                User.onboarding_completed_at.isnot(None),
            )
        )
        or 0
    )
    cand_onboard_rate = cand_onboarded / total_cands

    # ------------------------------------------------------------------ #
    # Employers                                                            #
    # ------------------------------------------------------------------ #
    emp_by_tier: dict[str, int] = {
        (t or "free"): c
        for t, c in db.execute(
            select(EmployerProfile.subscription_tier, func.count()).group_by(
                EmployerProfile.subscription_tier
            )
        ).all()
    }
    total_emps = sum(emp_by_tier.values()) or 1

    active_jobs = (
        db.scalar(
            select(func.count())
            .select_from(EmployerJob)
            .where(EmployerJob.status == "active", EmployerJob.archived.is_(False))
        )
        or 0
    )
    avg_jobs_per_emp = active_jobs / total_emps

    avg_views_raw, avg_apps_raw = db.execute(
        select(
            func.avg(EmployerJob.view_count), func.avg(EmployerJob.application_count)
        ).select_from(EmployerJob)
    ).one()
    avg_views = float(avg_views_raw or 0)
    avg_apps = float(avg_apps_raw or 0)

    emp_onboarded = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "employer",
                User.onboarding_completed_at.isnot(None),
            )
        )
        or 0
    )
    emp_onboard_rate = emp_onboarded / total_emps

    # ------------------------------------------------------------------ #
    # Recruiters                                                           #
    # ------------------------------------------------------------------ #
    rec_by_tier: dict[str, int] = {
        (t or "trial"): c
        for t, c in db.execute(
            select(RecruiterProfile.subscription_tier, func.count()).group_by(
                RecruiterProfile.subscription_tier
            )
        ).all()
    }
    total_recs = sum(rec_by_tier.values()) or 1

    pipeline_total = (
        db.scalar(select(func.count()).select_from(RecruiterPipelineCandidate)) or 0
    )
    avg_pipeline = pipeline_total / total_recs

    stage_dist: dict[str, int] = {
        s: c
        for s, c in db.execute(
            select(RecruiterPipelineCandidate.stage, func.count()).group_by(
                RecruiterPipelineCandidate.stage
            )
        ).all()
    }

    seat_rows = db.execute(
        select(RecruiterProfile.seats_purchased, RecruiterProfile.seats_used).where(
            RecruiterProfile.subscription_tier.in_(["team", "agency"])
        )
    ).all()
    util_vals = [u / p for p, u in seat_rows if p and p > 0]
    avg_seat_util = sum(util_vals) / len(util_vals) if util_vals else 0.0

    jobs_posted = (
        db.scalar(
            select(func.count())
            .select_from(RecruiterJob)
            .where(RecruiterJob.status != "draft")
        )
        or 0
    )

    rec_onboarded = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "recruiter",
                User.onboarding_completed_at.isnot(None),
            )
        )
        or 0
    )
    rec_onboard_rate = rec_onboarded / total_recs

    # ------------------------------------------------------------------ #
    # Trend data — last 12 months                                         #
    # ------------------------------------------------------------------ #
    # Build ordered list of (year, month) tuples for the last 12 months
    month_tuples: list[tuple[int, int]] = []
    for i in range(11, -1, -1):
        d = now - timedelta(days=30 * i)
        month_tuples.append((d.year, d.month))
    month_labels = [f"{y}-{m:02d}" for y, m in month_tuples]

    def _signups_by_role(role: str) -> list[int]:
        rows = db.execute(
            select(
                extract("year", User.created_at).label("y"),
                extract("month", User.created_at).label("m"),
                func.count(),
            )
            .where(User.role == role, User.created_at >= one_year_ago)
            .group_by("y", "m")
        ).all()
        lk = {(int(r.y), int(r.m)): r[2] for r in rows}
        return [lk.get(t, 0) for t in month_tuples]

    def _paid_candidates() -> list[int]:
        rows = db.execute(
            select(
                extract("year", Candidate.updated_at).label("y"),
                extract("month", Candidate.updated_at).label("m"),
                func.count(),
            )
            .where(
                Candidate.plan_tier.notin_(["free"]),
                Candidate.plan_tier.isnot(None),
                Candidate.subscription_status == "active",
                Candidate.updated_at >= one_year_ago,
            )
            .group_by("y", "m")
        ).all()
        lk = {(int(r.y), int(r.m)): r[2] for r in rows}
        return [lk.get(t, 0) for t in month_tuples]

    def _paid_employers() -> list[int]:
        rows = db.execute(
            select(
                extract("year", EmployerProfile.current_period_start).label("y"),
                extract("month", EmployerProfile.current_period_start).label("m"),
                func.count(),
            )
            .where(
                EmployerProfile.subscription_tier.notin_(["free"]),
                EmployerProfile.subscription_tier.isnot(None),
                EmployerProfile.subscription_status == "active",
                EmployerProfile.current_period_start.isnot(None),
                EmployerProfile.current_period_start >= one_year_ago,
            )
            .group_by("y", "m")
        ).all()
        lk = {(int(r.y), int(r.m)): r[2] for r in rows}
        return [lk.get(t, 0) for t in month_tuples]

    def _paid_recruiters() -> list[int]:
        rows = db.execute(
            select(
                extract("year", RecruiterProfile.updated_at).label("y"),
                extract("month", RecruiterProfile.updated_at).label("m"),
                func.count(),
            )
            .where(
                RecruiterProfile.subscription_tier.notin_(["trial"]),
                RecruiterProfile.subscription_tier.isnot(None),
                RecruiterProfile.subscription_status == "active",
                RecruiterProfile.updated_at.isnot(None),
                RecruiterProfile.updated_at >= one_year_ago,
            )
            .group_by("y", "m")
        ).all()
        lk = {(int(r.y), int(r.m)): r[2] for r in rows}
        return [lk.get(t, 0) for t in month_tuples]

    cand_sig = _signups_by_role("candidate")
    cand_paid = _paid_candidates()
    emp_sig = _signups_by_role("employer")
    emp_paid = _paid_employers()
    rec_sig = _signups_by_role("recruiter")
    rec_paid = _paid_recruiters()

    def _build_trend(signups: list[int], paid: list[int]) -> TrendData:
        return TrendData(
            points=[
                MonthlyDataPoint(
                    month=month_labels[i], new_signups=signups[i], new_paid=paid[i]
                )
                for i in range(len(month_labels))
            ]
        )

    trends = {
        "candidates": _build_trend(cand_sig, cand_paid),
        "employers": _build_trend(emp_sig, emp_paid),
        "recruiters": _build_trend(rec_sig, rec_paid),
        "total": _build_trend(
            [cand_sig[i] + emp_sig[i] + rec_sig[i] for i in range(len(month_tuples))],
            [
                cand_paid[i] + emp_paid[i] + rec_paid[i]
                for i in range(len(month_tuples))
            ],
        ),
    }

    return KpiDashboardResponse(
        overall=OverallKpis(
            total_users=total_users,
            users_by_role=role_counts,
            new_users_7d=new_7d,
            new_users_30d=new_30d,
        ),
        candidates=CandidateKpis(
            total=total_cands,
            by_tier=cand_by_tier,
            resume_upload_rate=round(resume_upload_rate, 4),
            avg_matches_per_candidate=round(avg_matches_per_cand, 2),
            avg_match_score=round(avg_match_score, 1),
            application_funnel=funnel,
            tailored_resumes_total=tailor_total,
            sieve_adoption_rate=round(sieve_rate, 4),
            onboarding_completion_rate=round(cand_onboard_rate, 4),
        ),
        employers=EmployerKpis(
            total=total_emps,
            by_tier=emp_by_tier,
            active_jobs=active_jobs,
            avg_jobs_per_employer=round(avg_jobs_per_emp, 2),
            avg_views_per_job=round(avg_views, 1),
            avg_applications_per_job=round(avg_apps, 1),
            onboarding_completion_rate=round(emp_onboard_rate, 4),
        ),
        recruiters=RecruiterKpis(
            total=total_recs,
            by_tier=rec_by_tier,
            total_pipeline_candidates=pipeline_total,
            avg_pipeline_per_recruiter=round(avg_pipeline, 2),
            pipeline_stage_distribution=stage_dist,
            avg_seat_utilization=round(avg_seat_util, 4),
            total_jobs_posted=jobs_posted,
            onboarding_completion_rate=round(rec_onboard_rate, 4),
        ),
        trends=trends,
        generated_at=now,
    )
