from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.profile import (
    CandidateProfileResponse,
    CandidateProfileUpdateRequest,
    ProfileCompletenessResponse,
    SkillCategoriesPayload,
)
from app.schemas.introduction import (
    IntroductionPreferencesUpdate,
    IntroductionResponseAction,
)
from app.services.auth import get_current_user, require_onboarded_user
from app.services.profile_parser import default_profile_json
from app.services.profile_scoring import compute_profile_completeness

router = APIRouter(
    prefix="/api/profile",
    tags=["profile"],
    dependencies=[Depends(require_onboarded_user)],
)


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
    # Get current profile to preserve skill_categories if not in payload
    current_stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    current_profile = session.execute(current_stmt).scalars().first()

    profile_json = payload.profile_json

    # Preserve skill_categories from current profile if the incoming payload
    # doesn't include them (prevents main "Save Profile" from overwriting
    # categories saved via the dedicated skill-categories endpoint)
    if current_profile:
        existing_prefs = (current_profile.profile_json or {}).get("preferences") or {}
        existing_cats = existing_prefs.get("skill_categories")
        if existing_cats:
            incoming_prefs = profile_json.get("preferences") or {}
            incoming_cats = incoming_prefs.get("skill_categories")
            if not incoming_cats:
                if not profile_json.get("preferences"):
                    profile_json["preferences"] = {}
                profile_json["preferences"]["skill_categories"] = existing_cats

    stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user.id
    )
    current = session.execute(stmt).scalar()
    next_version = int(current or 0) + 1

    profile = CandidateProfile(
        user_id=user.id,
        resume_document_id=None,
        version=next_version,
        profile_json=profile_json,
    )
    session.add(profile)
    session.commit()

    # Enqueue embedding generation (non-blocking, best-effort)
    try:
        from app.services.job_pipeline import embed_profile
        from app.services.queue import get_queue

        get_queue().enqueue(embed_profile, user.id, next_version)
    except Exception:
        pass

    # Refresh employer-side candidate cache
    try:
        from app.services.job_pipeline import refresh_candidates_for_profile
        from app.services.queue import get_queue

        get_queue().enqueue(refresh_candidates_for_profile, user.id)
    except Exception:
        pass

    # Recompute trust score with updated profile data
    try:
        from app.services.trust_scoring import evaluate_trust_for_resume, get_latest_resume

        resume = get_latest_resume(session, user.id)
        if resume is not None:
            evaluate_trust_for_resume(session, resume, profile_json, "profile_update")
    except Exception:
        pass

    # Re-run matching with updated profile
    try:
        from app.services.job_pipeline import match_jobs_job
        from app.services.queue import get_queue

        get_queue().enqueue(match_jobs_job, user.id, next_version)
    except Exception:
        pass

    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


