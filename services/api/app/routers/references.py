"""References CRUD router — manages candidate professional references."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.references import (
    ReferenceCreate,
    ReferenceResponse,
    ReferenceUpdate,
)
from app.services.auth import get_current_user, require_onboarded_user

router = APIRouter(
    prefix="/api/profile/references",
    tags=["references"],
    dependencies=[Depends(require_onboarded_user)],
)


def _get_latest_profile(user_id: int, session: Session) -> CandidateProfile | None:
    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def _create_new_version(
    user_id: int, profile_json: dict, session: Session
) -> CandidateProfile:
    """Create a new profile version with updated JSON (append-only)."""
    stmt = select(func.max(CandidateProfile.version)).where(
        CandidateProfile.user_id == user_id
    )
    current = session.execute(stmt).scalar()
    next_version = int(current or 0) + 1

    profile = CandidateProfile(
        user_id=user_id,
        resume_document_id=None,
        version=next_version,
        profile_json=profile_json,
    )
    session.add(profile)
    session.commit()
    return profile


@router.get("", response_model=list[ReferenceResponse])
def list_references(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ReferenceResponse]:
    """List all references from the current profile."""
    profile = _get_latest_profile(user.id, session)
    if not profile:
        return []

    refs = profile.profile_json.get("references", [])
    return [ReferenceResponse(**r) for r in refs if r.get("is_active", True)]


@router.post("", response_model=ReferenceResponse, status_code=201)
def add_reference(
    body: ReferenceCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReferenceResponse:
    """Add a new reference and create a new profile version."""
    profile = _get_latest_profile(user.id, session)
    if profile:
        profile_json = dict(profile.profile_json)
    else:
        from app.services.profile_parser import default_profile_json

        profile_json = default_profile_json()

    refs = list(profile_json.get("references", []))
    new_ref = {
        "id": f"ref-{uuid.uuid4().hex[:8]}",
        "name": body.name,
        "title": body.title,
        "company": body.company,
        "phone": body.phone,
        "email": body.email,
        "relationship": body.relationship,
        "years_known": body.years_known,
        "notes": body.notes,
        "is_active": True,
    }
    refs.append(new_ref)
    profile_json["references"] = refs

    _create_new_version(user.id, profile_json, session)
    return ReferenceResponse(**new_ref)


@router.put("/{ref_id}", response_model=ReferenceResponse)
def update_reference(
    ref_id: str,
    body: ReferenceUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReferenceResponse:
    """Update an existing reference."""
    profile = _get_latest_profile(user.id, session)
    if not profile:
        raise HTTPException(404, "No profile found")

    profile_json = dict(profile.profile_json)
    refs = list(profile_json.get("references", []))

    target = None
    for r in refs:
        if r.get("id") == ref_id:
            target = r
            break

    if not target:
        raise HTTPException(404, "Reference not found")

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        target[key] = value

    profile_json["references"] = refs
    _create_new_version(user.id, profile_json, session)
    return ReferenceResponse(**target)


@router.delete("/{ref_id}")
def delete_reference(
    ref_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Soft-delete a reference (set is_active=false)."""
    profile = _get_latest_profile(user.id, session)
    if not profile:
        raise HTTPException(404, "No profile found")

    profile_json = dict(profile.profile_json)
    refs = list(profile_json.get("references", []))

    found = False
    for r in refs:
        if r.get("id") == ref_id:
            r["is_active"] = False
            found = True
            break

    if not found:
        raise HTTPException(404, "Reference not found")

    profile_json["references"] = refs
    _create_new_version(user.id, profile_json, session)
    return {"status": "deleted", "ref_id": ref_id}
