"""add jobs, matches, tailored_resumes tables

Revision ID: 20260129_01
Revises: 20260127_01
Create Date: 2026-01-29 12:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260129_01"
down_revision = "20260127_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_job_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column(
            "remote_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hiring_manager_name", sa.String(length=255), nullable=True),
        sa.Column("hiring_manager_email", sa.String(length=255), nullable=True),
        sa.Column("hiring_manager_phone", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"], unique=False)

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("interview_readiness_score", sa.Integer(), nullable=False),
        sa.Column("offer_probability", sa.Integer(), nullable=False),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_matches_user_id", "matches", ["user_id"], unique=False)

    op.create_table(
        "tailored_resumes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("docx_url", sa.String(length=1000), nullable=False),
        sa.Column("cover_letter_url", sa.String(length=1000), nullable=False),
        sa.Column(
            "change_log",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_tailored_resumes_user_id", "tailored_resumes", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tailored_resumes_user_id", table_name="tailored_resumes")
    op.drop_table("tailored_resumes")
    op.drop_index("ix_matches_user_id", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_jobs_content_hash", table_name="jobs")
    op.drop_table("jobs")
