"""add purge FK constraints and snapshot columns

Revision ID: a1b2c3d4e5f6
Revises: f6ead5847f50
Create Date: 2026-02-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = ("f6ead5847f50", "20260228_01")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- matches.job_id: add ON DELETE CASCADE --
    op.drop_constraint("matches_job_id_fkey", "matches", type_="foreignkey")
    op.create_foreign_key(
        "matches_job_id_fkey",
        "matches",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # -- tailored_resumes.job_id: make nullable + ON DELETE SET NULL --
    op.alter_column(
        "tailored_resumes",
        "job_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_constraint(
        "tailored_resumes_job_id_fkey", "tailored_resumes", type_="foreignkey"
    )
    op.create_foreign_key(
        "tailored_resumes_job_id_fkey",
        "tailored_resumes",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -- snapshot columns on tailored_resumes --
    op.add_column(
        "tailored_resumes",
        sa.Column("job_title_snapshot", sa.String(255), nullable=True),
    )
    op.add_column(
        "tailored_resumes",
        sa.Column("job_company_snapshot", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tailored_resumes", "job_company_snapshot")
    op.drop_column("tailored_resumes", "job_title_snapshot")

    # Revert tailored_resumes FK
    op.drop_constraint(
        "tailored_resumes_job_id_fkey", "tailored_resumes", type_="foreignkey"
    )
    op.create_foreign_key(
        "tailored_resumes_job_id_fkey",
        "tailored_resumes",
        "jobs",
        ["job_id"],
        ["id"],
    )
    op.alter_column(
        "tailored_resumes",
        "job_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Revert matches FK
    op.drop_constraint("matches_job_id_fkey", "matches", type_="foreignkey")
    op.create_foreign_key(
        "matches_job_id_fkey",
        "matches",
        "jobs",
        ["job_id"],
        ["id"],
    )
