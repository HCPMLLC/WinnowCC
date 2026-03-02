"""add auth_events table and lockout columns to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 14:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- auth_events table ---
    op.create_table(
        "auth_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_events_email", "auth_events", ["email"])
    op.create_index("ix_auth_events_ip_address", "auth_events", ["ip_address"])
    op.create_index("ix_auth_events_created_at", "auth_events", ["created_at"])

    # --- Lockout columns on users ---
    op.add_column(
        "users",
        sa.Column("account_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("account_lock_reason", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_window_start",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "failed_login_window_start")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "account_lock_reason")
    op.drop_column("users", "account_locked_at")
    op.drop_index("ix_auth_events_created_at", table_name="auth_events")
    op.drop_index("ix_auth_events_ip_address", table_name="auth_events")
    op.drop_index("ix_auth_events_email", table_name="auth_events")
    op.drop_table("auth_events")
