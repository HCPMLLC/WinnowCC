"""MergedPacket model — final merged PDF application packets."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MergedPacket(Base):
    __tablename__ = "merged_packets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    document_order: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    merged_pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    naming_convention: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
