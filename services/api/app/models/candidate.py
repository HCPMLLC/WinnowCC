from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_authorization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_job_types: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    desired_locations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    desired_salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    desired_salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    plan_billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alert_frequency: Mapped[str | None] = mapped_column(String(30), nullable=True)
    communication_channels: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    consent_terms: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    consent_privacy: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    consent_auto_renewal: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    consent_marketing: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    billing_interval: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
