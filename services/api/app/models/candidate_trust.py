from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidateTrust(Base):
    __tablename__ = "candidate_trust"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resume_documents.id"), unique=True, nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("allowed", "soft_quarantine", "hard_quarantine", name="trust_status"),
        nullable=False,
    )
    reasons: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
