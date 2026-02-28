from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TailoredResume(Base):
    __tablename__ = "tailored_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    docx_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    cover_letter_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    change_log: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Snapshot fields — preserve job context after the job is purged
    job_title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_company_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
