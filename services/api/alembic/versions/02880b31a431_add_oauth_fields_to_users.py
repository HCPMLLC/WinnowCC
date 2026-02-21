"""Add OAuth fields to users

Revision ID: 02880b31a431
Revises: 7e681a4cfd1d
Create Date: 2026-02-03 13:54:34.575810

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02880b31a431"
down_revision: str | None = "7e681a4cfd1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add OAuth fields to users table
    op.add_column(
        "users", sa.Column("oauth_provider", sa.String(length=50), nullable=True)
    )
    op.add_column("users", sa.Column("oauth_sub", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "oauth_sub")
    op.drop_column("users", "oauth_provider")
