"""Sieve chatbot router — chat, triggers, conversation history."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.sieve_conversation import SieveConversation
from app.models.user import User
from app.schemas.sieve import (
    SieveChatRequest,
    SieveChatResponse,
    SieveTriggersRequest,
    SieveTriggersResponse,
)
from app.models.candidate import Candidate
from app.models.employer import EmployerProfile
from app.models.recruiter import RecruiterProfile
from app.services.auth import get_current_user
from app.services.billing import (
    check_daily_limit,
    get_employer_tier,
    get_plan_tier,
    get_recruiter_tier,
    increment_daily_counter,
)
from app.services.sieve_chat import (
    generate_conversation_id,
    get_employer_suggested_actions,
    get_recruiter_suggested_actions,
    get_suggested_actions,
    handle_chat,
    load_employer_context,
    load_recruiter_context,
    load_user_context,
)
from app.services.sieve_triggers import compute_all_triggers, compute_employer_triggers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sieve", tags=["sieve"])


@router.post("/triggers", response_model=SieveTriggersResponse)
def sieve_triggers(
    body: SieveTriggersRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SieveTriggersResponse:
    """Return proactive nudge triggers for the current user."""
    role = getattr(user, "role", "candidate")
    # Fallback: check for employer/recruiter profile if role is still "candidate"
    is_employer = role == "employer"
    is_recruiter = role == "recruiter"
    if not is_employer and not is_recruiter and role == "candidate":
        is_employer = session.execute(
            select(EmployerProfile.id).where(EmployerProfile.user_id == user.id).limit(1)
        ).scalar_one_or_none() is not None
        if not is_employer:
            is_recruiter = session.execute(
                select(RecruiterProfile.id).where(RecruiterProfile.user_id == user.id).limit(1)
            ).scalar_one_or_none() is not None

    if is_recruiter:
        # Recruiters use the FAB for chat but have no proactive triggers yet
        triggers = []
    elif is_employer:
        triggers = compute_employer_triggers(user, session, dismissed_ids=body.dismissed_ids)
    else:
        triggers = compute_all_triggers(user, session, dismissed_ids=body.dismissed_ids)
    return SieveTriggersResponse(triggers=triggers)


@router.post("/chat", response_model=SieveChatResponse)
def sieve_chat(
    request: Request,
    body: SieveChatRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SieveChatResponse:
    """Chat with Sieve, the career concierge."""
    # Billing: enforce daily message limit (recruiter/employer tier takes priority)
    recruiter_profile = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one_or_none()
    employer_profile = session.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user.id)
    ).scalar_one_or_none()
    if recruiter_profile:
        tier = get_recruiter_tier(recruiter_profile)
    elif employer_profile:
        tier = get_employer_tier(employer_profile)
    else:
        candidate = session.execute(
            select(Candidate).where(Candidate.user_id == user.id)
        ).scalar_one_or_none()
        tier = get_plan_tier(candidate)
    check_daily_limit(session, user.id, tier, "sieve_messages", "sieve_messages_per_day", request=request)

    platform = request.headers.get("X-Client-Platform", "web")

    if not body.message.strip():
        return SieveChatResponse(
            response="I didn't catch that. Could you try again?",
            conversation_id=generate_conversation_id(),
        )

    # Build history dicts from schema objects
    history = [
        {"role": h.role, "content": h.content} for h in body.conversation_history
    ]

    # Get response via handle_chat (includes rate limiting + fallback)
    response_text = handle_chat(
        user_id=user.id,
        message=body.message,
        conversation_history=history,
        session=session,
        platform=platform,
    )

    # Billing: increment daily counter
    increment_daily_counter(session, user.id, "sieve_messages")

    # Persist user message
    session.add(
        SieveConversation(
            user_id=user.id,
            role="user",
            content=body.message,
        )
    )
    # Persist assistant response
    session.add(
        SieveConversation(
            user_id=user.id,
            role="assistant",
            content=response_text,
        )
    )
    session.commit()

    # Get suggested actions (recruiter vs employer vs candidate)
    try:
        if recruiter_profile:
            rec_ctx = load_recruiter_context(user.id, session)
            suggestions = get_recruiter_suggested_actions(rec_ctx)
        elif employer_profile:
            emp_ctx = load_employer_context(user.id, session)
            suggestions = get_employer_suggested_actions(emp_ctx)
        else:
            user_context = load_user_context(user.id, session)
            suggestions = get_suggested_actions(user_context)
    except Exception:
        logger.exception("Failed to load suggested actions")
        suggestions = []

    return SieveChatResponse(
        response=response_text,
        conversation_id=generate_conversation_id(),
        suggested_actions=suggestions,
    )


@router.get("/history")
def sieve_history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Return last 50 conversation messages for the current user."""
    rows = (
        session.query(SieveConversation)
        .filter(SieveConversation.user_id == user.id)
        .order_by(SieveConversation.created_at.asc())
        .limit(50)
        .all()
    )
    return [
        {
            "role": r.role,
            "content": r.content,
            "trigger_id": r.trigger_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.delete("/history")
def sieve_clear_history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Delete all conversation history for the current user."""
    deleted = (
        session.query(SieveConversation)
        .filter(SieveConversation.user_id == user.id)
        .delete()
    )
    session.commit()
    return {"deleted": deleted}
