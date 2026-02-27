"""Add recruiter_jobs and recruiter_job_candidates tables.

Revision ID: 20260216_01
Revises: 323332b7bdf1
Create Date: 2026-02-16
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260216_01"
down_revision = "20260215_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recruiter_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("nice_to_haves", sa.Text(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("remote_policy", sa.String(50), nullable=True),
        sa.Column("employment_type", sa.String(50), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(10), server_default="USD"),
        sa.Column("client_company_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("application_url", sa.String(500), nullable=True),
        sa.Column("application_email", sa.String(255), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "recruiter_job_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_job_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("matched_skills", postgresql.JSONB(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "recruiter_job_id",
            "candidate_profile_id",
            name="uq_recruiter_job_candidate",
        ),
    )


def downgrade() -> None:
    op.drop_table("recruiter_job_candidates")
    op.drop_table("recruiter_jobs")
