"""Admin support dashboard schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# --- Overview ---


class ServiceStatus(BaseModel):
    status: str  # "ok" | "error"
    detail: str | None = None


class QueueSummary(BaseModel):
    redis_connected: bool
    total_pending: int
    total_failed: int
    queues: dict  # queue_name -> {pending, started, failed, deferred}


class SystemHealth(BaseModel):
    api: ServiceStatus
    database: ServiceStatus
    redis: ServiceStatus
    queues: QueueSummary


class PlatformStats(BaseModel):
    total_users: int
    users_by_role: dict[str, int]
    users_created_last_7d: int
    users_created_last_30d: int


class BillingStats(BaseModel):
    candidates_by_tier: dict[str, int]
    employers_by_tier: dict[str, int]
    recruiters_by_tier: dict[str, int]


class Alert(BaseModel):
    type: str  # "queue_failure" | "past_due" | "trust_queue"
    severity: str  # "error" | "warning" | "info"
    message: str
    action_url: str | None = None


class OverviewResponse(BaseModel):
    system_health: SystemHealth
    platform_stats: PlatformStats
    billing_stats: BillingStats
    alerts: list[Alert]


# --- User Lookup ---


class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    is_admin: bool
    created_at: datetime
    onboarding_completed: bool
    mfa_required: bool


class CandidateInfo(BaseModel):
    plan_tier: str | None
    subscription_status: str | None
    match_count: int
    trust_status: str | None = None


class EmployerInfo(BaseModel):
    company_name: str
    subscription_tier: str
    subscription_status: str | None
    active_jobs: int


class RecruiterInfo(BaseModel):
    company_name: str
    subscription_tier: str
    subscription_status: str | None
    seats_purchased: int
    seats_used: int


class UsageInfo(BaseModel):
    monthly_match_refreshes: int
    monthly_tailor_requests: int
    daily_counters: dict[str, int]  # counter_name -> count


class ActivityEntry(BaseModel):
    type: str  # "job_run" | "trust_audit"
    detail: str
    status: str | None = None
    created_at: datetime


class UserLookupResult(BaseModel):
    user: UserInfo
    candidate: CandidateInfo | None = None
    employer: EmployerInfo | None = None
    recruiter: RecruiterInfo | None = None
    usage: UsageInfo
    recent_activity: list[ActivityEntry]


# --- Billing Issues ---


class BillingIssueUser(BaseModel):
    user_id: int
    email: str
    segment: str  # "candidate" | "employer" | "recruiter"
    tier: str
    subscription_status: str | None
    detail: str | None = None


class BillingIssuesResponse(BaseModel):
    past_due: list[BillingIssueUser]
    near_limits: list[BillingIssueUser]
    tier_mismatches: list[BillingIssueUser]


# --- Queue Monitor ---


class FailedJob(BaseModel):
    job_id: str
    func_name: str | None = None
    error: str | None = None
    enqueued_at: str | None = None
    ended_at: str | None = None


class QueueDetail(BaseModel):
    name: str
    pending: int
    started: int
    failed: int
    deferred: int
    failed_jobs: list[FailedJob]


class QueueMonitorResponse(BaseModel):
    redis_connected: bool
    queues: list[QueueDetail]


# --- Feature Usage ---


class FeatureUsageResponse(BaseModel):
    period: str  # e.g. "2026-02"
    total_match_refreshes: int
    total_tailor_requests: int
    daily_usage_summary: dict[str, dict]  # counter_name -> {total, unique_users}
    top_users: list[dict]  # [{user_id, email, total_usage}]
    sieve_stats: dict  # {total_conversations, total_messages, active_users_7d}


# --- Audit Log ---


class AuditEntry(BaseModel):
    id: int
    source: str  # "trust" | "compliance"
    action: str
    actor: str | None = None
    user_email: str | None = None
    details: dict | None = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    page: int
    page_size: int


# --- Actions ---


class TierOverrideRequest(BaseModel):
    user_id: int
    segment: str  # "candidate" | "employer" | "recruiter"
    tier: str


class ActionResponse(BaseModel):
    success: bool
    message: str


# --- Match Diagnostics ---


class MatchDiagnosticsResponse(BaseModel):
    user_id: int
    email: str
    has_profile: bool
    profile_version: int | None = None
    skills_count: int = 0
    target_titles: list[str] = []
    ingest_query: dict | None = None
    total_matches: int = 0
    recent_matches: int = 0
    total_recent_jobs: int = 0
    trust_status: str | None = None
    diagnosis: list[str] = []
