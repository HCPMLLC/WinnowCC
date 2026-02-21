"""Recruiter action queue router — prioritized daily to-do list for recruiters."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.recruiter import RecruiterProfile
from app.services.auth import get_recruiter_profile

router = APIRouter(
    prefix="/api/recruiter/actions",
    tags=["recruiter-actions"],
)
logger = logging.getLogger(__name__)


@router.get("")
def get_action_queue(
    profile: RecruiterProfile = Depends(get_recruiter_profile),
    db: Session = Depends(get_session),
):
    """Get prioritized daily action queue for the recruiter."""
    from app.services.recruiter_actions import generate_recruiter_actions

    return generate_recruiter_actions(profile.id, db)


@router.post("/{action_id}/dismiss")
def dismiss_action(
    action_id: str,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
):
    """Dismiss an action item (session-based acknowledgment)."""
    return {"status": "dismissed", "action_id": action_id}


@router.post("/{action_id}/snooze")
def snooze_action(
    action_id: str,
    hours: int = 4,
    profile: RecruiterProfile = Depends(get_recruiter_profile),
):
    """Snooze an action for N hours (session-based)."""
    return {
        "status": "snoozed",
        "action_id": action_id,
        "snooze_hours": hours,
    }
