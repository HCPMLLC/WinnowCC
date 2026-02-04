"""add description_html to jobs

Revision ID: 20260204_01
Revises: 20260201_02
Create Date: 2026-02-04 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260204_01"
down_revision = "02880b31a431"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("description_html", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "description_html")
