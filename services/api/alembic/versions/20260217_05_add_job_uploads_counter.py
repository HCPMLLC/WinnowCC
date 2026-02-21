"""Add job_uploads_used counter to recruiter_profiles

Revision ID: 20260217_05
Revises: 20260217_04
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260217_05"
down_revision = "20260217_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "job_uploads_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "job_uploads_used")
