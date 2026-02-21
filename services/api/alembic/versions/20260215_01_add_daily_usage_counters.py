"""Add daily_usage_counters table for per-day billing enforcement.

Revision ID: 20260215_01
Revises: 20260214_03
Create Date: 2026-02-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20260215_01"
down_revision = "323332b7bdf1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("counter_name", sa.String(64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "counter_name", "date", name="uq_daily_user_counter_date"),
    )
    op.create_index(
        "ix_daily_usage_user_counter_date",
        "daily_usage_counters",
        ["user_id", "counter_name", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_usage_user_counter_date", table_name="daily_usage_counters")
    op.drop_table("daily_usage_counters")
