"""Recruiter notification model for @mentions and team alerts."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterNotification(Base):
    """Notification for recruiter team collaboration."""

    __tablename__ = "recruiter_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activity_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("recruiter_activities.id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    recipient = relationship("User", foreign_keys=[recipient_user_id])
    sender = relationship("User", foreign_keys=[sender_user_id])
    activity = relationship("RecruiterActivity")
