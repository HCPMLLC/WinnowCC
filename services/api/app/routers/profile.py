from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.profile import CandidateProfileResponse, CandidateProfileUpdateRequest
from app.services.auth import get_current_user
from app.services.profile_parser import default_profile_json

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=CandidateProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateProfileResponse:
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    profile = session.execute(stmt).scalars().first()
    if profile is None:
        return CandidateProfileResponse(version=0, profile_json=default_profile_json())
    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


@router.put("", response_model=CandidateProfileResponse)
def update_profile(
    payload: CandidateProfileUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateProfileResponse:
    stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user.id
    )
    current = session.execute(stmt).scalar()
    next_version = int(current or 0) + 1

    profile = CandidateProfile(
        user_id=user.id,
        resume_document_id=None,
        version=next_version,
        profile_json=payload.profile_json,
    )
    session.add(profile)
    session.commit()

    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )
