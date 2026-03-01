"""add unsubscribe_token to outreach_enrollment

Revision ID: g1a2b3c4d5e6
Revises: f6ead5847f50
Create Date: 2026-03-01 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g1a2b3c4d5e6"
down_revision: str | None = "f6ead5847f50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add as nullable first, backfill, then make non-nullable
    op.add_column(
        "outreach_enrollments",
        sa.Column("unsubscribe_token", sa.String(64), nullable=True),
    )
    # Backfill existing rows with unique tokens
    op.execute(
        "UPDATE outreach_enrollments "
        "SET unsubscribe_token = md5(random()::text || id::text) "
        "WHERE unsubscribe_token IS NULL"
    )
    op.alter_column(
        "outreach_enrollments",
        "unsubscribe_token",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("outreach_enrollments", "unsubscribe_token")
