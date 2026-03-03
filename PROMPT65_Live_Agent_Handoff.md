# PROMPT45_Live_Agent_Handoff.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, SIEVE-IMPLEMENTATION.md, and PROMPT24_Sieve_v2.md before making changes.

## Purpose

Enable real-time live agent support within the Sieve chatbot. When a user requests human help or Sieve cannot resolve their issue, the system escalates to Ron (the admin), who can join the conversation as a third participant. This creates a seamless handoff from AI to human support without leaving the Sieve widget.

**Key Features:**
- Automatic and manual escalation triggers
- Real-time bidirectional messaging via WebSockets
- Multi-channel notifications (Email + SMS + Push)
- Business hours awareness (08:00-18:00 CST Mon-Sat)
- Conversation transcript emailing upon resolution
- Knowledge base learning from resolved tickets

---

## Triggers — When to Use This Prompt

- Implementing live agent handoff in Sieve
- Adding WebSocket-based real-time chat
- Creating an admin support dashboard
- Setting up multi-channel notifications (Email/SMS/Push)
- Building support ticket management system

---

## What Already Exists (DO NOT recreate)

1. **Sieve widget:** `apps/web/app/components/sieve/SieveWidget.tsx` — fully styled chatbot with FAB, chat panel, message bubbles, typing indicator, input field, API integration to `/api/sieve/chat`.

2. **Sieve backend:** `services/api/app/services/sieve.py` — Claude-powered chat with user context awareness.

3. **Sieve router:** `services/api/app/routers/sieve.py` — `POST /api/sieve/chat` and `POST /api/sieve/triggers` endpoints.

4. **Sieve conversation model:** `services/api/app/models/sieve_conversation.py` — `sieve_conversations` table for message persistence (if implemented from PROMPT24).

5. **Email service:** Resend SDK configured with `RESEND_API_KEY` in environment.

6. **SMS service:** Telnyx configured with `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER` in environment (from PROMPT_AUTH_ONBOARDING_V1).

7. **Auth system:** `get_current_user` dependency resolves user from cookie or Bearer token.

8. **Admin token:** `ADMIN_TOKEN` for admin endpoint authentication.

9. **Redis:** Already configured for caching and RQ queues.

10. **WebSocket support:** FastAPI supports WebSockets natively; Cloud Run supports WebSocket connections.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LIVE AGENT HANDOFF FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER (Sieve Widget)                   BACKEND                    ADMIN     │
│  ───────────────────                   ───────                    ─────     │
│                                                                             │
│  1. "I need to talk to                                                      │
│      a real person"     ─────────────► Detect escalation trigger            │
│                                              │                              │
│                                              ▼                              │
│                                        Create support_ticket                │
│                                        (status: 'waiting')                  │
│                                              │                              │
│                                              ├─────────► Email (Resend)     │
│                                              │           ron@winnowcc.com   │
│                                              │                              │
│                                              ├─────────► SMS (Telnyx)       │
│                                              │           +1-XXX-XXX-XXXX    │
│                                              │                              │
│                                              ├─────────► Push (Future)      │
│                                              │                              │
│                                              ▼                              │
│  2. "Connecting you to a ◄─────────── Response to user                      │
│      live agent..."                                                         │
│      [WAITING FOR AGENT]                                                    │
│                                                                             │
│  3. WebSocket opens     ═══════════════════════════════════ WS opens        │
│     /ws/support/{id}           Redis Pub/Sub              /ws/admin/{id}    │
│                                     │                                       │
│  4. User types message  ═══════════════════════════════════► Agent sees     │
│                                                              message        │
│                                                                             │
│  5. User sees message   ◄═══════════════════════════════════ Agent types    │
│     [LIVE AGENT BADGE]                                       response       │
│                                                                             │
│  6. "Thanks for your    ◄─────────── Agent closes ticket                    │
│      help!"                               │                                 │
│                                           ├─────────► Email transcript      │
│                                           │           to ron@winnowcc.com   │
│                                           │                                 │
│                                           └─────────► Add to Sieve KB       │
│                                                       (if marked helpful)   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What to Build

This prompt covers 8 parts. Implement in order.

---

# PART 1 — DATABASE: SUPPORT TICKETS TABLE

### 1.1 Create the support ticket model

**File to create:** `services/api/app/models/support_ticket.py`

```python
"""
Support ticket model for live agent escalations.
Tracks conversations that have been escalated from Sieve AI to human support.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import enum

from app.db.base import Base


class TicketStatus(str, enum.Enum):
    WAITING = "waiting"      # User is waiting for agent
    ACTIVE = "active"        # Agent has joined
    RESOLVED = "resolved"    # Ticket closed successfully
    ABANDONED = "abandoned"  # User left before resolution


class TicketPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Who created the ticket
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user = relationship("User", foreign_keys=[user_id])
    
    # Ticket metadata
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.WAITING, nullable=False, index=True)
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.NORMAL, nullable=False)
    
    # Escalation reason
    escalation_reason = Column(String(50), nullable=False)  # "user_request", "ai_uncertainty", "frustration"
    escalation_trigger = Column(Text, nullable=True)  # The message that triggered escalation
    
    # Context from the Sieve conversation before escalation
    pre_escalation_context = Column(JSONB, nullable=True)  # Last N messages before escalation
    
    # User info snapshot (in case profile changes)
    user_snapshot = Column(JSONB, nullable=True)  # {name, email, profile_summary}
    
    # Resolution
    resolution_summary = Column(Text, nullable=True)  # Agent's notes on how it was resolved
    resolution_category = Column(String(100), nullable=True)  # "billing", "technical", "feature_request", etc.
    add_to_knowledge_base = Column(Boolean, default=False)  # Should this be learned by Sieve?
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    agent_joined_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    messages = relationship("SupportMessage", back_populates="ticket", cascade="all, delete-orphan")


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    ticket_id = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket = relationship("SupportTicket", back_populates="messages")
    
    # Who sent it
    sender_type = Column(String(20), nullable=False)  # "user", "agent", "system"
    sender_id = Column(Integer, nullable=True)  # user_id or admin_id
    sender_name = Column(String(100), nullable=True)  # Display name
    
    # Message content
    content = Column(Text, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)  # When the recipient read it
```

### 1.2 Register the models

**File to modify:** `services/api/app/models/__init__.py`

Add these imports at the end of the file:

```python
from app.models.support_ticket import SupportTicket, SupportMessage, TicketStatus, TicketPriority
```

### 1.3 Create the database migration

**Run in PowerShell (from your project root):**

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "add support_tickets and support_messages tables"
alembic upgrade head
```

**What this does:**
- Creates a new migration file in `services/api/alembic/versions/`
- Creates the `support_tickets` table with all columns
- Creates the `support_messages` table with all columns
- Creates indexes on frequently queried columns

---

# PART 2 — BACKEND: ESCALATION SERVICE

### 2.1 Create the live agent service

This service handles escalation detection, ticket creation, and notifications.

**File to create:** `services/api/app/services/live_agent.py`

```python
"""
Live agent escalation service.
Handles detecting when escalation is needed, creating tickets,
and sending notifications to the admin.
"""
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import pytz

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.support_ticket import SupportTicket, SupportMessage, TicketStatus, TicketPriority
from app.models.candidate_profile import CandidateProfile

logger = logging.getLogger(__name__)

# Business hours configuration
BUSINESS_TIMEZONE = pytz.timezone("America/Chicago")  # CST
BUSINESS_HOURS_START = 8   # 08:00
BUSINESS_HOURS_END = 18    # 18:00
BUSINESS_DAYS = [0, 1, 2, 3, 4, 5]  # Monday=0 through Saturday=5

# Admin contact info (from environment)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ron@winnowcc.com")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "")  # Format: +1XXXXXXXXXX

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
    
    # Check day of week (0=Monday, 6=Sunday)
    if now.weekday() not in BUSINESS_DAYS:
        return False
    
    # Check hour
    if now.hour < BUSINESS_HOURS_START or now.hour >= BUSINESS_HOURS_END:
        return False
    
    return True


