"""Add MFA columns to users table.

Revision ID: 20260219_01
Revises: 20260218_03
"""

from alembic import op  # noqa: I001
import sqlalchemy as sa

revision = "20260219_01"
down_revision = "20260218_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_otp_hash", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("mfa_otp_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("mfa_otp_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("mfa_required", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Backfill: require MFA for existing employers and recruiters
    op.execute(
        "UPDATE users SET mfa_required = true WHERE role IN ('employer', 'recruiter')"
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_required")
    op.drop_column("users", "mfa_otp_attempts")
    op.drop_column("users", "mfa_otp_expires_at")
    op.drop_column("users", "mfa_otp_hash")
