import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate_trust import CandidateTrust
from app.models.trust_audit_log import TrustAuditLog
from app.schemas.trust import (
    AdminTrustRecordResponse,
    AdminTrustUpdateRequest,
    AdminTrustUpdateResponse,
)

router = APIRouter(prefix="/api/admin/trust", tags=["admin-trust"])


def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected or (x_admin_token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Admin token invalid.")


@router.get("/queue", response_model=list[AdminTrustRecordResponse])
def get_trust_queue(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
) -> list[AdminTrustRecordResponse]:
    stmt = (
        select(CandidateTrust)
        .where(CandidateTrust.status != "allowed")
        .order_by(CandidateTrust.updated_at.desc())
    )
    records = session.execute(stmt).scalars().all()
    return [
        AdminTrustRecordResponse(
            id=record.id,
            resume_document_id=record.resume_document_id,
            score=record.score,
            status=record.status,
            reasons=record.reasons,
            user_message=record.user_message,
            internal_notes=record.internal_notes,
            updated_at=record.updated_at,
        )
        for record in records
    ]


@router.post("/{trust_id}/set", response_model=AdminTrustUpdateResponse)
def set_trust_status(
    trust_id: int,
    payload: AdminTrustUpdateRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
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
            details={"internal_notes": payload.internal_notes},
        )
    )
    session.commit()
    session.refresh(trust)

    return AdminTrustUpdateResponse(
        id=trust.id, status=trust.status, internal_notes=trust.internal_notes
    )
