from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'candidate'")
    )
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # MFA
    mfa_otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_otp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mfa_otp_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    mfa_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    mfa_delivery_method: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'email'")
    )

    # Password reset
    password_reset_token: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Profile
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # OAuth
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Back-references for ORM relationships declared on other models
    employer_profile = relationship(
        "EmployerProfile", back_populates="user", uselist=False
    )
    recruiter_profile = relationship(
        "RecruiterProfile", back_populates="user", uselist=False
    )
