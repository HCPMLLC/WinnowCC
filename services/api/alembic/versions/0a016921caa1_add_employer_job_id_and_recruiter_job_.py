"""add employer_job_id and recruiter_job_id to jobs

Revision ID: 0a016921caa1
Revises: b2c3d4e5f6a7
Create Date: 2026-02-28 13:13:31.014006

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0a016921caa1'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('employer_job_id', sa.Integer(), nullable=True))
    op.add_column('jobs', sa.Column('recruiter_job_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_jobs_employer_job_id'), 'jobs', ['employer_job_id'], unique=False
    )
    op.create_index(
        op.f('ix_jobs_recruiter_job_id'), 'jobs', ['recruiter_job_id'], unique=False
    )
    op.create_foreign_key(
        'fk_jobs_employer_job_id', 'jobs', 'employer_jobs',
        ['employer_job_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_jobs_recruiter_job_id', 'jobs', 'recruiter_jobs',
        ['recruiter_job_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_jobs_recruiter_job_id', 'jobs', type_='foreignkey')
    op.drop_constraint('fk_jobs_employer_job_id', 'jobs', type_='foreignkey')
    op.drop_index(op.f('ix_jobs_recruiter_job_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_employer_job_id'), table_name='jobs')
    op.drop_column('jobs', 'recruiter_job_id')
    op.drop_column('jobs', 'employer_job_id')
