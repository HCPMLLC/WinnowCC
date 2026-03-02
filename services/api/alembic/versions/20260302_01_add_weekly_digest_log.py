"""Add weekly_digest_logs table for personalized weekly email digests.

Revision ID: 20260302_01
Revises: 20260228_01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260302_01"
down_revision = "20260228_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_digest_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer,
            sa.ForeignKey("candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("digest_json", sa.JSON, nullable=True),
        sa.Column("summary_text", sa.Text, nullable=True),
        sa.Column(
            "hidden_gem_job_id",
            sa.Integer,
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email_id", sa.String(100), nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("week_end", sa.Date, nullable=False),
    )
    op.create_index(
        "ix_weekly_digest_logs_candidate_id",
        "weekly_digest_logs",
        ["candidate_id"],
    )
    op.create_index(
        "uq_weekly_digest_candidate_week",
        "weekly_digest_logs",
        ["candidate_id", "week_start"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_weekly_digest_candidate_week", table_name="weekly_digest_logs")
    op.drop_index("ix_weekly_digest_logs_candidate_id", table_name="weekly_digest_logs")
    op.drop_table("weekly_digest_logs")
