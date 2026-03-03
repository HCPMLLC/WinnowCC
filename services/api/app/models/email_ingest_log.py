"""EmailIngestLog model — tracks every email received at the ingest address.

Stores sender info, processing status, matched user, created job reference,
and parsing confidence for monitoring and debugging.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailIngestLog(Base):
    __tablename__ = "email_ingest_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sendgrid_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status: received → processing → parsed → draft_created | failed | ignored
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="received", index=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Attachment info
    attachment_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_content_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    attachment_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Linked records
    matched_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_employer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Parsing results
    parsing_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw metadata (headers, diagnostics)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<EmailIngestLog {self.id} from={self.sender_email} status={self.status}>"
        )
