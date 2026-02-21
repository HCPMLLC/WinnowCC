"""Add recruiter CRM tables: clients, pipeline candidates, activities; extend recruiter_jobs.

Revision ID: 20260216_02
Revises: 20260216_01
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260216_02"
down_revision = "20260216_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- recruiter_clients ---
    op.create_table(
        "recruiter_clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=True),
        sa.Column("company_size", sa.String(50), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("contact_title", sa.String(255), nullable=True),
        sa.Column("contract_type", sa.String(50), nullable=True),
        sa.Column("fee_percentage", sa.Float(), nullable=True),
        sa.Column("flat_fee", sa.Integer(), nullable=True),
        sa.Column("contract_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contract_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_recruiter_clients_profile_id",
        "recruiter_clients",
        ["recruiter_profile_id"],
    )

    # --- recruiter_pipeline_candidates ---
    op.create_table(
        "recruiter_pipeline_candidates",
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
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_name", sa.String(255), nullable=True),
        sa.Column("external_email", sa.String(255), nullable=True),
        sa.Column("external_phone", sa.String(50), nullable=True),
        sa.Column("external_linkedin", sa.String(500), nullable=True),
        sa.Column("external_resume_url", sa.String(500), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("stage", sa.String(50), server_default="sourced"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("outreach_count", sa.Integer(), server_default="0"),
        sa.Column("last_outreach_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_recruiter_pipeline_profile_id",
        "recruiter_pipeline_candidates",
        ["recruiter_profile_id"],
    )
    op.create_index(
        "idx_recruiter_pipeline_stage",
        "recruiter_pipeline_candidates",
        ["stage"],
    )
    op.create_index(
        "idx_recruiter_pipeline_job_id",
        "recruiter_pipeline_candidates",
        ["recruiter_job_id"],
    )

    # --- recruiter_activities ---
    op.create_table(
        "recruiter_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "pipeline_candidate_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_pipeline_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recruiter_job_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_recruiter_activities_profile_id",
        "recruiter_activities",
        ["recruiter_profile_id"],
    )
    op.create_index(
        "idx_recruiter_activities_created_at",
        "recruiter_activities",
        ["created_at"],
    )

    # --- ALTER recruiter_jobs: add CRM columns ---
    op.add_column(
        "recruiter_jobs",
        sa.Column(
            "client_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "recruiter_jobs",
        sa.Column("priority", sa.String(20), server_default="normal"),
    )
    op.add_column(
        "recruiter_jobs",
        sa.Column("positions_to_fill", sa.Integer(), server_default="1"),
    )
    op.add_column(
        "recruiter_jobs",
        sa.Column("positions_filled", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "recruiter_jobs",
        sa.Column("department", sa.String(100), nullable=True),
    )
    op.add_column(
        "recruiter_jobs",
        sa.Column(
            "assigned_to_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recruiter_jobs", "assigned_to_user_id")
    op.drop_column("recruiter_jobs", "department")
    op.drop_column("recruiter_jobs", "positions_filled")
    op.drop_column("recruiter_jobs", "positions_to_fill")
    op.drop_column("recruiter_jobs", "priority")
    op.drop_column("recruiter_jobs", "client_id")

    op.drop_index("idx_recruiter_activities_created_at")
    op.drop_index("idx_recruiter_activities_profile_id")
    op.drop_table("recruiter_activities")

    op.drop_index("idx_recruiter_pipeline_job_id")
    op.drop_index("idx_recruiter_pipeline_stage")
    op.drop_index("idx_recruiter_pipeline_profile_id")
    op.drop_table("recruiter_pipeline_candidates")

    op.drop_index("idx_recruiter_clients_profile_id")
    op.drop_table("recruiter_clients")
