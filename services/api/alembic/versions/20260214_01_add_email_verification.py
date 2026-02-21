"""Add email verification columns to users table.

Revision ID: 20260214_01
Revises: 20260211_04
Create Date: 2026-02-14
"""

import sqlalchemy as sa

from alembic import op

revision = "20260214_01"
down_revision = "20260211_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verification_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_unique_constraint(
        "uq_users_email_verification_token", "users", ["email_verification_token"]
    )

    # Backfill: mark all existing users as verified (they proved engagement)
    op.execute("UPDATE users SET email_verified_at = created_at")


def downgrade() -> None:
    op.drop_constraint("uq_users_email_verification_token", "users", type_="unique")
    op.drop_column("users", "email_verification_expires_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified_at")
