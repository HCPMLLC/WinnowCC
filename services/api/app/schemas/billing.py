from __future__ import annotations

from pydantic import BaseModel


class UsageSummary(BaseModel):
    match_refreshes: int = 0
    tailor_requests: int = 0
    sieve_messages_today: int = 0
    semantic_searches_today: int = 0


class FeatureAccess(BaseModel):
    data_export: bool = False
    career_intelligence: bool = False
    ips_detail: str = "score_only"


class BillingStatusResponse(BaseModel):
    plan_tier: str  # "free", "starter", or "pro"
    billing_cycle: str | None  # "monthly", "annual", or None
    subscription_status: str | None  # "active", "past_due", "canceled", etc.
    match_refreshes_used: int
    match_refreshes_limit: int | None  # None = unlimited
    tailor_requests_used: int
    tailor_requests_limit: int | None  # None = unlimited
    usage: UsageSummary | None = None
    limits: dict | None = None
    features: FeatureAccess | None = None


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class UnifiedCheckoutRequest(BaseModel):
    segment: str = "candidate"  # "candidate", "employer", "recruiter"
    tier: str = "pro"  # plan tier within segment
    interval: str = "monthly"  # "monthly" or "annual"


class PortalSessionResponse(BaseModel):
    portal_url: str


class PlanTierDetail(BaseModel):
    tier: str
    limits: dict
    prices: dict  # {"monthly": int|str, "annual": int|str, ...}


class PlansResponse(BaseModel):
    segment: str
    tiers: list[PlanTierDetail]


class AdminPlanOverrideRequest(BaseModel):
    plan_tier: str  # "free", "starter", or "pro"
    billing_cycle: str | None = None
    segment: str = "candidate"  # "candidate", "employer", "recruiter"


class AdminPlanOverrideResponse(BaseModel):
    user_id: int
    plan_tier: str
    billing_cycle: str | None
    segment: str = "candidate"
