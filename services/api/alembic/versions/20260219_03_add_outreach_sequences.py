"""Add outreach sequences and enrollments tables.

Revision ID: 20260219_03
Revises: 20260219_02
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260219_03"
down_revision = "20260219_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach_sequences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recruiter_job_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("steps", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "outreach_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sequence_id",
            sa.Integer(),
            sa.ForeignKey("outreach_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_candidate_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_pipeline_candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_step", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "sequence_id",
            "pipeline_candidate_id",
            name="uq_enrollment_seq_candidate",
        ),
    )

    op.create_index(
        "ix_enrollment_status_next_send",
        "outreach_enrollments",
        ["status", "next_send_at"],
    )
    op.create_index(
        "ix_enrollment_recruiter",
        "outreach_enrollments",
        ["recruiter_profile_id"],
    )

    # Add outreach counter to recruiter_profiles
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "outreach_enrollments_used",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "outreach_enrollments_used")
    op.drop_index("ix_enrollment_recruiter", table_name="outreach_enrollments")
    op.drop_index("ix_enrollment_status_next_send", table_name="outreach_enrollments")
    op.drop_table("outreach_enrollments")
    op.drop_table("outreach_sequences")
