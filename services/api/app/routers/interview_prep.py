"""Interview prep router — retrieve and retry interview preparation content."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.interview_prep import InterviewPrep
from app.models.match import Match
from app.models.user import User
from app.services.auth import get_current_user, require_onboarded_user
from app.services.billing import get_plan_tier
from app.services.queue import get_queue
from app.services.trust_gate import require_allowed_trust

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["interview-prep"])


class InterviewPrepResponse(BaseModel):
    id: int
    match_id: int
    status: str
    prep_content: dict | None = None
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


@router.get(
    "/{match_id}/interview-prep",
    response_model=InterviewPrepResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def get_interview_prep(
    match_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> InterviewPrepResponse:
    """Get interview prep results for a match."""
    # Verify match ownership
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    prep = session.execute(
        select(InterviewPrep).where(InterviewPrep.match_id == match_id)
    ).scalar_one_or_none()
    if prep is None:
        raise HTTPException(status_code=404, detail="No interview prep for this match.")

    # Determine tier for content gating
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)

    content = prep.prep_content
    if content and tier != "pro":
        # Starter users don't get gap_strategies
        content = {k: v for k, v in content.items() if k != "gap_strategies"}

    return InterviewPrepResponse(
        id=prep.id,
        match_id=prep.match_id,
        status=prep.status,
        prep_content=content,
        error_message=prep.error_message,
        created_at=prep.created_at.isoformat() if prep.created_at else None,
        completed_at=prep.completed_at.isoformat() if prep.completed_at else None,
    )


@router.post(
    "/{match_id}/interview-prep/retry",
    response_model=InterviewPrepResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def retry_interview_prep(
    match_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> InterviewPrepResponse:
    """Retry a failed interview prep generation."""
    # Verify match ownership
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    prep = session.execute(
        select(InterviewPrep).where(InterviewPrep.match_id == match_id)
    ).scalar_one_or_none()
    if prep is None:
        raise HTTPException(status_code=404, detail="No interview prep for this match.")

    if prep.status != "failed":
        raise HTTPException(
            status_code=400, detail="Only failed preps can be retried."
        )

    # Reset and re-enqueue
    prep.status = "pending"
    prep.error_message = None
    prep.prep_content = None
    prep.completed_at = None
    session.flush()

    from app.services.interview_prep import generate_interview_prep_job

    queue = get_queue("default")
    queue.enqueue(generate_interview_prep_job, prep.id)

    session.commit()

    return InterviewPrepResponse(
        id=prep.id,
        match_id=prep.match_id,
        status=prep.status,
        created_at=prep.created_at.isoformat() if prep.created_at else None,
    )
