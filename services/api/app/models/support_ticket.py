"""Support ticket model for live agent escalations.

Tracks conversations that have been escalated from Sieve AI to human support.
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class TicketStatus(str, enum.Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Who created the ticket
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user = relationship("User", foreign_keys=[user_id])

    # Ticket metadata
    status = Column(String(20), default=TicketStatus.WAITING.value, nullable=False, index=True)
    priority = Column(String(20), default=TicketPriority.NORMAL.value, nullable=False)

    # Escalation reason
    escalation_reason = Column(String(50), nullable=False)
    escalation_trigger = Column(Text, nullable=True)

    # Context from the Sieve conversation before escalation
    pre_escalation_context = Column(JSONB, nullable=True)

    # User info snapshot (in case profile changes)
    user_snapshot = Column(JSONB, nullable=True)

    # Resolution
    resolution_summary = Column(Text, nullable=True)
    resolution_category = Column(String(100), nullable=True)
    add_to_knowledge_base = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    agent_joined_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    messages = relationship(
        "SupportMessage", back_populates="ticket", cascade="all, delete-orphan"
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    ticket_id = Column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket = relationship("SupportTicket", back_populates="messages")

    # Who sent it
    sender_type = Column(String(20), nullable=False)  # "user", "agent", "system"
    sender_id = Column(Integer, nullable=True)
    sender_name = Column(String(100), nullable=True)

    # Message content
    content = Column(Text, nullable=False)

    # Metadata
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    read_at = Column(DateTime(timezone=True), nullable=True)
