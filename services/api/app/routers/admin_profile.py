import re
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
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

        results.append(
            UserSummary(
                id=user.id,
                email=user.email,
                name=name,
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    users = session.execute(select(User).order_by(User.id)).scalars().all()

    # Pre-fetch user IDs that have at least one candidate profile
    users_with_profile = set(
        session.execute(
            select(CandidateProfile.user_id).distinct()
        ).scalars().all()
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
            and user.created_at.replace(tzinfo=timezone.utc) < cutoff
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


# --- Dynamic /{user_id} routes (must come after static-prefix routes) ---


@router.get("/{user_id}", response_model=CandidateProfileResponse)
def get_user_profile(
    user_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> CandidateProfileResponse:
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
        return CandidateProfileResponse(version=0, profile_json=default_profile_json())
    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


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
