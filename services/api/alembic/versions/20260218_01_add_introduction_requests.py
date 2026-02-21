"""Add introduction_requests table, open_to_introductions, intro_requests_used

Revision ID: 20260218_01
Revises: 20260217_05
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260218_01"
down_revision = "20260217_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "introduction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recruiter_job_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
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
        "ix_intro_req_candidate_status",
        "introduction_requests",
        ["candidate_profile_id", "status"],
    )
    op.create_index(
        "ix_intro_req_recruiter_status",
        "introduction_requests",
        ["recruiter_profile_id", "status"],
    )

    # Add open_to_introductions to candidate_profiles
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "open_to_introductions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Add intro_requests_used to recruiter_profiles
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "intro_requests_used",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_profiles", "intro_requests_used")
    op.drop_column("candidate_profiles", "open_to_introductions")
    op.drop_index("ix_intro_req_recruiter_status", "introduction_requests")
    op.drop_index("ix_intro_req_candidate_status", "introduction_requests")
    op.drop_table("introduction_requests")
