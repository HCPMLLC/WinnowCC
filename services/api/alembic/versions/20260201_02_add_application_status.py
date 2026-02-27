"""add application_status to matches

Revision ID: 20260201_02
Revises: 20260201_01
Create Date: 2026-02-01 14:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "20260201_02"
down_revision = "20260201_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("application_status", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matches", "application_status")
