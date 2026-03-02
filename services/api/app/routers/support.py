"""Support ticket API endpoints.

Handles live agent escalation from Sieve and admin ticket management.
"""

import logging
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.support_ticket import (
    SupportMessage,
    SupportTicket,
    TicketStatus,
)
from app.models.user import User
from app.services.auth import get_current_user, require_admin_user
from app.services.live_agent import (
    add_message_to_ticket,
    close_ticket,
    create_support_ticket,
    detect_escalation_trigger,
    get_ticket_with_messages,
    is_within_business_hours,
)
from app.services.support_notifications import notify_new_ticket, notify_ticket_resolved

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/support", tags=["support"])


# ============================================================================
# USER ENDPOINTS (for the Sieve widget)
# ============================================================================


class EscalateRequest(BaseModel):
    message: str
    conversation_history: Optional[list[dict]] = []


class EscalateResponse(BaseModel):
    ticket_id: int
    status: str
    message: str
    within_business_hours: bool
    expected_response: Optional[str] = None


@router.post("/escalate", response_model=EscalateResponse)
async def escalate_to_agent(
    payload: EscalateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Escalate the current Sieve conversation to a live agent."""
    # Check for existing open ticket
    existing = (
        session.query(SupportTicket)
        .filter(
            SupportTicket.user_id == user.id,
            SupportTicket.status.in_(
                [TicketStatus.WAITING.value, TicketStatus.ACTIVE.value]
            ),
        )
        .first()
    )

    if existing:
        return EscalateResponse(
            ticket_id=existing.id,
            status=existing.status,
            message="You already have an open support ticket. An agent will be with you shortly.",
            within_business_hours=is_within_business_hours(),
        )

    # Detect escalation reason
    trigger_result = detect_escalation_trigger(
        payload.message, payload.conversation_history
    )

    if trigger_result:
        reason, trigger = trigger_result
    else:
        reason = "user_request"
        trigger = payload.message

    # Create the ticket
    ticket = create_support_ticket(
        user=user,
        session=session,
        escalation_reason=reason,
        escalation_trigger=trigger,
        conversation_history=payload.conversation_history,
    )

    # Send notifications to admin
    notify_new_ticket(ticket)

    # Prepare response
    within_hours = is_within_business_hours()

    if within_hours:
        response_message = "I'm connecting you with a live agent. Someone will be with you shortly."
        expected = "within a few minutes"
    else:
        response_message = "I've created a support ticket for you. Our team will respond during normal business hours, 8:00 am to 6:00 pm CST M-F."
        expected = "during business hours (8:00 AM – 6:00 PM CST, M-F)"

    return EscalateResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        message=response_message,
        within_business_hours=within_hours,
        expected_response=expected,
    )


class UserTicketStatusResponse(BaseModel):
    ticket_id: int
    status: str
    agent_joined: bool
    messages: list[dict]


@router.get("/ticket/active")
async def get_active_ticket(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get the user's currently active support ticket, if any."""
    ticket = (
        session.query(SupportTicket)
        .filter(
            SupportTicket.user_id == user.id,
            SupportTicket.status.in_(
                [TicketStatus.WAITING.value, TicketStatus.ACTIVE.value]
            ),
        )
        .first()
    )

    if not ticket:
        return None

    messages = (
        session.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.created_at.asc())
        .all()
    )

    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "agent_joined": ticket.agent_joined_at is not None,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


class SendMessageRequest(BaseModel):
    content: str


