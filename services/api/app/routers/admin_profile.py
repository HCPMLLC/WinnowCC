import re
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.employer import EmployerJob, EmployerProfile, EmployerSavedCandidate
from app.models.recruiter import RecruiterProfile, RecruiterTeamMember
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.user import User
from app.schemas.profile import (
    CandidateProfileResponse,
    CandidateProfileUpdateRequest,
    ProfileCompletenessResponse,
)
from app.services.auth import require_admin_user
from app.services.cascade_delete import cascade_delete_user
from app.services.profile_parser import default_profile_json
from app.services.profile_scoring import compute_profile_completeness

router = APIRouter(prefix="/api/admin/profile", tags=["admin-profile"])


class UserSummary(BaseModel):
    id: int
    email: str
    name: str | None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    company_name: str | None = None
    completeness_score: int
    onboarding_completed: bool


# --- Purge schemas ---

_TEST_EMAIL_RE = re.compile(r"(test|example)", re.IGNORECASE)


class PurgeableUser(BaseModel):
    id: int
    email: str
    name: str | None
    reason: str  # "test" | "inactive"
    created_at: datetime | None


class PurgeRequest(BaseModel):
    user_ids: list[int]


class PurgeResponse(BaseModel):
    deleted_count: int
    message: str


# --- Static-path routes (must come before /{user_id} dynamic routes) ---


