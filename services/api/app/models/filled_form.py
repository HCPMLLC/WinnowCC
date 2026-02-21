"""FilledForm model — candidate-specific filled form instances."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FilledForm(Base):
    __tablename__ = "filled_forms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_form_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_forms.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    match_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    filled_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    unfilled_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gaps_detected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_storage_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    output_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="docx"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
