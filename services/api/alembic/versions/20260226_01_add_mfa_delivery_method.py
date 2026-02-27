"""Add mfa_delivery_method column to users table.

Revision ID: 20260226_01
Revises: 57d09d733d54
"""

from alembic import op  # noqa: I001
import sqlalchemy as sa

revision = "20260226_01"
down_revision = "57d09d733d54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_delivery_method",
            sa.String(10),
            nullable=False,
            server_default="email",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_delivery_method")
