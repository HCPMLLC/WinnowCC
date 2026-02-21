"""add stripe billing columns and usage_counters table

Revision ID: 20260207_02
Revises: e1e14d06cf9d
Create Date: 2026-02-07 20:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "20260207_02"
down_revision = "e1e14d06cf9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stripe columns on candidate table
    op.add_column(
        "candidate",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "candidate",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "candidate",
        sa.Column("subscription_status", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_candidate_stripe_customer_id",
        "candidate",
        ["stripe_customer_id"],
        unique=True,
    )

    # Usage counters table
    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("match_refreshes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tailor_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "period_start", name="uq_usage_user_period"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_index("ix_candidate_stripe_customer_id", table_name="candidate")
    op.drop_column("candidate", "subscription_status")
    op.drop_column("candidate", "stripe_subscription_id")
    op.drop_column("candidate", "stripe_customer_id")
