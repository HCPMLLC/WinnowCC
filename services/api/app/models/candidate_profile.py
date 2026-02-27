from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector as _Vector

    _EmbeddingType = _Vector(384)
except ImportError:
    import sqlalchemy as _sa

    _EmbeddingType = _sa.JSON()

from app.db.base import Base


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume_document_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("resume_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    open_to_opportunities: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    profile_visibility: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding = mapped_column(_EmbeddingType, nullable=True)
    llm_parse_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # pending | running | succeeded | failed
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
