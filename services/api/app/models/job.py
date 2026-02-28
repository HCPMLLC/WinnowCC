from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector as _Vector

    _EmbeddingType = _Vector(384)
except ImportError:
    import sqlalchemy as _sa

    _EmbeddingType = _sa.JSON()

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    application_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hiring_manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hiring_manager_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hiring_manager_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding = mapped_column(_EmbeddingType, nullable=True)

    # Lifecycle columns (exist in DB via prior migrations)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    dedup_group_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
