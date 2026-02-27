"""Add employer_introduction_requests table and intro_requests_used counter.

Revision ID: 20260219_02
Revises: 20260219_01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260219_02"
down_revision = "20260219_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_introduction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employer_profile_id",
            sa.Integer(),
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("candidate_response_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_emp_intro_employer_status",
        "employer_introduction_requests",
        ["employer_profile_id", "status"],
    )
    op.create_index(
        "ix_emp_intro_candidate_status",
        "employer_introduction_requests",
        ["candidate_profile_id", "status"],
    )

    # Add monthly intro counter to employer_profiles
    op.add_column(
        "employer_profiles",
        sa.Column(
            "intro_requests_used", sa.Integer(), server_default="0", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("employer_profiles", "intro_requests_used")
    op.drop_index(
        "ix_emp_intro_candidate_status", table_name="employer_introduction_requests"
    )
    op.drop_index(
        "ix_emp_intro_employer_status", table_name="employer_introduction_requests"
    )
    op.drop_table("employer_introduction_requests")
