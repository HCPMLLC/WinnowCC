"""add upstream_recruiter_job_id to recruiter_jobs

Revision ID: 913ccd9ff7e8
Revises: 803260b9760b
Create Date: 2026-03-10 16:46:51.428341

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '913ccd9ff7e8'
down_revision: Union[str, None] = '803260b9760b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recruiter_jobs",
        sa.Column("upstream_recruiter_job_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_recruiter_jobs_upstream_recruiter_job_id"),
        "recruiter_jobs",
        ["upstream_recruiter_job_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_recruiter_jobs_upstream_recruiter_job_id",
        "recruiter_jobs",
        "recruiter_jobs",
        ["upstream_recruiter_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_recruiter_jobs_upstream_recruiter_job_id",
        "recruiter_jobs",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_recruiter_jobs_upstream_recruiter_job_id"),
        table_name="recruiter_jobs",
    )
    op.drop_column("recruiter_jobs", "upstream_recruiter_job_id")
