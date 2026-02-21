"""add_job_parsed_details

Revision ID: e1e14d06cf9d
Revises: 20260204_01
Create Date: 2026-02-07 08:53:35.961222

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1e14d06cf9d"
down_revision: str | None = "20260204_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- Create job_parsed_details table --
    op.create_table(
        "job_parsed_details",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Title / Role
        sa.Column("normalized_title", sa.String(255), nullable=True),
        sa.Column("seniority_level", sa.String(50), nullable=True),
        sa.Column("employment_type", sa.String(50), nullable=True),
        sa.Column("estimated_duration_months", sa.Integer(), nullable=True),
        # Location
        sa.Column("parsed_city", sa.String(100), nullable=True),
        sa.Column("parsed_state", sa.String(100), nullable=True),
        sa.Column("parsed_country", sa.String(100), nullable=True),
        sa.Column("work_mode", sa.String(30), nullable=True),
        sa.Column("travel_percent", sa.Integer(), nullable=True),
        sa.Column("relocation_offered", sa.Boolean(), nullable=True),
        # Compensation
        sa.Column("parsed_salary_min", sa.Integer(), nullable=True),
        sa.Column("parsed_salary_max", sa.Integer(), nullable=True),
        sa.Column("parsed_salary_currency", sa.String(10), nullable=True),
        sa.Column("parsed_salary_type", sa.String(20), nullable=True),
        sa.Column("salary_confidence", sa.String(20), nullable=True),
        sa.Column("benefits_mentioned", postgresql.JSONB(), nullable=True),
        # Requirements
        sa.Column("required_skills", postgresql.JSONB(), nullable=True),
        sa.Column("preferred_skills", postgresql.JSONB(), nullable=True),
        sa.Column("required_certifications", postgresql.JSONB(), nullable=True),
        sa.Column("required_education", postgresql.JSONB(), nullable=True),
        sa.Column("years_experience_min", sa.Integer(), nullable=True),
        sa.Column("years_experience_max", sa.Integer(), nullable=True),
        sa.Column("tools_and_technologies", postgresql.JSONB(), nullable=True),
        sa.Column("raw_responsibilities", postgresql.JSONB(), nullable=True),
        sa.Column("raw_qualifications", postgresql.JSONB(), nullable=True),
        # Company Intelligence
        sa.Column("inferred_industry", sa.String(100), nullable=True),
        sa.Column("company_size_signal", sa.String(50), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("reports_to", sa.String(100), nullable=True),
        sa.Column("team_size", sa.String(50), nullable=True),
        # Quality & Fraud
        sa.Column("posting_quality_score", sa.Integer(), nullable=True),
        sa.Column("fraud_score", sa.Integer(), nullable=True, default=0),
        sa.Column("is_likely_fraudulent", sa.Boolean(), nullable=True, default=False),
        sa.Column("red_flags", postgresql.JSONB(), nullable=True),
        # Dedup
        sa.Column("is_duplicate_of_job_id", sa.Integer(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=True, default=False),
        # Meta
        sa.Column("parse_version", sa.Integer(), nullable=False, default=1),
        sa.Column(
            "parsed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_jpd_job_id", "job_parsed_details", ["job_id"], unique=True)
    op.create_index("ix_jpd_fraud_score", "job_parsed_details", ["fraud_score"])
    op.create_index(
        "ix_jpd_quality_score", "job_parsed_details", ["posting_quality_score"]
    )

    # -- Add columns to jobs table --
    op.add_column(
        "jobs",
        sa.Column(
            "is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")
        ),
    )
    op.add_column("jobs", sa.Column("dedup_group_id", sa.String(64), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "last_seen_at")
    op.drop_column("jobs", "first_seen_at")
    op.drop_column("jobs", "dedup_group_id")
    op.drop_column("jobs", "is_active")
    op.drop_index("ix_jpd_quality_score", table_name="job_parsed_details")
    op.drop_index("ix_jpd_fraud_score", table_name="job_parsed_details")
    op.drop_index("ix_jpd_job_id", table_name="job_parsed_details")
    op.drop_table("job_parsed_details")
