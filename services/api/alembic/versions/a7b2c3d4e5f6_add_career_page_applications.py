"""Add career page applications table

Revision ID: a7b2c3d4e5f6
Revises: 33d784d78434
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a7b2c3d4e5f6"
down_revision = "33d784d78434"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_page_applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "career_page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("career_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidate.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "session_token",
            sa.String(64),
            unique=True,
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="started",
        ),
        sa.Column(
            "completeness_score",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "missing_fields",
            postgresql.JSONB(),
            server_default="[]",
        ),
        sa.Column(
            "conversation_history",
            postgresql.JSONB(),
            server_default="[]",
        ),
        sa.Column(
            "resume_file_url", sa.String(500), nullable=True
        ),
        sa.Column(
            "resume_parsed_data",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "question_responses",
            postgresql.JSONB(),
            server_default="{}",
        ),
        sa.Column(
            "cross_job_recommendations",
            postgresql.JSONB(),
            server_default="[]",
        ),
        sa.Column(
            "additional_applications",
            postgresql.ARRAY(sa.Integer()),
            server_default="{}",
        ),
        sa.Column("ips_score", sa.Integer(), nullable=True),
        sa.Column(
            "ips_breakdown", postgresql.JSONB(), nullable=True
        ),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column(
            "utm_params", postgresql.JSONB(), nullable=True
        ),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_activity_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "career_page_id",
            "job_id",
            "email",
            name="uq_career_page_application_email_job",
        ),
    )

    op.create_index(
        "ix_career_page_applications_session",
        "career_page_applications",
        ["session_token"],
    )
    op.create_index(
        "ix_career_page_applications_email",
        "career_page_applications",
        ["email"],
    )
    op.create_index(
        "ix_career_page_applications_status",
        "career_page_applications",
        ["status"],
    )
    op.create_index(
        "ix_career_page_applications_job",
        "career_page_applications",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_table("career_page_applications")
