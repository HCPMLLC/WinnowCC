"""create candidate_profiles and job_runs tables

Revision ID: 20260125_01
Revises: 20260124_01
Create Date: 2026-01-25 09:30:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260125_01"
down_revision = "20260124_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("resume_document_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_candidate_profiles_user_id_version",
        "candidate_profiles",
        ["user_id", "version"],
    )

    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("resume_document_id", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_index(
        "ix_candidate_profiles_user_id_version", table_name="candidate_profiles"
    )
    op.drop_table("candidate_profiles")
