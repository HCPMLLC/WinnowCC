"""Add career intelligence and migration tables.

Six new tables: recruiter_candidate_briefs, market_intel,
time_to_fill_predictions, career_trajectories, migration_jobs,
migration_entity_map.

Revision ID: 20260211_04
Revises: 20260211_03
Create Date: 2026-02-11
"""

import sqlalchemy as sa

from alembic import op

revision = "20260211_04"
down_revision = "20260211_03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recruiter_candidate_briefs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "candidate_profile_id",
            sa.Integer,
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employer_job_id",
            sa.Integer,
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generated_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("brief_type", sa.String(50), nullable=False),
        sa.Column("brief_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("brief_text", sa.Text, nullable=False),
        sa.Column("model_used", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_briefs_candidate_job",
        "recruiter_candidate_briefs",
        ["candidate_profile_id", "employer_job_id"],
    )

    op.create_table(
        "market_intel",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scope_type", sa.String(50), nullable=False),
        sa.Column("scope_key", sa.String(255), nullable=False),
        sa.Column("data_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("sample_size", sa.Integer),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("scope_type", "scope_key", name="uq_market_intel_scope"),
    )

    op.create_table(
        "time_to_fill_predictions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_job_id",
            sa.Integer,
            sa.ForeignKey("employer_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("predicted_days", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2)),
        sa.Column("factors_json", sa.dialects.postgresql.JSONB),
        sa.Column("actual_days", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_ttf_employer_job_id",
        "time_to_fill_predictions",
        ["employer_job_id"],
    )

    op.create_table(
        "career_trajectories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "candidate_profile_id",
            sa.Integer,
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trajectory_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("model_used", sa.String(100)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "migration_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_platform", sa.String(50), nullable=False),
        sa.Column("source_platform_detected", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("config_json", sa.dialects.postgresql.JSONB),
        sa.Column("stats_json", sa.dialects.postgresql.JSONB),
        sa.Column("error_log", sa.dialects.postgresql.JSONB),
        sa.Column("source_file_path", sa.String(500), nullable=True),
        sa.Column("api_credentials_encrypted", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "migration_entity_map",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "migration_job_id",
            sa.Integer,
            sa.ForeignKey("migration_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_entity_type", sa.String(50), nullable=False),
        sa.Column("source_entity_id", sa.String(255), nullable=False),
        sa.Column("winnow_entity_type", sa.String(50), nullable=False),
        sa.Column("winnow_entity_id", sa.Integer),
        sa.Column("parent_source_id", sa.String(255), nullable=True),
        sa.Column("raw_data", sa.dialects.postgresql.JSONB),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_entity_map_job_type_id",
        "migration_entity_map",
        ["migration_job_id", "source_entity_type", "source_entity_id"],
    )


def downgrade():
    op.drop_index("idx_entity_map_job_type_id")
    op.drop_table("migration_entity_map")
    op.drop_table("migration_jobs")
    op.drop_table("career_trajectories")
    op.drop_index("idx_ttf_employer_job_id")
    op.drop_table("time_to_fill_predictions")
    op.drop_table("market_intel")
    op.drop_index("idx_briefs_candidate_job")
    op.drop_table("recruiter_candidate_briefs")
