"""Add resume_imports_used column to recruiter_profiles

Revision ID: 20260218_02
Revises: 20260218_01
Create Date: 2026-02-18
"""

import sqlalchemy as sa

from alembic import op

revision = "20260218_02"
down_revision = "20260218_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "resume_imports_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "resume_imports_used")