def get_next_business_hours() -> str:
    """Get a human-readable string for when business hours resume."""
    now = datetime.now(BUSINESS_TIMEZONE)
    
    # If it's a business day but before hours
    if now.weekday() in BUSINESS_DAYS and now.hour < BUSINESS_HOURS_START:
        return f"today at {BUSINESS_HOURS_START}:00 AM CST"
    
    # If it's a business day but after hours, or Sunday
    if now.weekday() == 6:  # Sunday
        return "Monday at 8:00 AM CST"
    elif now.weekday() == 5:  # Saturday after hours
        return "Monday at 8:00 AM CST"
    else:
        return "tomorrow at 8:00 AM CST"


def detect_escalation_trigger(
    message: str,
    conversation_history: list[dict],
) -> Optional[tuple[str, str]]:
    """
    Detect if the user's message or conversation state warrants escalation.
    
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


def get_user_snapshot(user: User, db: Session) -> dict:
    """Build a snapshot of user info for the ticket."""
    snapshot = {
        "user_id": user.id,
        "email": user.email,
    }
    
    # Get profile info
    try:
        profile = db.query(CandidateProfile).filter(
            CandidateProfile.user_id == user.id
        ).order_by(CandidateProfile.version.desc()).first()
        
        if profile and profile.profile_json:
            pj = profile.profile_json if isinstance(profile.profile_json, dict) else json.loads(profile.profile_json)
            snapshot["name"] = pj.get("basics", {}).get("name", "Unknown")
            snapshot["title"] = pj.get("basics", {}).get("title", "")
            snapshot["location"] = pj.get("basics", {}).get("location", "")
        else:
            snapshot["name"] = user.email.split("@")[0]  # Fallback
    except Exception as e:
        logger.warning(f"Failed to get user snapshot: {e}")
        snapshot["name"] = user.email.split("@")[0]
    
    return snapshot


def create_support_ticket(
    user: User,
    db: Session,
    escalation_reason: str,
    escalation_trigger: str,
    conversation_history: list[dict],
    priority: TicketPriority = TicketPriority.NORMAL,
) -> SupportTicket:
    """
    Create a new support ticket for live agent escalation.
    
    Args:
        user: The user requesting support
        db: Database session
        escalation_reason: Why escalation occurred ("user_request", "ai_uncertainty", "frustration")
        escalation_trigger: The message that triggered escalation
        conversation_history: Recent Sieve conversation for context
        priority: Ticket priority level
    
    Returns:
        The created SupportTicket
    """
    # Build user snapshot
    user_snapshot = get_user_snapshot(user, db)
    
    # Keep last 10 messages as pre-escalation context
    pre_context = conversation_history[-10:] if conversation_history else []
    
    # Determine priority based on reason
    if escalation_reason == "frustration":
        priority = TicketPriority.HIGH
    elif escalation_reason == "user_request":
        priority = TicketPriority.NORMAL
    
    # Create the ticket
    ticket = SupportTicket(
        user_id=user.id,
        status=TicketStatus.WAITING,
        priority=priority,
        escalation_reason=escalation_reason,
        escalation_trigger=escalation_trigger,
        pre_escalation_context=pre_context,
        user_snapshot=user_snapshot,
    )
    
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # Add initial system message
    system_msg = SupportMessage(
        ticket_id=ticket.id,
        sender_type="system",
        sender_name="Sieve",
        content=f"Ticket created. Reason: {escalation_reason}. User is waiting for a live agent.",
    )
    db.add(system_msg)
    db.commit()
    
    logger.info(f"Created support ticket {ticket.id} for user {user.id}, reason: {escalation_reason}")
    
    return ticket


def add_message_to_ticket(
    ticket_id: int,
    sender_type: str,
    content: str,
    db: Session,
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
    db.add(message)
    db.commit()
    db.refresh(message)
    
    return message


def get_ticket_with_messages(ticket_id: int, db: Session) -> Optional[dict]:
    """Get a ticket with all its messages."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        return None
    
    messages = db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket_id
    ).order_by(SupportMessage.created_at.asc()).all()
    
    return {
        "ticket": {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
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
    db: Session,
    resolution_summary: str,
    resolution_category: str,
    add_to_kb: bool = False,
) -> Optional[SupportTicket]:
    """Close a support ticket with resolution details."""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        return None
    
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = datetime.now(timezone.utc)
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
    db.add(close_msg)
    
    db.commit()
    db.refresh(ticket)
    
    logger.info(f"Closed support ticket {ticket.id} with category: {resolution_category}")
    
    return ticket
```

### 2.2 Create the notification service

**File to create:** `services/api/app/services/support_notifications.py`

```python
"""
Support notification service.
Sends notifications to admin when tickets are created or updated.
Uses Email (Resend), SMS (Telnyx), and prepares for Push notifications.
"""
import os
import logging
from datetime import datetime, timezone

import resend
from telnyx import Message as TelnyxMessage
import telnyx

from app.models.support_ticket import SupportTicket, TicketPriority

logger = logging.getLogger(__name__)

# Admin contact info
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ron@winnowcc.com")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "")  # +1XXXXXXXXXX format

# API keys
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
TELNYX_API_KEY = os.environ.get("TELNYX_API_KEY", "")
TELNYX_PHONE = os.environ.get("TELNYX_PHONE_NUMBER", "")

# Configure clients
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

if TELNYX_API_KEY:
    telnyx.api_key = TELNYX_API_KEY


def send_escalation_email(ticket: SupportTicket) -> bool:
    """
    Send an email notification to admin about a new support ticket.
    Includes conversation context and direct link to admin dashboard.
    """
    if not RESEND_API_KEY or not ADMIN_EMAIL:
        logger.warning("Email notification skipped: RESEND_API_KEY or ADMIN_EMAIL not configured")
        return False
    
    try:
        # Get user info from snapshot
        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "Unknown User")
        user_email = user_info.get("email", "unknown@email.com")
        
        # Build context summary
        context_html = ""
        if ticket.pre_escalation_context:
            context_html = "<h3>Recent Conversation:</h3><ul>"
            for msg in ticket.pre_escalation_context[-5:]:  # Last 5 messages
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate
                role_label = "User" if role == "user" else "Sieve"
                context_html += f"<li><strong>{role_label}:</strong> {content}</li>"
            context_html += "</ul>"
        
        # Priority emoji
        priority_emoji = {
            TicketPriority.LOW: "🟢",
            TicketPriority.NORMAL: "🟡",
            TicketPriority.HIGH: "🟠",
            TicketPriority.URGENT: "🔴",
        }.get(ticket.priority, "🟡")
        
        # Dashboard URL (update with your actual domain)
        dashboard_url = os.environ.get("APP_BASE_URL", "http://localhost:3000")
        ticket_url = f"{dashboard_url}/admin/support/{ticket.id}"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2>{priority_emoji} Live Agent Request from {user_name}</h2>
            
            <p><strong>Ticket #{ticket.id}</strong> | Priority: {ticket.priority.value.upper()}</p>
            
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>User:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{user_name} ({user_email})</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.escalation_reason}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Trigger:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.escalation_trigger or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC</td>
                </tr>
            </table>
            
            {context_html}
            
            <p style="margin-top: 20px;">
                <a href="{ticket_url}" style="background-color: #1B3025; color: #E8C84A; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Open Support Dashboard →
                </a>
            </p>
            
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This notification was sent by Winnow Career Concierge.
            </p>
        </div>
        """
        
        params = {
            "from": "Winnow Support <support@winnowcc.com>",
            "to": [ADMIN_EMAIL],
            "subject": f"🚨 Live Agent Request: {user_name} needs help",
            "html": html_body,
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Escalation email sent for ticket {ticket.id}: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send escalation email for ticket {ticket.id}: {e}")
        return False


def send_escalation_sms(ticket: SupportTicket) -> bool:
    """
    Send an SMS notification to admin about a new support ticket.
    Short message with essential info and link.
    """
    if not TELNYX_API_KEY or not ADMIN_PHONE or not TELNYX_PHONE:
        logger.warning("SMS notification skipped: Telnyx not configured")
        return False
    
    try:
        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "User")
        
        # Dashboard URL
        dashboard_url = os.environ.get("APP_BASE_URL", "http://localhost:3000")
        ticket_url = f"{dashboard_url}/admin/support/{ticket.id}"
        
        # Keep SMS concise
        message_text = f"🚨 Winnow: {user_name} needs live help. Reason: {ticket.escalation_reason}. Ticket #{ticket.id}. {ticket_url}"
        
        response = telnyx.Message.create(
            from_=TELNYX_PHONE,
            to=ADMIN_PHONE,
            text=message_text,
        )
        
        logger.info(f"Escalation SMS sent for ticket {ticket.id}: {response.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send escalation SMS for ticket {ticket.id}: {e}")
        return False


def send_resolution_transcript_email(ticket: SupportTicket, messages: list[dict]) -> bool:
    """
    Send a transcript of the resolved conversation to admin for records.
    """
    if not RESEND_API_KEY or not ADMIN_EMAIL:
        logger.warning("Transcript email skipped: RESEND_API_KEY or ADMIN_EMAIL not configured")
        return False
    
    try:
        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "Unknown User")
        
        # Build transcript HTML
        transcript_html = "<div style='font-family: monospace; background: #f5f5f5; padding: 20px;'>"
        for msg in messages:
            sender = msg.get("sender_name") or msg.get("sender_type", "Unknown")
            content = msg.get("content", "")
            timestamp = msg.get("created_at", "")
            
            color = "#1B3025" if msg.get("sender_type") == "agent" else "#333"
            transcript_html += f"""
                <div style="margin-bottom: 15px; border-left: 3px solid {color}; padding-left: 10px;">
                    <strong>{sender}</strong> <span style="color: #999; font-size: 12px;">({timestamp})</span>
                    <p style="margin: 5px 0;">{content}</p>
                </div>
            """
        transcript_html += "</div>"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px;">
            <h2>✅ Support Ticket Resolved - #{ticket.id}</h2>
            
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>User:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{user_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Category:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.resolution_category or 'Unspecified'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Resolution:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.resolution_summary or 'No summary provided'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Duration:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{_calculate_duration(ticket)}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Added to KB:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{'Yes' if ticket.add_to_knowledge_base else 'No'}</td>
                </tr>
            </table>
            
            <h3>Conversation Transcript</h3>
            {transcript_html}
            
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This transcript was generated by Winnow Career Concierge for your records.
            </p>
        </div>
        """
        
        params = {
            "from": "Winnow Support <support@winnowcc.com>",
            "to": [ADMIN_EMAIL],
            "subject": f"✅ Ticket #{ticket.id} Resolved - {user_name}",
            "html": html_body,
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Resolution transcript sent for ticket {ticket.id}: {response}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send resolution transcript for ticket {ticket.id}: {e}")
        return False


def _calculate_duration(ticket: SupportTicket) -> str:
    """Calculate human-readable duration from creation to resolution."""
    if not ticket.resolved_at or not ticket.created_at:
        return "Unknown"
    
    delta = ticket.resolved_at - ticket.created_at
    minutes = int(delta.total_seconds() / 60)
    
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    hours = minutes // 60
    remaining_mins = minutes % 60
    return f"{hours}h {remaining_mins}m"


def notify_new_ticket(ticket: SupportTicket) -> dict:
    """
    Send all configured notifications for a new ticket.
    Returns a dict of which channels succeeded.
    """
    results = {
        "email": send_escalation_email(ticket),
        "sms": send_escalation_sms(ticket),
        "push": False,  # TODO: Implement push notifications
    }
    
    logger.info(f"Ticket {ticket.id} notifications sent: {results}")
    return results


def notify_ticket_resolved(ticket: SupportTicket, messages: list[dict]) -> dict:
    """
    Send resolution notifications including transcript.
    """
    results = {
        "transcript_email": send_resolution_transcript_email(ticket, messages),
    }
    
    logger.info(f"Ticket {ticket.id} resolution notifications sent: {results}")
    return results
```

---

# PART 3 — BACKEND: SUPPORT API ENDPOINTS

### 3.1 Create the support router

**File to create:** `services/api/app/routers/support.py`

```python
"""
Support ticket API endpoints.
Handles live agent escalation from Sieve and admin ticket management.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.services.auth import get_current_user
from app.models.user import User
from app.models.support_ticket import SupportTicket, SupportMessage, TicketStatus, TicketPriority
from app.services.live_agent import (
    detect_escalation_trigger,
    create_support_ticket,
    add_message_to_ticket,
    get_ticket_with_messages,
    close_ticket,
    is_within_business_hours,
    get_next_business_hours,
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
    db: Session = Depends(get_db),
):
    """
    Escalate the current Sieve conversation to a live agent.
    Creates a support ticket and notifies the admin.
    
    Called when:
    - User explicitly requests human help
    - Sieve detects it cannot answer the question
    - Frustration is detected in the conversation
    """
    # Check for existing open ticket
    existing = db.query(SupportTicket).filter(
        SupportTicket.user_id == user.id,
        SupportTicket.status.in_([TicketStatus.WAITING, TicketStatus.ACTIVE]),
    ).first()
    
    if existing:
        return EscalateResponse(
            ticket_id=existing.id,
            status=existing.status.value,
            message="You already have an open support ticket. An agent will be with you shortly.",
            within_business_hours=is_within_business_hours(),
        )
    
    # Detect escalation reason
    trigger_result = detect_escalation_trigger(payload.message, payload.conversation_history)
    
    if trigger_result:
        reason, trigger = trigger_result
    else:
        reason = "user_request"
        trigger = payload.message
    
    # Create the ticket
    ticket = create_support_ticket(
        user=user,
        db=db,
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
        next_hours = get_next_business_hours()
        response_message = f"I've created a support ticket for you. Our team will respond {next_hours}."
        expected = next_hours
    
    return EscalateResponse(
        ticket_id=ticket.id,
        status=ticket.status.value,
        message=response_message,
        within_business_hours=within_hours,
        expected_response=expected,
    )


class UserTicketStatusResponse(BaseModel):
    ticket_id: int
    status: str
    agent_joined: bool
    messages: list[dict]


@router.get("/ticket/active", response_model=Optional[UserTicketStatusResponse])
async def get_active_ticket(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the user's currently active support ticket, if any.
    Used by the Sieve widget to check if there's an ongoing live agent session.
    """
    ticket = db.query(SupportTicket).filter(
        SupportTicket.user_id == user.id,
        SupportTicket.status.in_([TicketStatus.WAITING, TicketStatus.ACTIVE]),
    ).first()
    
    if not ticket:
        return None
    
    messages = db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket.id
    ).order_by(SupportMessage.created_at.asc()).all()
    
    return UserTicketStatusResponse(
        ticket_id=ticket.id,
        status=ticket.status.value,
        agent_joined=ticket.agent_joined_at is not None,
        messages=[
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    )


class SendMessageRequest(BaseModel):
    content: str


@router.post("/ticket/{ticket_id}/message")
async def user_send_message(
    ticket_id: int,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Send a message to the support ticket (user side).
    """
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == user.id,
        SupportTicket.status.in_([TicketStatus.WAITING, TicketStatus.ACTIVE]),
    ).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or not accessible")
    
    # Get user name from snapshot
    user_name = (ticket.user_snapshot or {}).get("name", "User")
    
    message = add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="user",
        sender_id=user.id,
        sender_name=user_name,
        content=payload.content,
        db=db,
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

def verify_admin(x_admin_token: str = Header(None)) -> bool:
    """Verify the admin token from request header."""
    import os
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    
    if not admin_token:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured")
    
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    
    return True


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
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    List all support tickets (admin only).
    Optionally filter by status.
    """
    query = db.query(SupportTicket)
    
    if status:
        try:
            status_enum = TicketStatus(status)
            query = query.filter(SupportTicket.status == status_enum)
        except ValueError:
            pass
    
    tickets = query.order_by(desc(SupportTicket.created_at)).limit(100).all()
    
    result = []
    for t in tickets:
        user_info = t.user_snapshot or {}
        
        # Calculate waiting time
        now = datetime.now(timezone.utc)
        waiting_mins = int((now - t.created_at).total_seconds() / 60) if t.created_at else 0
        
        # Get last message
        last_msg = db.query(SupportMessage).filter(
            SupportMessage.ticket_id == t.id
        ).order_by(desc(SupportMessage.created_at)).first()
        
        result.append(TicketListItem(
            id=t.id,
            user_name=user_info.get("name", "Unknown"),
            user_email=user_info.get("email", "unknown"),
            status=t.status.value,
            priority=t.priority.value,
            escalation_reason=t.escalation_reason,
            created_at=t.created_at.isoformat() if t.created_at else "",
            waiting_minutes=waiting_mins,
            last_message=last_msg.content[:100] if last_msg else None,
        ))
    
    return TicketListResponse(tickets=result, total=len(result))


@router.get("/admin/tickets/{ticket_id}")
async def admin_get_ticket(
    ticket_id: int,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get full details of a support ticket including all messages (admin only).
    """
    result = get_ticket_with_messages(ticket_id, db)
    
    if not result:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return result


@router.post("/admin/tickets/{ticket_id}/join")
async def admin_join_ticket(
    ticket_id: int,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Admin joins the ticket (marks as active).
    """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = TicketStatus.ACTIVE
    ticket.agent_joined_at = datetime.now(timezone.utc)
    
    # Add system message
    add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="system",
        sender_name="System",
        content="A support agent has joined the conversation.",
        db=db,
    )
    
    db.commit()
    
    return {"status": "joined", "ticket_id": ticket_id}


class AdminReplyRequest(BaseModel):
    content: str


@router.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_to_ticket(
    ticket_id: int,
    payload: AdminReplyRequest,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Admin sends a message to the ticket.
    """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Auto-join if not already
    if ticket.status == TicketStatus.WAITING:
        ticket.status = TicketStatus.ACTIVE
        ticket.agent_joined_at = datetime.now(timezone.utc)
        db.commit()
    
    message = add_message_to_ticket(
        ticket_id=ticket_id,
        sender_type="agent",
        sender_name="Ron",  # Or get from admin user
        content=payload.content,
        db=db,
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
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Close a support ticket with resolution details.
    Sends transcript email and optionally adds to Sieve knowledge base.
    """
    ticket = close_ticket(
        ticket_id=ticket_id,
        db=db,
        resolution_summary=payload.resolution_summary,
        resolution_category=payload.resolution_category,
        add_to_kb=payload.add_to_knowledge_base,
    )
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Get messages for transcript
    messages = db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket_id
    ).order_by(SupportMessage.created_at.asc()).all()
    
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
    
    # TODO: If add_to_knowledge_base is True, process the conversation
    # and add relevant Q&A pairs to Sieve's training data
    
    return {"status": "closed", "ticket_id": ticket_id}
```

### 3.2 Register the support router

**File to modify:** `services/api/app/main.py`

Find the section where routers are registered (look for `app.include_router`). Add:

```python
from app.routers import support

app.include_router(support.router)
```

---

# PART 4 — BACKEND: WEBSOCKET FOR REAL-TIME MESSAGING

### 4.1 Create the WebSocket handler

**File to create:** `services/api/app/routers/support_ws.py`

```python
"""
WebSocket handlers for real-time support chat.
Enables instant message delivery between users and agents.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.support_ticket import SupportTicket, SupportMessage, TicketStatus
from app.services.live_agent import add_message_to_ticket

logger = logging.getLogger(__name__)

router = APIRouter()

# Connection managers - one for user connections, one for admin
class ConnectionManager:
    def __init__(self):
        # ticket_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, ticket_id: int, websocket: WebSocket):
        await websocket.accept()
        if ticket_id not in self.active_connections:
            self.active_connections[ticket_id] = set()
        self.active_connections[ticket_id].add(websocket)
        logger.info(f"WebSocket connected for ticket {ticket_id}. Total: {len(self.active_connections[ticket_id])}")
    
    def disconnect(self, ticket_id: int, websocket: WebSocket):
        if ticket_id in self.active_connections:
            self.active_connections[ticket_id].discard(websocket)
            if not self.active_connections[ticket_id]:
                del self.active_connections[ticket_id]
        logger.info(f"WebSocket disconnected for ticket {ticket_id}")
    
    async def broadcast(self, ticket_id: int, message: dict, exclude: WebSocket = None):
        """Send message to all connections for a ticket except the sender."""
        if ticket_id in self.active_connections:
            for connection in self.active_connections[ticket_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Failed to send to WebSocket: {e}")


# Shared connection manager for all ticket chats
manager = ConnectionManager()


@router.websocket("/ws/support/{ticket_id}")
async def websocket_support_chat(
    websocket: WebSocket,
    ticket_id: int,
    token: str = Query(None),  # Auth token passed as query param
    role: str = Query("user"),  # "user" or "admin"
):
    """
    WebSocket endpoint for real-time support chat.
    
    Connect with:
    - User: ws://host/ws/support/123?token=USER_SESSION_TOKEN&role=user
    - Admin: ws://host/ws/support/123?token=ADMIN_TOKEN&role=admin
    """
    # Get DB session
    from app.db.session import SessionLocal
    db = SessionLocal()
    
    try:
        # Verify ticket exists
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            await websocket.close(code=4004, reason="Ticket not found")
            return
        
        # Verify authorization
        import os
        if role == "admin":
            admin_token = os.environ.get("ADMIN_TOKEN", "")
            if token != admin_token:
                await websocket.close(code=4001, reason="Invalid admin token")
                return
            sender_type = "agent"
            sender_name = "Ron"
        else:
            # For user role, verify the token matches the ticket owner
            # In production, decode JWT and check user_id matches ticket.user_id
            # For now, we'll trust the connection if they have the ticket_id
            sender_type = "user"
            sender_name = (ticket.user_snapshot or {}).get("name", "User")
        
        # Connect to the ticket room
        await manager.connect(ticket_id, websocket)
        
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "ticket_id": ticket_id,
            "status": ticket.status.value,
            "role": role,
        })
        
        # Listen for messages
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get("type") == "message":
                    content = data.get("content", "").strip()
                    
                    if not content:
                        continue
                    
                    # Save message to database
                    message = add_message_to_ticket(
                        ticket_id=ticket_id,
                        sender_type=sender_type,
                        sender_name=sender_name,
                        content=content,
                        db=db,
                    )
                    
                    # Broadcast to all connections (including sender for confirmation)
                    broadcast_data = {
                        "type": "message",
                        "id": message.id,
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                        "content": content,
                        "created_at": message.created_at.isoformat() if message.created_at else None,
                    }
                    
                    # Send to all including sender
                    for conn in manager.active_connections.get(ticket_id, set()):
                        try:
                            await conn.send_json(broadcast_data)
                        except Exception:
                            pass
                
                elif data.get("type") == "typing":
                    # Broadcast typing indicator to others
                    typing_data = {
                        "type": "typing",
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                    }
                    await manager.broadcast(ticket_id, typing_data, exclude=websocket)
                
                elif data.get("type") == "read":
                    # Mark messages as read (optional feature)
                    pass
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"WebSocket error for ticket {ticket_id}: {e}")
                break
    
    finally:
        manager.disconnect(ticket_id, websocket)
        db.close()


@router.websocket("/ws/admin/tickets")
async def websocket_admin_ticket_feed(
    websocket: WebSocket,
    token: str = Query(None),
):
    """
    WebSocket endpoint for admin to receive notifications about new tickets.
    
    Connect with: ws://host/ws/admin/tickets?token=ADMIN_TOKEN
    """
    import os
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    
    if token != admin_token:
        await websocket.close(code=4001, reason="Invalid admin token")
        return
    
    await websocket.accept()
    
    # This would connect to Redis pub/sub for new ticket notifications
    # For simplicity, we'll just keep the connection alive
    # In production, subscribe to a Redis channel for new tickets
    
    try:
        while True:
            # Keep connection alive, waiting for messages
            # In production, this would be fed by Redis pub/sub
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
```

### 4.2 Register the WebSocket router

**File to modify:** `services/api/app/main.py`

Add:

```python
from app.routers import support_ws

app.include_router(support_ws.router)
```

---

# PART 5 — FRONTEND: UPDATE SIEVE WIDGET FOR LIVE AGENT MODE

### 5.1 Add live agent state to SieveWidget

**File to modify:** `apps/web/app/components/sieve/SieveWidget.tsx`

Add these imports at the top:

```typescript
import { useEffect, useRef, useCallback } from "react";
```

Add these new state variables inside the component (near the existing useState calls):

```typescript
// Live agent state
const [liveAgentMode, setLiveAgentMode] = useState(false);
const [activeTicket, setActiveTicket] = useState<{
  ticket_id: number;
  status: string;
  agent_joined: boolean;
} | null>(null);
const [isEscalating, setIsEscalating] = useState(false);
const wsRef = useRef<WebSocket | null>(null);
```

Add the escalation function:

```typescript
async function escalateToAgent(message: string, history: { role: string; content: string }[]) {
  setIsEscalating(true);
  
  try {
    const res = await fetch(`${API_BASE}/api/support/escalate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        message,
        conversation_history: history,
      }),
    });
    
    if (!res.ok) {
      throw new Error("Failed to escalate");
    }
    
    const data = await res.json();
    
    setActiveTicket({
      ticket_id: data.ticket_id,
      status: data.status,
      agent_joined: false,
    });
    setLiveAgentMode(true);
    
    // Add system message to chat
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: data.message,
        isSystem: true,
      },
    ]);
    
    // Connect WebSocket for real-time updates
    connectWebSocket(data.ticket_id);
    
  } catch (error) {
    console.error("Escalation error:", error);
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "I'm having trouble connecting you to support. Please try again or email support@winnowcc.com.",
      },
    ]);
  } finally {
    setIsEscalating(false);
  }
}
```

Add WebSocket connection function:

```typescript
const connectWebSocket = useCallback((ticketId: number) => {
  // Close existing connection if any
  if (wsRef.current) {
    wsRef.current.close();
  }
  
  const wsUrl = `${API_BASE.replace('http', 'ws')}/ws/support/${ticketId}?role=user`;
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    console.log("WebSocket connected for ticket", ticketId);
  };
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      if (data.type === "connected") {
        // Connection confirmed
        if (data.status === "active") {
          setActiveTicket((prev) => prev ? { ...prev, agent_joined: true } : null);
        }
      } else if (data.type === "message") {
        // New message from agent
        if (data.sender_type === "agent") {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.content,
              senderName: data.sender_name,
              isAgent: true,
            },
          ]);
          setActiveTicket((prev) => prev ? { ...prev, agent_joined: true } : null);
        }
        // Also handle system messages
        if (data.sender_type === "system") {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.content,
              isSystem: true,
            },
          ]);
        }
      } else if (data.type === "typing") {
        // Show typing indicator for agent
        if (data.sender_type === "agent") {
          setIsTyping(true);
          setTimeout(() => setIsTyping(false), 3000);
        }
      }
    } catch (e) {
      console.error("WebSocket message parse error:", e);
    }
  };
  
  ws.onclose = () => {
    console.log("WebSocket closed");
  };
  
  ws.onerror = (error) => {
    console.error("WebSocket error:", error);
  };
  
  wsRef.current = ws;
}, []);
```

Modify the `handleSend` function to detect escalation requests and handle live agent mode:

```typescript
async function handleSend() {
  if (!input.trim()) return;
  const userMessage = input.trim();
  setInput("");

  // Add user message to display
  setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

  // Build history for context
  const history = [...conversationHistory, { role: "user", content: userMessage }];

  // Check if in live agent mode
  if (liveAgentMode && activeTicket) {
    // Send via WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "message",
        content: userMessage,
      }));
    } else {
      // Fallback to REST API
      await fetch(`${API_BASE}/api/support/ticket/${activeTicket.ticket_id}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ content: userMessage }),
      });
    }
    
    // Update conversation history
    setConversationHistory([
      ...history,
      { role: "user", content: userMessage },
    ]);
    
    return;
  }

  // Check for escalation trigger phrases
  const escalationPhrases = [
    "talk to a person",
    "talk to someone",
    "speak to a human",
    "human help",
    "live agent",
    "representative",
    "customer support",
    "real person",
  ];
  
  const shouldEscalate = escalationPhrases.some(phrase => 
    userMessage.toLowerCase().includes(phrase)
  );
  
  if (shouldEscalate) {
    await escalateToAgent(userMessage, history);
    return;
  }

  // Normal Sieve AI flow
  setIsTyping(true);

  const result = await sendMessage(userMessage, history);

  // Update conversation history
  setConversationHistory([
    ...history,
    { role: "assistant", content: result.response },
  ]);

  // Add assistant response to display
  setMessages((prev) => [...prev, { role: "assistant", content: result.response }]);
  setSuggestions(result.suggestions || []);
  setIsTyping(false);
}
```

Add cleanup effect:

```typescript
useEffect(() => {
  return () => {
    // Cleanup WebSocket on unmount
    if (wsRef.current) {
      wsRef.current.close();
    }
  };
}, []);
```

Add check for existing active ticket when widget opens:

```typescript
useEffect(() => {
  if (isOpen) {
    // Check for existing active support ticket
    fetch(`${API_BASE}/api/support/ticket/active`, {
      credentials: "include",
    })
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (data) {
          setActiveTicket({
            ticket_id: data.ticket_id,
            status: data.status,
            agent_joined: data.agent_joined,
          });
          setLiveAgentMode(true);
          connectWebSocket(data.ticket_id);
          
          // Load existing messages
          setMessages(data.messages.map((m: any) => ({
            role: m.sender_type === "user" ? "user" : "assistant",
            content: m.content,
            senderName: m.sender_name,
            isAgent: m.sender_type === "agent",
            isSystem: m.sender_type === "system",
          })));
        }
      })
      .catch(() => {});
  }
}, [isOpen, connectWebSocket]);
```

### 5.2 Update message bubble styling for agent messages

In the message rendering section, add visual distinction for agent vs AI messages:

```tsx
{/* Inside the messages.map */}
<div
  key={idx}
  style={{
    marginBottom: "12px",
    display: "flex",
    justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
  }}
>
  <div
    style={{
      maxWidth: "85%",
      padding: "10px 14px",
      borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
      backgroundColor: msg.role === "user" 
        ? "#1B3025" 
        : msg.isAgent 
          ? "#E8C84A"  // Gold for live agent
          : "#F5F0E4",
      color: msg.role === "user" 
        ? "#F0E8D0" 
        : msg.isAgent 
          ? "#1B3025"  // Dark text on gold
          : "#3E3525",
    }}
  >
    {/* Agent badge */}
    {msg.isAgent && (
      <div style={{ 
        fontSize: "10px", 
        fontWeight: "bold", 
        marginBottom: "4px",
        display: "flex",
        alignItems: "center",
        gap: "4px",
      }}>
        <span style={{ 
          width: "8px", 
          height: "8px", 
          borderRadius: "50%", 
          backgroundColor: "#5CB87A",
          display: "inline-block",
        }} />
        LIVE AGENT: {msg.senderName || "Support"}
      </div>
    )}
    
    {/* System message styling */}
    {msg.isSystem && (
      <div style={{ 
        fontSize: "12px", 
        fontStyle: "italic",
        color: "#666",
        textAlign: "center",
      }}>
        {msg.content}
      </div>
    )}
    
    {/* Regular message content */}
    {!msg.isSystem && (
      <span>{msg.content}</span>
    )}
  </div>
</div>
```

### 5.3 Add live agent status indicator in header

In the header section, add a visual indicator when in live agent mode:

```tsx
{/* Inside the header, near the "Online" status */}
{liveAgentMode && (
  <div style={{
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "4px 8px",
    backgroundColor: "#E8C84A",
    borderRadius: "12px",
    fontSize: "10px",
    fontWeight: "bold",
    color: "#1B3025",
  }}>
    <span style={{
      width: "6px",
      height: "6px",
      borderRadius: "50%",
      backgroundColor: activeTicket?.agent_joined ? "#5CB87A" : "#ff9800",
      animation: activeTicket?.agent_joined ? "none" : "pulse 1.5s infinite",
    }} />
    {activeTicket?.agent_joined ? "LIVE AGENT CONNECTED" : "WAITING FOR AGENT..."}
  </div>
)}
```

---

# PART 6 — FRONTEND: ADMIN SUPPORT DASHBOARD

### 6.1 Create the admin support dashboard page

**File to create:** `apps/web/app/admin/support/page.tsx`

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface Ticket {
  id: number;
  user_name: string;
  user_email: string;
  status: string;
  priority: string;
  escalation_reason: string;
  created_at: string;
  waiting_minutes: number;
  last_message: string | null;
}

export default function AdminSupportPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("waiting");
  const [adminToken, setAdminToken] = useState<string>("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const router = useRouter();

  const fetchTickets = useCallback(async () => {
    if (!adminToken) return;
    
    try {
      const res = await fetch(
        `${API_BASE}/api/support/admin/tickets${statusFilter ? `?status=${statusFilter}` : ""}`,
        {
          headers: {
            "X-Admin-Token": adminToken,
          },
        }
      );
      
      if (res.status === 401) {
        setIsAuthenticated(false);
        return;
      }
      
      if (res.ok) {
        const data = await res.json();
        setTickets(data.tickets);
        setIsAuthenticated(true);
      }
    } catch (error) {
      console.error("Failed to fetch tickets:", error);
    } finally {
      setLoading(false);
    }
  }, [adminToken, statusFilter]);

  useEffect(() => {
    // Check for stored admin token
    const stored = localStorage.getItem("winnow_admin_token");
    if (stored) {
      setAdminToken(stored);
    } else {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (adminToken) {
      fetchTickets();
      // Refresh every 30 seconds
      const interval = setInterval(fetchTickets, 30000);
      return () => clearInterval(interval);
    }
  }, [adminToken, fetchTickets]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("winnow_admin_token", adminToken);
    fetchTickets();
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent": return "#dc3545";
      case "high": return "#fd7e14";
      case "normal": return "#ffc107";
      case "low": return "#28a745";
      default: return "#6c757d";
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      waiting: { bg: "#fff3cd", text: "#856404" },
      active: { bg: "#d4edda", text: "#155724" },
      resolved: { bg: "#d1ecf1", text: "#0c5460" },
      abandoned: { bg: "#f8d7da", text: "#721c24" },
    };
    const c = colors[status] || colors.waiting;
    
    return (
      <span style={{
        padding: "4px 8px",
        borderRadius: "4px",
        fontSize: "12px",
        fontWeight: "bold",
        backgroundColor: c.bg,
        color: c.text,
      }}>
        {status.toUpperCase()}
      </span>
    );
  };

  if (!isAuthenticated && !loading) {
    return (
      <div style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f5f5f5",
      }}>
        <form onSubmit={handleLogin} style={{
          backgroundColor: "white",
          padding: "40px",
          borderRadius: "12px",
          boxShadow: "0 4px 20px rgba(0,0,0,0.1)",
          width: "100%",
          maxWidth: "400px",
        }}>
          <h1 style={{ marginBottom: "24px", color: "#1B3025" }}>
            Admin Support Dashboard
          </h1>
          <input
            type="password"
            placeholder="Enter Admin Token"
            value={adminToken}
            onChange={(e) => setAdminToken(e.target.value)}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "6px",
              border: "1px solid #ddd",
              marginBottom: "16px",
              fontSize: "16px",
            }}
          />
          <button
            type="submit"
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "6px",
              backgroundColor: "#1B3025",
              color: "#E8C84A",
              border: "none",
              fontSize: "16px",
              fontWeight: "bold",
              cursor: "pointer",
            }}
          >
            Login
          </button>
        </form>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px", maxWidth: "1200px", margin: "0 auto" }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "24px",
      }}>
        <h1 style={{ color: "#1B3025", margin: 0 }}>
          Support Tickets
        </h1>
        <div style={{ display: "flex", gap: "8px" }}>
          {["waiting", "active", "resolved", ""].map((status) => (
            <button
              key={status || "all"}
              onClick={() => setStatusFilter(status)}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: statusFilter === status ? "2px solid #1B3025" : "1px solid #ddd",
                backgroundColor: statusFilter === status ? "#1B3025" : "white",
                color: statusFilter === status ? "#E8C84A" : "#333",
                cursor: "pointer",
                fontWeight: statusFilter === status ? "bold" : "normal",
              }}
            >
              {status || "All"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "40px" }}>Loading...</div>
      ) : tickets.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: "60px",
          backgroundColor: "#f9f9f9",
          borderRadius: "12px",
        }}>
          <p style={{ fontSize: "18px", color: "#666" }}>
            No {statusFilter} tickets found
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {tickets.map((ticket) => (
            <div
              key={ticket.id}
              onClick={() => router.push(`/admin/support/${ticket.id}?token=${adminToken}`)}
              style={{
                padding: "20px",
                backgroundColor: "white",
                borderRadius: "12px",
                boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                cursor: "pointer",
                borderLeft: `4px solid ${getPriorityColor(ticket.priority)}`,
                transition: "transform 0.2s, box-shadow 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.12)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
              }}
            >
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "12px",
              }}>
                <div>
                  <h3 style={{ margin: "0 0 4px 0", color: "#1B3025" }}>
                    {ticket.user_name}
                  </h3>
                  <p style={{ margin: 0, color: "#666", fontSize: "14px" }}>
                    {ticket.user_email}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                  {getStatusBadge(ticket.status)}
                  {ticket.status === "waiting" && (
                    <span style={{
                      fontSize: "12px",
                      color: ticket.waiting_minutes > 5 ? "#dc3545" : "#666",
                      fontWeight: ticket.waiting_minutes > 5 ? "bold" : "normal",
                    }}>
                      ⏱️ {ticket.waiting_minutes}m
                    </span>
                  )}
                </div>
              </div>
              
              <div style={{
                display: "flex",
                gap: "16px",
                fontSize: "13px",
                color: "#666",
              }}>
                <span>Reason: <strong>{ticket.escalation_reason}</strong></span>
                <span>Priority: <strong style={{ color: getPriorityColor(ticket.priority) }}>
                  {ticket.priority}
                </strong></span>
                <span>#{ticket.id}</span>
              </div>
              
              {ticket.last_message && (
                <p style={{
                  margin: "12px 0 0 0",
                  padding: "8px 12px",
                  backgroundColor: "#f5f5f5",
                  borderRadius: "6px",
                  fontSize: "13px",
                  color: "#444",
                }}>
                  "{ticket.last_message}..."
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 6.2 Create the individual ticket view page

**File to create:** `apps/web/app/admin/support/[id]/page.tsx`

```tsx
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface Message {
  id: number;
  sender_type: string;
  sender_name: string;
  content: string;
  created_at: string;
}

interface Ticket {
  id: number;
  user_id: number;
  status: string;
  priority: string;
  escalation_reason: string;
  escalation_trigger: string;
  user_snapshot: {
    name: string;
    email: string;
    title?: string;
    location?: string;
  };
  pre_escalation_context: Array<{ role: string; content: string }>;
  created_at: string;
  agent_joined_at: string | null;
  resolved_at: string | null;
  resolution_summary: string | null;
  resolution_category: string | null;
}

export default function AdminTicketPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const ticketId = Number(params.id);
  const adminToken = searchParams.get("token") || localStorage.getItem("winnow_admin_token") || "";

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [resolutionSummary, setResolutionSummary] = useState("");
  const [resolutionCategory, setResolutionCategory] = useState("general");
  const [addToKB, setAddToKB] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchTicket = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/support/admin/tickets/${ticketId}`, {
        headers: { "X-Admin-Token": adminToken },
      });
      
      if (res.ok) {
        const data = await res.json();
        setTicket(data.ticket);
        setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to fetch ticket:", error);
    } finally {
      setLoading(false);
    }
  }, [ticketId, adminToken]);

  const connectWebSocket = useCallback(() => {
    const wsUrl = `${API_BASE.replace("http", "ws")}/ws/support/${ticketId}?token=${adminToken}&role=admin`;
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "message") {
          setMessages((prev) => [...prev, data]);
          scrollToBottom();
        }
      } catch (e) {
        console.error("WebSocket parse error:", e);
      }
    };
    
    ws.onclose = () => {
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000);
    };
    
    wsRef.current = ws;
  }, [ticketId, adminToken]);

  useEffect(() => {
    fetchTicket();
    connectWebSocket();
    
    return () => {
      wsRef.current?.close();
    };
  }, [fetchTicket, connectWebSocket]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const joinTicket = async () => {
    try {
      await fetch(`${API_BASE}/api/support/admin/tickets/${ticketId}/join`, {
        method: "POST",
        headers: { "X-Admin-Token": adminToken },
      });
      fetchTicket();
    } catch (error) {
      console.error("Failed to join ticket:", error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    
    setSending(true);
    
    try {
      // Send via WebSocket if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "message",
          content: input.trim(),
        }));
      } else {
        // Fallback to REST
        await fetch(`${API_BASE}/api/support/admin/tickets/${ticketId}/reply`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Token": adminToken,
          },
          body: JSON.stringify({ content: input.trim() }),
        });
        fetchTicket();
      }
      
      setInput("");
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setSending(false);
    }
  };

  const closeTicket = async () => {
    try {
      await fetch(`${API_BASE}/api/support/admin/tickets/${ticketId}/close`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Token": adminToken,
        },
        body: JSON.stringify({
          resolution_summary: resolutionSummary,
          resolution_category: resolutionCategory,
          add_to_knowledge_base: addToKB,
        }),
      });
      
      router.push("/admin/support");
    } catch (error) {
      console.error("Failed to close ticket:", error);
    }
  };

  if (loading) {
    return <div style={{ padding: "40px", textAlign: "center" }}>Loading...</div>;
  }

  if (!ticket) {
    return <div style={{ padding: "40px", textAlign: "center" }}>Ticket not found</div>;
  }

  return (
    <div style={{ 
      display: "flex", 
      height: "100vh", 
      backgroundColor: "#f5f5f5",
    }}>
      {/* Left sidebar - User info & context */}
      <div style={{
        width: "300px",
        backgroundColor: "white",
        borderRight: "1px solid #e0e0e0",
        padding: "20px",
        overflowY: "auto",
      }}>
        <button
          onClick={() => router.push("/admin/support")}
          style={{
            padding: "8px 16px",
            marginBottom: "20px",
            backgroundColor: "transparent",
            border: "1px solid #ddd",
            borderRadius: "6px",
            cursor: "pointer",
          }}
        >
          ← Back to Tickets
        </button>
        
        <h2 style={{ margin: "0 0 4px 0", color: "#1B3025" }}>
          {ticket.user_snapshot?.name || "Unknown User"}
        </h2>
        <p style={{ margin: "0 0 16px 0", color: "#666", fontSize: "14px" }}>
          {ticket.user_snapshot?.email}
        </p>
        
        <div style={{ marginBottom: "20px" }}>
          <span style={{
            padding: "4px 12px",
            borderRadius: "4px",
            backgroundColor: ticket.status === "waiting" ? "#fff3cd" : 
                           ticket.status === "active" ? "#d4edda" : "#d1ecf1",
            color: ticket.status === "waiting" ? "#856404" :
                   ticket.status === "active" ? "#155724" : "#0c5460",
            fontWeight: "bold",
            fontSize: "12px",
          }}>
            {ticket.status.toUpperCase()}
          </span>
        </div>
        
        <div style={{ fontSize: "13px", color: "#666", marginBottom: "20px" }}>
          <p><strong>Reason:</strong> {ticket.escalation_reason}</p>
          <p><strong>Priority:</strong> {ticket.priority}</p>
          <p><strong>Created:</strong> {new Date(ticket.created_at).toLocaleString()}</p>
          {ticket.user_snapshot?.title && (
            <p><strong>Title:</strong> {ticket.user_snapshot.title}</p>
          )}
        </div>
        
        {ticket.escalation_trigger && (
          <div style={{ marginBottom: "20px" }}>
            <h4 style={{ margin: "0 0 8px 0", color: "#1B3025" }}>Trigger Message</h4>
            <p style={{
              padding: "12px",
              backgroundColor: "#f9f9f9",
              borderRadius: "8px",
              fontSize: "13px",
              fontStyle: "italic",
            }}>
              "{ticket.escalation_trigger}"
            </p>
          </div>
        )}
        
        {ticket.pre_escalation_context && ticket.pre_escalation_context.length > 0 && (
          <div>
            <h4 style={{ margin: "0 0 8px 0", color: "#1B3025" }}>Pre-escalation Context</h4>
            <div style={{
              maxHeight: "200px",
              overflowY: "auto",
              backgroundColor: "#f9f9f9",
              borderRadius: "8px",
              padding: "12px",
            }}>
              {ticket.pre_escalation_context.map((msg, idx) => (
                <div key={idx} style={{
                  marginBottom: "8px",
                  fontSize: "12px",
                }}>
                  <strong>{msg.role === "user" ? "User" : "Sieve"}:</strong>
                  <p style={{ margin: "4px 0 0 0" }}>{msg.content}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {ticket.status !== "resolved" && (
          <button
            onClick={() => setShowCloseModal(true)}
            style={{
              width: "100%",
              marginTop: "20px",
              padding: "12px",
              backgroundColor: "#28a745",
              color: "white",
              border: "none",
              borderRadius: "6px",
              cursor: "pointer",
              fontWeight: "bold",
            }}
          >
            ✓ Resolve Ticket
          </button>
        )}
      </div>
      
      {/* Main chat area */}
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
      }}>
        {/* Messages */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px",
        }}>
          {/* Join prompt if waiting */}
          {ticket.status === "waiting" && (
            <div style={{
              textAlign: "center",
              padding: "40px",
              marginBottom: "20px",
            }}>
              <p style={{ color: "#666", marginBottom: "16px" }}>
                The user is waiting for you to join the conversation.
              </p>
              <button
                onClick={joinTicket}
                style={{
                  padding: "16px 32px",
                  backgroundColor: "#1B3025",
                  color: "#E8C84A",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "bold",
                  fontSize: "16px",
                }}
              >
                Join Conversation
              </button>
            </div>
          )}
          
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: "16px",
                display: "flex",
                justifyContent: msg.sender_type === "agent" ? "flex-end" : "flex-start",
              }}
            >
              <div style={{
                maxWidth: "70%",
                padding: "12px 16px",
                borderRadius: msg.sender_type === "agent" 
                  ? "18px 18px 4px 18px" 
                  : "18px 18px 18px 4px",
                backgroundColor: msg.sender_type === "agent" 
                  ? "#1B3025" 
                  : msg.sender_type === "system"
                    ? "#f0f0f0"
                    : "#E8C84A",
                color: msg.sender_type === "agent" ? "#E8C84A" : "#1B3025",
              }}>
                {msg.sender_type !== "system" && (
                  <div style={{ 
                    fontSize: "11px", 
                    opacity: 0.8, 
                    marginBottom: "4px",
                    fontWeight: "bold",
                  }}>
                    {msg.sender_name}
                  </div>
                )}
                <div style={{ 
                  fontSize: msg.sender_type === "system" ? "13px" : "14px",
                  fontStyle: msg.sender_type === "system" ? "italic" : "normal",
                }}>
                  {msg.content}
                </div>
                <div style={{ 
                  fontSize: "10px", 
                  opacity: 0.6, 
                  marginTop: "4px",
                  textAlign: "right",
                }}>
                  {new Date(msg.created_at).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input area */}
        {ticket.status !== "resolved" && (
          <div style={{
            padding: "16px",
            backgroundColor: "white",
            borderTop: "1px solid #e0e0e0",
            display: "flex",
            gap: "12px",
          }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
              placeholder="Type your response..."
              style={{
                flex: 1,
                padding: "12px 16px",
                borderRadius: "24px",
                border: "1px solid #ddd",
                fontSize: "14px",
                outline: "none",
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || sending}
              style={{
                padding: "12px 24px",
                backgroundColor: "#1B3025",
                color: "#E8C84A",
                border: "none",
                borderRadius: "24px",
                cursor: input.trim() && !sending ? "pointer" : "not-allowed",
                fontWeight: "bold",
                opacity: input.trim() && !sending ? 1 : 0.5,
              }}
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        )}
      </div>
      
      {/* Close ticket modal */}
      {showCloseModal && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: "white",
            padding: "32px",
            borderRadius: "12px",
            width: "100%",
            maxWidth: "500px",
          }}>
            <h2 style={{ margin: "0 0 20px 0", color: "#1B3025" }}>
              Resolve Ticket
            </h2>
            
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
                Category
              </label>
              <select
                value={resolutionCategory}
                onChange={(e) => setResolutionCategory(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  border: "1px solid #ddd",
                }}
              >
                <option value="general">General Support</option>
                <option value="billing">Billing</option>
                <option value="technical">Technical Issue</option>
                <option value="feature_request">Feature Request</option>
                <option value="account">Account Issue</option>
                <option value="matching">Job Matching</option>
                <option value="other">Other</option>
              </select>
            </div>
            
            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
                Resolution Summary
              </label>
              <textarea
                value={resolutionSummary}
                onChange={(e) => setResolutionSummary(e.target.value)}
                placeholder="Brief summary of how the issue was resolved..."
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  border: "1px solid #ddd",
                  minHeight: "100px",
                  resize: "vertical",
                }}
              />
            </div>
            
            <div style={{ marginBottom: "24px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={addToKB}
                  onChange={(e) => setAddToKB(e.target.checked)}
                />
                <span>Add this resolution to Sieve's knowledge base</span>
              </label>
              <p style={{ fontSize: "12px", color: "#666", marginTop: "4px", marginLeft: "24px" }}>
                If checked, Sieve will learn from this conversation and be able to handle similar questions automatically.
              </p>
            </div>
            
            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowCloseModal(false)}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "transparent",
                  border: "1px solid #ddd",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={closeTicket}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "#28a745",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontWeight: "bold",
                }}
              >
                Resolve & Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

# PART 7 — ENVIRONMENT VARIABLES

### 7.1 Add required environment variables

**File to modify:** `services/api/.env` (add these if not present)

```bash
# Admin contact for notifications
ADMIN_EMAIL=ron@winnowcc.com
ADMIN_PHONE=+1XXXXXXXXXX  # Your phone number for SMS

# Admin authentication
ADMIN_TOKEN=your-secure-admin-token-here  # Generate a strong random string

# App base URL (for links in notifications)
APP_BASE_URL=http://localhost:3000  # Change to production URL when deployed
```

**File to modify:** `services/api/.env.example` (add these)

```bash
# Live Agent Support
ADMIN_EMAIL=admin@example.com
ADMIN_PHONE=+1XXXXXXXXXX
ADMIN_TOKEN=generate-a-secure-token
APP_BASE_URL=http://localhost:3000
```

---

# PART 8 — KNOWLEDGE BASE LEARNING (OPTIONAL ENHANCEMENT)

When a ticket is resolved and "Add to knowledge base" is checked, the system can learn from the conversation to improve Sieve's responses.

### 8.1 Create the knowledge extraction service

**File to create:** `services/api/app/services/sieve_knowledge.py`

```python
"""
Sieve knowledge base learning service.
Extracts Q&A pairs from resolved support tickets to improve Sieve's responses.
"""
import os
import json
import logging

import anthropic
from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket, SupportMessage

logger = logging.getLogger(__name__)


async def extract_knowledge_from_ticket(ticket_id: int, db: Session) -> dict:
    """
    Use Claude to extract key learnings from a resolved support ticket.
    
    Returns:
        dict with:
        - question: The core question/issue
        - answer: The resolution that worked
        - category: Topic category
        - keywords: Search keywords
    """
    # Get ticket and messages
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        return {}
    
    messages = db.query(SupportMessage).filter(
        SupportMessage.ticket_id == ticket_id
    ).order_by(SupportMessage.created_at.asc()).all()
    
    # Build conversation transcript
    transcript = ""
    for msg in messages:
        if msg.sender_type in ["user", "agent"]:
            role = "User" if msg.sender_type == "user" else "Agent"
            transcript += f"{role}: {msg.content}\n\n"
    
    # Include pre-escalation context
    if ticket.pre_escalation_context:
        pre_context = "\n".join([
            f"{'User' if m.get('role') == 'user' else 'Sieve'}: {m.get('content', '')}"
            for m in ticket.pre_escalation_context
        ])
        transcript = f"[Previous Sieve conversation]\n{pre_context}\n\n[Escalated to live agent]\n{transcript}"
    
    try:
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="""You are extracting knowledge from a resolved support conversation.
            
Output a JSON object with:
- question: The core question or issue the user had (phrased as a question)
- answer: A clear, helpful answer that Sieve should give in the future
- category: One of: billing, technical, account, matching, feature, general
- keywords: Array of 3-5 keywords for search matching

Keep the answer concise but complete. Write it as if Sieve (an AI assistant) is responding.""",
            messages=[
                {
                    "role": "user",
                    "content": f"""Extract knowledge from this resolved support ticket:

Resolution category: {ticket.resolution_category}
Resolution summary: {ticket.resolution_summary}

Conversation:
{transcript}

Return only valid JSON."""
                }
            ],
        )
        
        result_text = response.content[0].text if response.content else "{}"
        
        # Parse JSON (handle potential markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
        
    except Exception as e:
        logger.error(f"Failed to extract knowledge from ticket {ticket_id}: {e}")
        return {}


# Future: Store extracted knowledge in a vector database for semantic search
# For now, you could store in a simple JSON file or database table
```

---

## Summary Checklist

### Database & Models
- [ ] `support_tickets` table created with all fields
- [ ] `support_messages` table created with all fields
- [ ] Models registered in `__init__.py`
- [ ] Alembic migration created and applied

### Backend Services
- [ ] `live_agent.py` created with escalation detection, ticket management
- [ ] `support_notifications.py` created with Email + SMS notification functions
- [ ] Business hours logic implemented (08:00-18:00 CST Mon-Sat)

### API Endpoints
- [ ] `POST /api/support/escalate` - User escalates to live agent
- [ ] `GET /api/support/ticket/active` - Get user's active ticket
- [ ] `POST /api/support/ticket/{id}/message` - User sends message
- [ ] `GET /api/support/admin/tickets` - Admin lists tickets
- [ ] `GET /api/support/admin/tickets/{id}` - Admin gets ticket details
- [ ] `POST /api/support/admin/tickets/{id}/join` - Admin joins ticket
- [ ] `POST /api/support/admin/tickets/{id}/reply` - Admin sends message
- [ ] `POST /api/support/admin/tickets/{id}/close` - Admin closes ticket

### WebSocket
- [ ] `/ws/support/{ticket_id}` - Real-time chat for users and admin
- [ ] `/ws/admin/tickets` - Admin notification feed (optional)

### Frontend - Sieve Widget Updates
- [ ] Live agent mode state added
- [ ] Escalation detection for trigger phrases
- [ ] WebSocket connection for real-time messaging
- [ ] Visual indicator for live agent mode
- [ ] Agent messages styled distinctly (gold background)

### Frontend - Admin Dashboard
- [ ] `/admin/support` - Ticket list page with filtering
- [ ] `/admin/support/[id]` - Individual ticket chat interface
- [ ] Ticket resolution modal with category and KB option
- [ ] Real-time message updates via WebSocket

### Notifications
- [ ] Email notification on new ticket (via Resend)
- [ ] SMS notification on new ticket (via Telnyx)
- [ ] Email transcript on ticket resolution

### Environment
- [ ] `ADMIN_EMAIL` configured
- [ ] `ADMIN_PHONE` configured
- [ ] `ADMIN_TOKEN` configured
- [ ] `APP_BASE_URL` configured

---

## Cost Estimate

| Component | Cost |
|-----------|------|
| PostgreSQL storage | $0 (existing) |
| Redis | $0 (existing) |
| WebSocket connections | $0 (Cloud Run) |
| Resend emails | ~$0.001/email |
| Telnyx SMS | ~$0.01/SMS |
| Claude API (KB extraction) | ~$0.003/ticket |
| **Estimated monthly** | **$1-5** |

---

## Testing Checklist

1. [ ] User requests "talk to a person" → Ticket created, notifications sent
2. [ ] Admin receives email with conversation context and link
3. [ ] Admin clicks link → Taken to ticket page
4. [ ] Admin joins ticket → User sees "Live Agent Connected"
5. [ ] Messages appear in real-time on both sides
6. [ ] Admin resolves ticket → User sees resolution message
7. [ ] Transcript email sent to admin
8. [ ] Outside business hours → User sees expected response time
9. [ ] User refreshes page → Existing ticket restored
10. [ ] Multiple tickets → Admin can switch between them

---

## Next Steps After Implementation

1. **Push Notifications** - Implement mobile push when the Expo app is ready
2. **Agent Availability Status** - Show if you're online/offline in the widget
3. **Canned Responses** - Quick-reply templates for common issues
4. **Analytics** - Track average response time, resolution time, satisfaction
5. **Multiple Agents** - Support for team members with role assignments
