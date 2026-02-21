"""Add employer usage counter columns.

Revision ID: 20260217_01
Revises: 20260216_02
Create Date: 2026-02-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20260217_01"
down_revision = "20260216_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employer_profiles",
        sa.Column(
            "ai_parsing_used", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("usage_reset_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employer_profiles", "usage_reset_at")
    op.drop_column("employer_profiles", "ai_parsing_used")
