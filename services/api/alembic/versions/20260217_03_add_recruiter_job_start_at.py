"""Add start_at to recruiter_jobs

Revision ID: 20260217_03
Revises: 20260217_02
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260217_03"
down_revision = "20260217_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_jobs",
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recruiter_jobs", "start_at")
