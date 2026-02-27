"""Add auto_populate_pipeline to recruiter_profiles

Revision ID: 20260217_04
Revises: 20260217_03
Create Date: 2026-02-17
"""

import sqlalchemy as sa

from alembic import op

revision = "20260217_04"
down_revision = "20260217_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "auto_populate_pipeline",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "auto_populate_pipeline")
