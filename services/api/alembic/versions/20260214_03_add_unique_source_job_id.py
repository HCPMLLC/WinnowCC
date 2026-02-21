"""Add unique constraint on (source, source_job_id) in jobs table.

Revision ID: 20260214_03
Revises: 20260214_02
Create Date: 2026-02-14
"""

from alembic import op

revision = "20260214_03"
down_revision = "20260214_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_jobs_source_source_job_id",
        "jobs",
        ["source", "source_job_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jobs_source_source_job_id", "jobs", type_="unique")
