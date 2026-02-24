"""Recruiter client company model."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterClient(Base):
    """Client company managed by a recruiter."""

    __tablename__ = "recruiter_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Legacy single-contact columns (kept for backward compat)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Multi-contact array [{name, email, phone, role}, ...]
    contacts: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Contract terms
    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fee_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    flat_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contract_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), server_default="active")

    # Hierarchy & contract vehicle
    parent_client_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recruiter_clients.id", ondelete="SET NULL"), nullable=True
    )
    contract_vehicle: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    recruiter_profile = relationship("RecruiterProfile", back_populates="clients")
    jobs = relationship("RecruiterJob", back_populates="client")
    parent = relationship(
        "RecruiterClient", remote_side=[id], back_populates="children"
    )
    children = relationship("RecruiterClient", back_populates="parent")
