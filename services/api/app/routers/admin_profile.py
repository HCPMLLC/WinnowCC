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
from app.services.profile_parser import default_profile_json
from app.services.profile_scoring import compute_profile_completeness

router = APIRouter(prefix="/api/admin/profile", tags=["admin-profile"])


class UserSummary(BaseModel):
    id: int
    email: str
    name: str | None
    completeness_score: int
    onboarding_completed: bool


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
