"""Add parent hierarchy, contract vehicle, cross-segment
job linking, and candidate submissions.

Revision ID: 20260224_02
Revises: 955f2dae948a
Create Date: 2026-02-24
"""

import sqlalchemy as sa  # noqa: I001

from alembic import op

revision = "20260224_02"
down_revision = "955f2dae948a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1A: Parent/child hierarchy + contract vehicle on recruiter_clients
    op.add_column(
        "recruiter_clients",
        sa.Column(
            "parent_client_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "recruiter_clients",
        sa.Column("contract_vehicle", sa.String(255), nullable=True),
    )

    # Phase 1B: Parent/child hierarchy + contract vehicle on employer_profiles
    op.add_column(
        "employer_profiles",
        sa.Column(
            "parent_employer_id",
            sa.Integer(),
            sa.ForeignKey("employer_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("contract_vehicle", sa.String(255), nullable=True),
    )

    # Phase 2: Cross-segment job linking on recruiter_jobs
    op.add_column(
        "recruiter_jobs",
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Phase 3: Candidate submissions table
    op.create_table(
        "candidate_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column(
            "recruiter_profile_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_candidate_id",
            sa.Integer(),
            sa.ForeignKey("recruiter_pipeline_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_company_name", sa.String(255), nullable=True),
        sa.Column("external_job_title", sa.String(255), nullable=True),
        sa.Column("external_job_id", sa.String(100), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(50), server_default="submitted"),
        sa.Column("is_first_submission", sa.Boolean(), server_default="false"),
        sa.Column("employer_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employer_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "employer_job_id",
            "candidate_profile_id",
            "recruiter_profile_id",
            name="uq_submission_employer_job_candidate_recruiter",
        ),
        sa.UniqueConstraint(
            "recruiter_job_id",
            "candidate_profile_id",
            name="uq_submission_recruiter_job_candidate",
        ),
    )


def downgrade() -> None:
    op.drop_table("candidate_submissions")
    op.drop_column("recruiter_jobs", "employer_job_id")
    op.drop_column("employer_profiles", "contract_vehicle")
    op.drop_column("employer_profiles", "parent_employer_id")
    op.drop_column("recruiter_clients", "contract_vehicle")
    op.drop_column("recruiter_clients", "parent_client_id")
