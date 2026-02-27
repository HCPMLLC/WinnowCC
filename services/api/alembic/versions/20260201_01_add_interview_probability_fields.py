"""add interview probability fields to matches

Revision ID: 20260201_01
Revises: 0a348886fd05
Create Date: 2026-02-01 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "20260201_01"
down_revision = "0a348886fd05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("resume_score", sa.Integer(), nullable=True))
    op.add_column(
        "matches", sa.Column("cover_letter_score", sa.Integer(), nullable=True)
    )
    op.add_column(
        "matches", sa.Column("application_logistics_score", sa.Integer(), nullable=True)
    )
    op.add_column(
        "matches",
        sa.Column(
            "referred", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "matches", sa.Column("interview_probability", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("matches", "interview_probability")
    op.drop_column("matches", "referred")
    op.drop_column("matches", "application_logistics_score")
    op.drop_column("matches", "cover_letter_score")
    op.drop_column("matches", "resume_score")