@router.get("/completeness", response_model=ProfileCompletenessResponse)
def get_profile_completeness(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProfileCompletenessResponse:
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    profile = session.execute(stmt).scalars().first()
    if profile is None:
        profile_json = default_profile_json()
    else:
        profile_json = profile.profile_json

    return compute_profile_completeness(profile_json)


@router.put("/skill-categories", response_model=CandidateProfileResponse)
def update_skill_categories(
    payload: SkillCategoriesPayload,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateProfileResponse:
    """
    Update user's skill category assignments.

    Saves the user's custom skill categorization to preferences.skill_categories.
    This creates a new profile version with the updated categories.
    """
    # Get current profile
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    current_profile = session.execute(stmt).scalars().first()

    if current_profile is None:
        profile_json = default_profile_json()
    else:
        profile_json = dict(current_profile.profile_json)

    # Ensure preferences exists
    if "preferences" not in profile_json:
        profile_json["preferences"] = {}

    # Update skill_categories in preferences
    profile_json["preferences"]["skill_categories"] = {
        "core_technical": payload.core_technical,
        "environmental_adjacent": payload.environmental_adjacent,
        "leadership_soft": payload.leadership_soft,
    }

    # Create new profile version
    stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user.id
    )
    current_version = session.execute(stmt).scalar()
    next_version = int(current_version or 0) + 1

    profile = CandidateProfile(
        user_id=user.id,
        resume_document_id=None,
        version=next_version,
        profile_json=profile_json,
    )
    session.add(profile)
    session.commit()

    # Enqueue embedding generation (non-blocking, best-effort)
    try:
        from app.services.job_pipeline import embed_profile
        from app.services.queue import get_queue

        get_queue().enqueue(embed_profile, user.id, next_version)
    except Exception:
        pass

    # Refresh employer-side candidate cache
    try:
        from app.services.job_pipeline import refresh_candidates_for_profile
        from app.services.queue import get_queue

        get_queue().enqueue(refresh_candidates_for_profile, user.id)
    except Exception:
        pass

    # Re-run matching with updated profile
    try:
        from app.services.job_pipeline import match_jobs_job
        from app.services.queue import get_queue

        get_queue().enqueue(match_jobs_job, user.id, next_version)
    except Exception:
        pass

    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


# ---------------------------------------------------------------------------
# Skill years manual override
# ---------------------------------------------------------------------------


class SkillYearsPayload(BaseModel):
    years_experience: int


@router.patch("/skills/{skill_name}/years", response_model=CandidateProfileResponse)
def update_skill_years(
    skill_name: str,
    payload: SkillYearsPayload,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CandidateProfileResponse:
    """Manually set years_experience for a skill (overrides parsed value)."""
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    current_profile = session.execute(stmt).scalars().first()
    if current_profile is None:
        raise HTTPException(404, "No profile found")

    profile_json = dict(current_profile.profile_json)
    skill_years = dict(profile_json.get("skill_years", {}))

    skill_years[skill_name] = {
        "years_experience": payload.years_experience,
        "years_experience_source": "manual",
    }
    profile_json["skill_years"] = skill_years

    ver_stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user.id
    )
    current_version = session.execute(ver_stmt).scalar()
    next_version = int(current_version or 0) + 1

    profile = CandidateProfile(
        user_id=user.id,
        resume_document_id=None,
        version=next_version,
        profile_json=profile_json,
    )
    session.add(profile)
    session.commit()

    # Refresh employer-side candidate cache
    try:
        from app.services.job_pipeline import refresh_candidates_for_profile
        from app.services.queue import get_queue

        get_queue().enqueue(refresh_candidates_for_profile, user.id)
    except Exception:
        pass

    # Re-run matching with updated profile
    try:
        from app.services.job_pipeline import match_jobs_job
        from app.services.queue import get_queue

        get_queue().enqueue(match_jobs_job, user.id, next_version)
    except Exception:
        pass

    return CandidateProfileResponse(
        version=profile.version, profile_json=profile.profile_json
    )


# ---------------------------------------------------------------------------
# Introduction Requests (candidate-side)
# ---------------------------------------------------------------------------


def _get_user_profile_ids(session: Session, user_id: int) -> list[int]:
    """Get all candidate profile IDs for a user (all versions)."""
    rows = session.execute(
        select(CandidateProfile.id).where(CandidateProfile.user_id == user_id)
    ).scalars().all()
    return list(rows)


@router.get("/introductions")
def list_candidate_introductions(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List introduction requests received by this candidate (recruiter + employer)."""
    from app.services.introductions import get_candidate_introductions
    from app.services.employer_introductions import get_candidate_employer_introductions

    cp_ids = _get_user_profile_ids(session, user.id)
    if not cp_ids:
        return []

    # Recruiter intros (add sender_type)
    recruiter_intros = get_candidate_introductions(
        session=session,
        candidate_profile_ids=cp_ids,
        status_filter=status,
        limit=limit,
    )
    for intro in recruiter_intros:
        intro["sender_type"] = "recruiter"

    # Employer intros (already have sender_type from service)
    employer_intros = get_candidate_employer_introductions(
        session=session,
        candidate_profile_ids=cp_ids,
        status_filter=status,
        limit=limit,
    )

    # Merge and sort by created_at descending
    merged = recruiter_intros + employer_intros
    merged.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return merged[:limit]


@router.get("/introductions/count")
def get_candidate_introduction_count(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get count of pending introduction requests (recruiter + employer)."""
    from app.services.introductions import get_candidate_pending_count
    from app.services.employer_introductions import get_candidate_employer_pending_count

    cp_ids = _get_user_profile_ids(session, user.id)
    if not cp_ids:
        return {"pending_count": 0}
    recruiter_count = get_candidate_pending_count(session, cp_ids)
    employer_count = get_candidate_employer_pending_count(session, cp_ids)
    return {"pending_count": recruiter_count + employer_count}


@router.post("/introductions/{intro_id}/respond")
def respond_to_introduction_request(
    intro_id: int,
    payload: IntroductionResponseAction,
    sender_type: str = Query("recruiter"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Accept or decline an introduction request (recruiter or employer)."""
    cp_ids = _get_user_profile_ids(session, user.id)
    if not cp_ids:
        raise HTTPException(status_code=404, detail="No profile found.")

    if sender_type == "employer":
        from app.services.employer_introductions import respond_to_employer_introduction

        intro = respond_to_employer_introduction(
            session=session,
            candidate_profile_ids=cp_ids,
            request_id=intro_id,
            action=payload.action,
            response_message=payload.response_message,
        )
    else:
        from app.services.introductions import respond_to_introduction

        intro = respond_to_introduction(
            session=session,
            candidate_profile_ids=cp_ids,
            request_id=intro_id,
            action=payload.action,
            response_message=payload.response_message,
        )
    session.commit()
    return {
        "id": intro.id,
        "status": intro.status,
        "responded_at": intro.responded_at.isoformat() if intro.responded_at else None,
    }


@router.patch("/introduction-preferences")
def update_introduction_preferences(
    payload: IntroductionPreferencesUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Toggle open_to_introductions preference on all profile versions."""
    cp_ids = _get_user_profile_ids(session, user.id)
    if not cp_ids:
        raise HTTPException(status_code=404, detail="No profile found.")
    # Update the latest profile
    cp = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="No profile found.")
    cp.open_to_introductions = payload.open_to_introductions
    session.commit()
    return {"open_to_introductions": cp.open_to_introductions}
