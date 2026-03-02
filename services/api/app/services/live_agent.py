"""Live agent escalation service.

Handles detecting when escalation is needed, creating tickets,
and sending notifications to the admin.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Optional

import pytz
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.support_ticket import (
    SupportMessage,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# Business hours configuration
BUSINESS_TIMEZONE = pytz.timezone("America/Chicago")  # CST
BUSINESS_HOURS_START = 8  # 08:00
BUSINESS_HOURS_END = 18  # 18:00
BUSINESS_DAYS = [0, 1, 2, 3, 4, 5]  # Monday=0 through Saturday=5

# Escalation trigger phrases
ESCALATION_PHRASES = [
    "talk to a person",
    "talk to someone",
    "speak to a human",
    "speak to someone",
    "real person",
    "human help",
    "live agent",
    "representative",
    "customer service",
    "customer support",
    "support team",
    "talk to support",
    "need help from a person",
    "actual person",
    "not a bot",
    "speak to a rep",
    "get a human",
    "transfer me",
    "escalate",
]

# AI uncertainty indicators (if Sieve responds with these 3+ times)
AI_UNCERTAINTY_PHRASES = [
    "i'm not sure",
    "i don't have information",
    "i cannot access",
    "i'm unable to",
    "you might want to contact",
    "i don't know",
    "i can't help with that",
    "outside my capabilities",
    "i apologize, but i cannot",
]

# Frustration indicators
FRUSTRATION_PHRASES = [
    "this isn't working",
    "you're not helping",
    "useless",
    "frustrated",
    "doesn't make sense",
    "i give up",
    "forget it",
    "never mind",
    "this is stupid",
    "waste of time",
]


def is_within_business_hours() -> bool:
    """Check if current time is within business hours (08:00-18:00 CST Mon-Sat)."""
    now = datetime.now(BUSINESS_TIMEZONE)
    if now.weekday() not in BUSINESS_DAYS:
        return False
    if now.hour < BUSINESS_HOURS_START or now.hour >= BUSINESS_HOURS_END:
        return False
    return True


def get_next_business_hours() -> str:
    """Get a human-readable string for when business hours resume."""
    now = datetime.now(BUSINESS_TIMEZONE)

    # If it's a business day but before hours
    if now.weekday() in BUSINESS_DAYS and now.hour < BUSINESS_HOURS_START:
        return f"today at {BUSINESS_HOURS_START}:00 AM CST"

    # Sunday
    if now.weekday() == 6:
        return "Monday at 8:00 AM CST"
    # Saturday after hours
    if now.weekday() == 5:
        return "Monday at 8:00 AM CST"

    return "tomorrow at 8:00 AM CST"


def detect_escalation_trigger(
    message: str,
    conversation_history: list[dict],
) -> Optional[tuple[str, str]]:
    """Detect if the user's message or conversation state warrants escalation.

    Returns:
        tuple of (reason, trigger_message) if escalation detected, None otherwise
        reason: "user_request" | "ai_uncertainty" | "frustration"
    """
    message_lower = message.lower()

    # Check for explicit user request
    for phrase in ESCALATION_PHRASES:
        if phrase in message_lower:
            return ("user_request", message)

    # Check for frustration
    for phrase in FRUSTRATION_PHRASES:
        if phrase in message_lower:
            return ("frustration", message)

    # Check for repeated AI uncertainty (3+ times in last 6 messages)
    recent_assistant_messages = [
        m.get("content", "").lower()
        for m in conversation_history[-6:]
        if m.get("role") == "assistant"
    ]

    uncertainty_count = 0
    for msg in recent_assistant_messages:
        for phrase in AI_UNCERTAINTY_PHRASES:
            if phrase in msg:
                uncertainty_count += 1
                break

    if uncertainty_count >= 3:
        return ("ai_uncertainty", "Sieve was uncertain in 3+ consecutive responses")

    return None


def get_user_snapshot(user: User, session: Session) -> dict:
    """Build a snapshot of user info for the ticket."""
    snapshot = {
        "user_id": user.id,
        "email": user.email,
    }

    try:
        profile = (
            session.query(CandidateProfile)
            .filter(CandidateProfile.user_id == user.id)
            .order_by(CandidateProfile.version.desc())
            .first()
        )

        if profile and profile.profile_json:
            pj = (
                profile.profile_json
                if isinstance(profile.profile_json, dict)
                else json.loads(profile.profile_json)
            )
            snapshot["name"] = pj.get("basics", {}).get("name", "Unknown")
            snapshot["title"] = pj.get("basics", {}).get("title", "")
            snapshot["location"] = pj.get("basics", {}).get("location", "")
        else:
            snapshot["name"] = user.full_name or user.email.split("@")[0]
    except Exception as e:
        logger.warning("Failed to get user snapshot: %s", e)
        snapshot["name"] = user.full_name or user.email.split("@")[0]

    return snapshot


def create_support_ticket(
    user: User,
    session: Session,
    escalation_reason: str,
    escalation_trigger: str,
    conversation_history: list[dict],
    priority: str = TicketPriority.NORMAL.value,
) -> SupportTicket:
    """Create a new support ticket for live agent escalation."""
    user_snapshot = get_user_snapshot(user, session)

    # Keep last 10 messages as pre-escalation context
    pre_context = conversation_history[-10:] if conversation_history else []

    # Determine priority based on reason
    if escalation_reason == "frustration":
        priority = TicketPriority.HIGH.value
    elif escalation_reason == "user_request":
        priority = TicketPriority.NORMAL.value

    ticket = SupportTicket(
        user_id=user.id,
        status=TicketStatus.WAITING.value,
        priority=priority,
        escalation_reason=escalation_reason,
        escalation_trigger=escalation_trigger,
        pre_escalation_context=pre_context,
        user_snapshot=user_snapshot,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    # Add initial system message
    system_msg = SupportMessage(
        ticket_id=ticket.id,
        sender_type="system",
        sender_name="Sieve",
        content=f"Ticket created. Reason: {escalation_reason}. User is waiting for a live agent.",
    )
    session.add(system_msg)
    session.commit()

    logger.info(
        "Created support ticket %d for user %d, reason: %s",
        ticket.id,
        user.id,
        escalation_reason,
    )

    return ticket


def add_message_to_ticket(
    ticket_id: int,
    sender_type: str,
    content: str,
    session: Session,
    sender_id: Optional[int] = None,
    sender_name: Optional[str] = None,
) -> SupportMessage:
    """Add a message to an existing support ticket."""
    message = SupportMessage(
        ticket_id=ticket_id,
        sender_type=sender_type,
        sender_id=sender_id,
        sender_name=sender_name,
        content=content,
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    return message


def get_ticket_with_messages(ticket_id: int, session: Session) -> Optional[dict]:
    """Get a ticket with all its messages."""
    ticket = (
        session.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        return None

    messages = (
        session.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at.asc())
        .all()
    )

    return {
        "ticket": {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "status": ticket.status,
            "priority": ticket.priority,
            "escalation_reason": ticket.escalation_reason,
            "escalation_trigger": ticket.escalation_trigger,
            "user_snapshot": ticket.user_snapshot,
            "pre_escalation_context": ticket.pre_escalation_context,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "agent_joined_at": ticket.agent_joined_at.isoformat() if ticket.agent_joined_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "resolution_summary": ticket.resolution_summary,
            "resolution_category": ticket.resolution_category,
        },
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "sender_name": m.sender_name,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


def close_ticket(
    ticket_id: int,
    session: Session,
    resolution_summary: str,
    resolution_category: str,
    add_to_kb: bool = False,
) -> Optional[SupportTicket]:
    """Close a support ticket with resolution details."""
    ticket = (
        session.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        return None

    ticket.status = TicketStatus.RESOLVED.value
    ticket.resolved_at = datetime.now(UTC)
    ticket.resolution_summary = resolution_summary
    ticket.resolution_category = resolution_category
    ticket.add_to_knowledge_base = add_to_kb

    # Add system message
    close_msg = SupportMessage(
        ticket_id=ticket.id,
        sender_type="system",
        sender_name="System",
        content=f"Ticket resolved. Category: {resolution_category}",
    )
    session.add(close_msg)

    session.commit()
    session.refresh(ticket)

    logger.info(
        "Closed support ticket %d with category: %s", ticket.id, resolution_category
    )

    return ticket