@router.get("/users", response_model=list[UserSummary])
def list_users(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[UserSummary]:
    stmt = select(User).order_by(User.id.desc())
    users = session.execute(stmt).scalars().all()

    # Pre-fetch company names for employer and recruiter users
    employer_companies: dict[int, str] = {}
    for ep in session.execute(select(EmployerProfile)).scalars().all():
        employer_companies[ep.user_id] = ep.company_name or ""
    recruiter_companies: dict[int, str] = {}
    for rp in session.execute(select(RecruiterProfile)).scalars().all():
        recruiter_companies[rp.user_id] = rp.company_name or ""

    results = []
    for user in users:
        profile_stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
        profile = session.execute(profile_stmt).scalars().first()
        if profile:
            profile_json = profile.profile_json
            completeness = compute_profile_completeness(profile_json)
            name = profile_json.get("basics", {}).get("name")
        else:
            completeness = compute_profile_completeness(default_profile_json())
            name = None

        company_name = (
            employer_companies.get(user.id) or recruiter_companies.get(user.id) or None
        )

        results.append(
            UserSummary(
                id=user.id,
                email=user.email,
                name=name,
                first_name=user.first_name,
                last_name=user.last_name,
                full_name=user.full_name,
                phone=user.phone,
                role=user.role,
                company_name=company_name,
                completeness_score=completeness.score,
                onboarding_completed=user.onboarding_completed_at is not None,
            )
        )
    return results


@router.get("/purgeable", response_model=list[PurgeableUser])
def list_purgeable_users(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[PurgeableUser]:
    """Scan for test or inactive accounts that can be purged."""
    cutoff = datetime.now(UTC) - timedelta(days=30)

    users = session.execute(select(User).order_by(User.id)).scalars().all()

    # Pre-fetch user IDs that have at least one candidate profile
    users_with_profile = set(
        session.execute(select(CandidateProfile.user_id).distinct()).scalars().all()
    )

    results: list[PurgeableUser] = []
    for user in users:
        reason = None

        # Test accounts: email matches test/example patterns
        if _TEST_EMAIL_RE.search(user.email or ""):
            reason = "test"
        # Inactive accounts: no candidate profile and created > 30 days ago
        elif (
            user.id not in users_with_profile
            and user.created_at
            and user.created_at.replace(tzinfo=UTC) < cutoff
        ):
            reason = "inactive"

        if reason:
            # Try to get name from latest profile
            name = None
            profile = session.execute(
                select(CandidateProfile)
                .where(CandidateProfile.user_id == user.id)
                .order_by(CandidateProfile.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if profile and profile.profile_json:
                name = profile.profile_json.get("basics", {}).get("name")

            results.append(
                PurgeableUser(
                    id=user.id,
                    email=user.email,
                    name=name,
                    reason=reason,
                    created_at=user.created_at,
                )
            )

    return results


@router.post("/purge", response_model=PurgeResponse)
def purge_users(
    payload: PurgeRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> PurgeResponse:
    """Delete selected purgeable users and all their associated data."""
    if not payload.user_ids:
        raise HTTPException(status_code=400, detail="No user IDs provided.")

    deleted_count = 0
    for user_id in payload.user_ids:
        if cascade_delete_user(session, user_id):
            deleted_count += 1

    session.commit()

    return PurgeResponse(
        deleted_count=deleted_count,
        message=f"Successfully purged {deleted_count} user(s).",
    )


# --- Role-aware detail schemas ---


class AdminUserBasics(BaseModel):
    id: int
    email: str
    role: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    phone: str | None = None
    created_at: datetime | None = None
    onboarding_completed: bool = False


class AdminRecruiterProfileData(BaseModel):
    profile_id: int
    company_name: str
    company_type: str | None = None
    company_website: str | None = None
    specializations: list | None = None
    subscription_tier: str = "trial"
    subscription_status: str | None = None
    billing_interval: str | None = None
    billing_exempt: bool = False
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    is_trial_active: bool = False
    trial_days_remaining: int = 0
    seats_purchased: int = 1
    seats_used: int = 1
    auto_populate_pipeline: bool = False
    candidate_briefs_used: int = 0
    salary_lookups_used: int = 0
    job_uploads_used: int = 0
    intro_requests_used: int = 0
    resume_imports_used: int = 0
    outreach_enrollments_used: int = 0
    team_member_count: int = 0
    client_count: int = 0
    pipeline_candidate_count: int = 0
    jobs_count: int = 0
    created_at: datetime | None = None


class AdminEmployerProfileData(BaseModel):
    profile_id: int
    company_name: str
    company_size: str | None = None
    industry: str | None = None
    company_website: str | None = None
    company_description: str | None = None
    company_logo_url: str | None = None
    billing_email: str | None = None
    contact_first_name: str | None = None
    contact_last_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    subscription_tier: str = "free"
    subscription_status: str | None = None
    trial_ends_at: datetime | None = None
    ai_parsing_used: int = 0
    intro_requests_used: int = 0
    total_jobs_count: int = 0
    active_jobs_count: int = 0
    saved_candidates_count: int = 0
    created_at: datetime | None = None


class AdminProfileDetailResponse(BaseModel):
    user: AdminUserBasics
    role: str
    candidate_profile: CandidateProfileResponse | None = None
    recruiter_profile: AdminRecruiterProfileData | None = None
    employer_profile: AdminEmployerProfileData | None = None


class AdminUserBasicsUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


# --- Dynamic /{user_id} routes (must come after static-prefix routes) ---


@router.get("/{user_id}", response_model=AdminProfileDetailResponse)
def get_user_profile(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> AdminProfileDetailResponse:
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    user_basics = AdminUserBasics(
        id=target_user.id,
        email=target_user.email,
        role=target_user.role,
        first_name=target_user.first_name,
        last_name=target_user.last_name,
        full_name=target_user.full_name,
        phone=target_user.phone,
        created_at=target_user.created_at,
        onboarding_completed=target_user.onboarding_completed_at is not None,
    )

    role = target_user.role or "candidate"
    result = AdminProfileDetailResponse(user=user_basics, role=role)

    if role == "recruiter":
        rp = session.execute(
            select(RecruiterProfile).where(RecruiterProfile.user_id == user_id)
        ).scalar_one_or_none()
        if rp:
            team_count = (
                session.execute(
                    select(func.count(RecruiterTeamMember.id)).where(
                        RecruiterTeamMember.recruiter_profile_id == rp.id
                    )
                ).scalar()
                or 0
            )
            client_count = (
                session.execute(
                    select(func.count(RecruiterClient.id)).where(
                        RecruiterClient.recruiter_profile_id == rp.id
                    )
                ).scalar()
                or 0
            )
            pipeline_count = (
                session.execute(
                    select(func.count(RecruiterPipelineCandidate.id)).where(
                        RecruiterPipelineCandidate.recruiter_profile_id == rp.id
                    )
                ).scalar()
                or 0
            )
            jobs_count = (
                session.execute(
                    select(func.count(RecruiterJob.id)).where(
                        RecruiterJob.recruiter_profile_id == rp.id
                    )
                ).scalar()
                or 0
            )
            result.recruiter_profile = AdminRecruiterProfileData(
                profile_id=rp.id,
                company_name=rp.company_name,
                company_type=rp.company_type,
                company_website=rp.company_website,
                specializations=rp.specializations,
                subscription_tier=rp.subscription_tier or "trial",
                subscription_status=rp.subscription_status,
                billing_interval=rp.billing_interval,
                billing_exempt=rp.billing_exempt,
                trial_started_at=rp.trial_started_at,
                trial_ends_at=rp.trial_ends_at,
                is_trial_active=rp.is_trial_active,
                trial_days_remaining=rp.trial_days_remaining,
                seats_purchased=rp.seats_purchased,
                seats_used=rp.seats_used,
                auto_populate_pipeline=rp.auto_populate_pipeline,
                candidate_briefs_used=rp.candidate_briefs_used,
                salary_lookups_used=rp.salary_lookups_used,
                job_uploads_used=rp.job_uploads_used,
                intro_requests_used=rp.intro_requests_used,
                resume_imports_used=rp.resume_imports_used,
                outreach_enrollments_used=rp.outreach_enrollments_used,
                team_member_count=team_count,
                client_count=client_count,
                pipeline_candidate_count=pipeline_count,
                jobs_count=jobs_count,
                created_at=rp.created_at,
            )
    elif role == "employer":
        ep = session.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == user_id)
        ).scalar_one_or_none()
        if ep:
            total_jobs = (
                session.execute(
                    select(func.count(EmployerJob.id)).where(
                        EmployerJob.employer_id == ep.id
                    )
                ).scalar()
                or 0
            )
            active_jobs = (
                session.execute(
                    select(func.count(EmployerJob.id)).where(
                        EmployerJob.employer_id == ep.id,
                        EmployerJob.status == "active",
                    )
                ).scalar()
                or 0
            )
            saved_count = (
                session.execute(
                    select(func.count(EmployerSavedCandidate.id)).where(
                        EmployerSavedCandidate.employer_id == ep.id
                    )
                ).scalar()
                or 0
            )
            result.employer_profile = AdminEmployerProfileData(
                profile_id=ep.id,
                company_name=ep.company_name,
                company_size=ep.company_size,
                industry=ep.industry,
                company_website=ep.company_website,
                company_description=ep.company_description,
                company_logo_url=ep.company_logo_url,
                billing_email=ep.billing_email,
                contact_first_name=ep.contact_first_name,
                contact_last_name=ep.contact_last_name,
                contact_email=ep.contact_email,
                contact_phone=ep.contact_phone,
                subscription_tier=ep.subscription_tier or "free",
                subscription_status=ep.subscription_status,
                trial_ends_at=ep.trial_ends_at,
                ai_parsing_used=ep.ai_parsing_used,
                intro_requests_used=ep.intro_requests_used,
                total_jobs_count=total_jobs,
                active_jobs_count=active_jobs,
                saved_candidates_count=saved_count,
                created_at=ep.created_at,
            )
    else:
        # Candidate (default)
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
        profile = session.execute(stmt).scalars().first()
        if profile is None:
            result.candidate_profile = CandidateProfileResponse(
                version=0, profile_json=default_profile_json()
            )
        else:
            result.candidate_profile = CandidateProfileResponse(
                version=profile.version, profile_json=profile.profile_json
            )

    return result


@router.patch("/{user_id}/user")
def update_user_basics(
    user_id: int,
    payload: AdminUserBasicsUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> dict:
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if payload.first_name is not None:
        target_user.first_name = payload.first_name
    if payload.last_name is not None:
        target_user.last_name = payload.last_name
    if payload.phone is not None:
        target_user.phone = payload.phone

    parts = [target_user.first_name, target_user.last_name]
    target_user.full_name = " ".join(p for p in parts if p) or None

    session.commit()
    return {"ok": True}


@router.put("/{user_id}", response_model=CandidateProfileResponse)
def update_user_profile(
    user_id: int,
    payload: CandidateProfileUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> CandidateProfileResponse:
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user_id
    )
    current = session.execute(stmt).scalar()
    next_version = int(current or 0) + 1

    profile = CandidateProfile(
        user_id=user_id,
        resume_document_id=None,
        version=next_version,
        profile_json=payload.profile_json,
    )
    session.add(profile)
    session.commit()

    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


@router.get("/{user_id}/completeness", response_model=ProfileCompletenessResponse)
def get_user_profile_completeness(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> ProfileCompletenessResponse:
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    profile = session.execute(stmt).scalars().first()
    if profile is None:
        profile_json = default_profile_json()
    else:
        profile_json = profile.profile_json

    return compute_profile_completeness(profile_json)
