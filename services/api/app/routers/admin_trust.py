from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_profile import CandidateProfile
from app.models.candidate_trust import CandidateTrust
from app.models.resume_document import ResumeDocument
from app.models.trust_audit_log import TrustAuditLog
from app.models.user import User
from app.schemas.trust import (
    AdminTrustRecordResponse,
    AdminTrustUpdateRequest,
    AdminTrustUpdateResponse,
)
from app.services.auth import require_admin_user

router = APIRouter(prefix="/api/admin/trust", tags=["admin-trust"])


def _candidate_name_for_user(session: Session, user_id: int) -> str | None:
    """Return the candidate's display name from their latest profile."""
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if profile and profile.profile_json:
        basics = profile.profile_json.get("basics", {})
        name = basics.get("name") or profile.profile_json.get("name")
        if name:
            return name
        first = basics.get("first_name", "")
        last = basics.get("last_name", "")
        full = f"{first} {last}".strip()
        if full:
            return full
    return None


@router.get("/queue", response_model=list[AdminTrustRecordResponse])
def get_trust_queue(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> list[AdminTrustRecordResponse]:
    stmt = (
        select(CandidateTrust, ResumeDocument, User)
        .join(ResumeDocument, CandidateTrust.resume_document_id == ResumeDocument.id)
        .join(User, ResumeDocument.user_id == User.id)
        .where(CandidateTrust.status != "allowed")
        .order_by(CandidateTrust.updated_at.desc())
    )
    rows = session.execute(stmt).all()
    results = []
    for record, _doc, user in rows:
        results.append(
            AdminTrustRecordResponse(
                id=record.id,
                resume_document_id=record.resume_document_id,
                candidate_name=_candidate_name_for_user(session, user.id),
                candidate_email=user.email,
                score=record.score,
                status=record.status,
                reasons=record.reasons,
                user_message=record.user_message,
                internal_notes=record.internal_notes,
                updated_at=record.updated_at,
            )
        )
    return results


@router.post("/{trust_id}/set", response_model=AdminTrustUpdateResponse)
def set_trust_status(
    trust_id: int,
    payload: AdminTrustUpdateRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
) -> AdminTrustUpdateResponse:
    trust = session.get(CandidateTrust, trust_id)
    if trust is None:
        raise HTTPException(status_code=404, detail="Trust record not found.")
    if payload.status not in {"allowed", "soft_quarantine", "hard_quarantine"}:
        raise HTTPException(status_code=400, detail="Invalid trust status.")

    prev_status = trust.status
    trust.status = payload.status
    trust.internal_notes = payload.internal_notes
    # Keep score as-is (score explains why the system flagged it),
    # but ensure the user-facing message matches the override status.
    if trust.status == "allowed":
        trust.user_message = "Profile ready for matching."
        # Optional: clear reasons so the candidate UI doesn't show stale flags.
        # If you want admins to still see them, keep reasons but hide from candidate UI.
        # trust.reasons = {}
    elif trust.status == "soft_quarantine":
        trust.user_message = "Verification required before matching."
    elif trust.status == "hard_quarantine":
        trust.user_message = "Account is quarantined pending verification."

    session.add(
        TrustAuditLog(
            trust_id=trust.id,
            actor_type="admin",
            action="admin_set_status",
            prev_status=prev_status,
            new_status=trust.status,
            details={"internal_notes": payload.internal_notes, "admin_user_id": admin.id},
        )
    )
    session.commit()
    session.refresh(trust)

    return AdminTrustUpdateResponse(
        id=trust.id, status=trust.status, internal_notes=trust.internal_notes
    )
