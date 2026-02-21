"""Add employer_job_candidates cache table.

Pre-computed candidate matches for employer jobs. Populated by background
workers when jobs are created/activated or candidate profiles change.

Revision ID: 20260211_03
Revises: 20260211_02
Create Date: 2026-02-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "20260211_03"
down_revision = "20260211_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employer_job_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="CASCADE"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employer_job_id",
            "candidate_profile_id",
            name="uq_employer_job_candidate",
        ),
    )
    op.create_index(
        "ix_ejc_job_score",
        "employer_job_candidates",
        ["employer_job_id", sa.text("match_score DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ejc_job_score", table_name="employer_job_candidates")
    op.drop_table("employer_job_candidates")
