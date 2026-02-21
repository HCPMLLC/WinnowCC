"""Migration models — track data imports from competing platforms."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MigrationJob(Base):
    """Top-level migration job tracking an import from a competing platform."""

    __tablename__ = "migration_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    source_platform_detected: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    config_json: Mapped[dict | None] = mapped_column(JSONB)
    stats_json: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[dict | None] = mapped_column(JSONB)
    source_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MigrationEntityMap(Base):
    """Maps source entities to Winnow entities during migration."""

    __tablename__ = "migration_entity_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    migration_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("migration_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    winnow_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    winnow_entity_id: Mapped[int | None] = mapped_column(Integer)
    parent_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
