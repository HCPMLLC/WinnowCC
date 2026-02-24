"""Recruiter profile and team member models."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecruiterProfile(Base):
    """Recruiter/staffing agency profile with subscription and usage tracking."""

    __tablename__ = "recruiter_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Company info
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    specializations: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Subscription
    subscription_tier: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="trial"
    )
    subscription_status: Mapped[str | None] = mapped_column(
        String(50), server_default="trialing"
    )
    billing_interval: Mapped[str | None] = mapped_column(
        String(20), server_default="monthly"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Billing exemption (admin override — immune to Stripe webhook changes)
    billing_exempt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    # Trial tracking
    trial_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Seat management
    seats_purchased: Mapped[int] = mapped_column(Integer, server_default="1")
    seats_used: Mapped[int] = mapped_column(Integer, server_default="1")

    # Usage counters
    candidate_briefs_used: Mapped[int] = mapped_column(Integer, server_default="0")
    salary_lookups_used: Mapped[int] = mapped_column(Integer, server_default="0")
    job_uploads_used: Mapped[int] = mapped_column(Integer, server_default="0")
    intro_requests_used: Mapped[int] = mapped_column(Integer, server_default="0")
    resume_imports_used: Mapped[int] = mapped_column(Integer, server_default="0")
    outreach_enrollments_used: Mapped[int] = mapped_column(Integer, server_default="0")
    usage_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Pipeline settings
    auto_populate_pipeline: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="recruiter_profile")
    team_members = relationship(
        "RecruiterTeamMember",
        back_populates="recruiter_profile",
        cascade="all, delete-orphan",
    )
    jobs = relationship(
        "RecruiterJob",
        back_populates="recruiter_profile",
        cascade="all, delete-orphan",
    )
    clients = relationship(
        "RecruiterClient",
        back_populates="recruiter_profile",
        cascade="all, delete-orphan",
    )
    pipeline_candidates = relationship(
        "RecruiterPipelineCandidate",
        back_populates="recruiter_profile",
        cascade="all, delete-orphan",
    )
    activities = relationship(
        "RecruiterActivity",
        back_populates="recruiter_profile",
        cascade="all, delete-orphan",
    )

    @property
    def is_trial_active(self) -> bool:
        if self.subscription_tier != "trial":
            return False
        if not self.trial_ends_at:
            return False
        return datetime.now(timezone.utc) < self.trial_ends_at

    @property
    def trial_days_remaining(self) -> int:
        if not self.trial_ends_at:
            return 0
        delta = self.trial_ends_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    def start_trial(self) -> None:
        now = datetime.now(timezone.utc)
        self.subscription_tier = "trial"
        self.subscription_status = "trialing"
        self.trial_started_at = now
        self.trial_ends_at = now + timedelta(days=14)


class RecruiterTeamMember(Base):
    """Team member under a recruiter profile (for team/agency plans)."""

    __tablename__ = "recruiter_team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str | None] = mapped_column(String(50), server_default="member")
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    recruiter_profile = relationship("RecruiterProfile", back_populates="team_members")
    user = relationship("User")
