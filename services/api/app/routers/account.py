"""Account management endpoints: data export and account deletion."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.middleware.rate_limit import limiter
from app.models.candidate_profile import CandidateProfile
from app.models.candidate_trust import CandidateTrust
from app.models.match import Match
from app.models.resume_document import ResumeDocument
from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.schemas.account import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    ExportPreviewResponse,
)
from app.models.candidate import Candidate
from app.services.auth import clear_auth_cookie, get_current_user
from app.services.billing import check_feature_access, get_plan_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/export/preview", response_model=ExportPreviewResponse)
def export_preview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ExportPreviewResponse:
    """Preview what data will be included in the export."""
    resume_docs = (
        db.query(ResumeDocument)
        .filter(ResumeDocument.user_id == user.id, ResumeDocument.deleted_at.is_(None))
        .all()
    )
    has_trust = False
    for doc in resume_docs:
        if (
            db.query(CandidateTrust)
            .filter(CandidateTrust.resume_document_id == doc.id)
            .first()
        ):
            has_trust = True
            break

    return ExportPreviewResponse(
        profile_versions=db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .count(),
        resume_documents=len(resume_docs),
        matches=db.query(Match).filter(Match.user_id == user.id).count(),
        tailored_resumes=db.query(TailoredResume)
        .filter(TailoredResume.user_id == user.id)
        .count(),
        has_trust_record=has_trust,
    )


@router.get("/export")
@limiter.limit("3/minute")
def export_data(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    """Export all user data as a ZIP file download."""
    # Billing: data export requires Starter or Pro
    from sqlalchemy import select

    candidate = db.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    if not check_feature_access(tier, "data_export"):
        raise HTTPException(
            status_code=403,
            detail="Data export requires a Starter or Pro plan.",
        )

    from app.services.data_export import export_user_data

    zip_buffer = export_user_data(user.id, db)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": (f"attachment; filename=winnow-export-{user.id}.zip")
        },
    )


@router.post("/delete", response_model=DeleteAccountResponse)
@limiter.limit("2/minute")
def delete_account(
    request: Request,
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> JSONResponse:
    """Permanently delete user account and all associated data.

    Requires ``{ "confirm": "DELETE MY ACCOUNT" }`` in the body.
    This action is **irreversible**.
    """
    from app.services.account_deletion import delete_user_account

    if body.confirm != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=400,
            detail=('To delete your account, send: {"confirm": "DELETE MY ACCOUNT"}'),
        )

    summary = delete_user_account(user.id, db)

    response = JSONResponse(
        content={
            "status": "deleted",
            "message": (
                "Your account and all associated data have been permanently deleted."
            ),
            "summary": summary,
        }
    )
    clear_auth_cookie(response)
    return response
