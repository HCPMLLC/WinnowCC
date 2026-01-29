from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrustAuditLog(Base):
    __tablename__ = "trust_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trust_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidate_trust.id"), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(
        Enum("system", "candidate", "admin", name="trust_actor_type"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    prev_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
