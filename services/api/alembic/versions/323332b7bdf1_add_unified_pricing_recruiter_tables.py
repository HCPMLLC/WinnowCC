"""add_unified_pricing_recruiter_tables

Revision ID: 323332b7bdf1
Revises: 20260214_03
Create Date: 2026-02-15 12:02:04.045975

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "323332b7bdf1"
down_revision: str | None = "20260214_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. Add billing_interval to candidate table ──
    op.add_column(
        "candidate",
        sa.Column("billing_interval", sa.String(20), server_default="monthly"),
    )

    # ── 2. Add new columns to employer_profiles ──
    op.add_column(
        "employer_profiles",
        sa.Column("billing_interval", sa.String(20), server_default="monthly"),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("candidate_views_used", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "employer_profiles",
        sa.Column(
            "candidate_views_reset_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("job_parses_used", sa.Integer(), server_default="0"),
    )

    # ── 3. Add sieve/semantic counters to usage_counters ──
    op.add_column(
        "usage_counters",
        sa.Column("sieve_messages", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "usage_counters",
        sa.Column(
            "semantic_searches", sa.Integer(), server_default="0", nullable=False
        ),
    )

    # ── 4. Create recruiter_profiles table ──
    op.create_table(
        "recruiter_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Company info
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_type", sa.String(50), nullable=True),
        sa.Column("company_website", sa.String(500), nullable=True),
        sa.Column("specializations", JSONB, nullable=True),
        # Subscription
        sa.Column(
            "subscription_tier",
            sa.String(50),
            nullable=False,
            server_default="trial",
        ),
        sa.Column("subscription_status", sa.String(50), server_default="trialing"),
        sa.Column("billing_interval", sa.String(20), server_default="monthly"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        # Trial tracking
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        # Seat management
        sa.Column("seats_purchased", sa.Integer(), server_default="1"),
        sa.Column("seats_used", sa.Integer(), server_default="1"),
        # Usage counters
        sa.Column("candidate_briefs_used", sa.Integer(), server_default="0"),
        sa.Column("salary_lookups_used", sa.Integer(), server_default="0"),
        sa.Column("usage_reset_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── 5. Create recruiter_team_members table ──
    op.create_table(
        "recruiter_team_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), server_default="member"),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 6. Indexes ──
    op.create_index(
        "idx_recruiter_profiles_stripe_customer",
        "recruiter_profiles",
        ["stripe_customer_id"],
    )
    op.create_index(
        "idx_recruiter_team_members_profile",
        "recruiter_team_members",
        ["recruiter_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_recruiter_team_members_profile")
    op.drop_index("idx_recruiter_profiles_stripe_customer")

    op.drop_table("recruiter_team_members")
    op.drop_table("recruiter_profiles")

    op.drop_column("usage_counters", "semantic_searches")
    op.drop_column("usage_counters", "sieve_messages")

    op.drop_column("employer_profiles", "job_parses_used")
    op.drop_column("employer_profiles", "candidate_views_reset_at")
    op.drop_column("employer_profiles", "candidate_views_used")
    op.drop_column("employer_profiles", "billing_interval")

    op.drop_column("candidate", "billing_interval")