@router.post("/ticket/{ticket_id}/message")
async def user_send_message(
    ticket_id: int,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Send a message to the support ticket (user side)."""
    ticket = (
        session.query(SupportTicket)
        .filter(
            SupportTicket.id == ticket_id,
            SupportTicket.user_id == user.id,
            SupportTicket.status.in_(
                [TicketStatus.WAITING.value, TicketStatus.ACTIVE.value]
            ),
        )
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or not accessible")

    user_name = (ticket.user_snapshot or {}).get("name", "User")

    message = add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=user.id,
        sender_name=user_name,
        content=payload.content,
        session=session,
    )

    return {
        "id": message.id,
        "sender_type": message.sender_type,
        "sender_name": message.sender_name,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


# ============================================================================
# ADMIN ENDPOINTS (for the admin dashboard)
# ============================================================================


class TicketListItem(BaseModel):
    id: int
    user_name: str
    user_email: str
    status: str
    priority: str
    escalation_reason: str
    created_at: str
    waiting_minutes: int
    last_message: Optional[str] = None


class TicketListResponse(BaseModel):
    tickets: List[TicketListItem]
    total: int


@router.get("/admin/tickets", response_model=TicketListResponse)
async def admin_list_tickets(
    status: Optional[str] = None,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
):
    """List all support tickets (admin only)."""
    query = session.query(SupportTicket)

    if status:
        query = query.filter(SupportTicket.status == status)

    tickets = query.order_by(desc(SupportTicket.created_at)).limit(100).all()

    result = []
    for t in tickets:
        user_info = t.user_snapshot or {}

        # Calculate waiting time
        now = datetime.now(UTC)
        waiting_mins = (
            int((now - t.created_at).total_seconds() / 60) if t.created_at else 0
        )

        # Get last message
        last_msg = (
            session.query(SupportMessage)
            .filter(SupportMessage.ticket_id == t.id)
            .order_by(desc(SupportMessage.created_at))
            .first()
        )

        result.append(
            TicketListItem(
                id=t.id,
                user_name=user_info.get("name", "Unknown"),
                user_email=user_info.get("email", "unknown"),
                status=t.status,
                priority=t.priority,
                escalation_reason=t.escalation_reason,
                created_at=t.created_at.isoformat() if t.created_at else "",
                waiting_minutes=waiting_mins,
                last_message=last_msg.content[:100] if last_msg else None,
            )
        )

    return TicketListResponse(tickets=result, total=len(result))


@router.get("/admin/tickets/{ticket_id}")
async def admin_get_ticket(
    ticket_id: int,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
):
    """Get full details of a support ticket including all messages (admin only)."""
    result = get_ticket_with_messages(ticket_id, session)

    if not result:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return result


@router.post("/admin/tickets/{ticket_id}/join")
async def admin_join_ticket(
    ticket_id: int,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
):
    """Admin joins the ticket (marks as active)."""
    ticket = (
        session.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = TicketStatus.ACTIVE.value
    ticket.agent_joined_at = datetime.now(UTC)

    add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="system",
        sender_name="System",
        content="A support agent has joined the conversation.",
        session=session,
    )

    session.commit()

    return {"status": "joined", "ticket_id": ticket_id}


class AdminReplyRequest(BaseModel):
    content: str


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(
    ticket_id: int,
    payload: AdminReplyRequest,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
):
    """Admin sends a message to the ticket."""
    ticket = (
        session.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Auto-join if not already
    if ticket.status == TicketStatus.WAITING.value:
        ticket.status = TicketStatus.ACTIVE.value
        ticket.agent_joined_at = datetime.now(UTC)
        session.commit()

    agent_name = admin.full_name or admin.email.split("@")[0]

    message = add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="agent",
        sender_name=agent_name,
        content=payload.content,
        session=session,
    )

    return {
        "id": message.id,
        "sender_type": message.sender_type,
        "sender_name": message.sender_name,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


class CloseTicketRequest(BaseModel):
    resolution_summary: str
    resolution_category: str
    add_to_knowledge_base: bool = False


@router.post("/admin/tickets/{ticket_id}/close")
async def admin_close_ticket(
    ticket_id: int,
    payload: CloseTicketRequest,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
):
    """Close a support ticket with resolution details."""
    ticket = close_ticket(
        ticket_id=ticket_id,
        session=session,
        resolution_summary=payload.resolution_summary,
        resolution_category=payload.resolution_category,
        add_to_kb=payload.add_to_knowledge_base,
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get messages for transcript
    messages = (
        session.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at.asc())
        .all()
    )

    messages_dict = [
        {
            "sender_type": m.sender_type,
            "sender_name": m.sender_name,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # Send transcript email
    notify_ticket_resolved(ticket, messages_dict)

    return {"status": "closed", "ticket_id": ticket_id}
