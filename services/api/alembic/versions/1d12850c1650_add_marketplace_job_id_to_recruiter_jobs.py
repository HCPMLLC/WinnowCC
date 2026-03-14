"""add marketplace_job_id to recruiter_jobs

Revision ID: 1d12850c1650
Revises: ca3032a6dd32
Create Date: 2026-03-14 13:44:35.018885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d12850c1650'
down_revision: Union[str, None] = 'ca3032a6dd32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recruiter_jobs',
        sa.Column('marketplace_job_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_recruiter_jobs_marketplace_job_id',
        'recruiter_jobs',
        ['marketplace_job_id'],
    )
    op.create_foreign_key(
        'fk_recruiter_jobs_marketplace_job_id',
        'recruiter_jobs',
        'jobs',
        ['marketplace_job_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_recruiter_jobs_marketplace_job_id',
        'recruiter_jobs',
        type_='foreignkey',
    )
    op.drop_index(
        'ix_recruiter_jobs_marketplace_job_id',
        table_name='recruiter_jobs',
    )
    op.drop_column('recruiter_jobs', 'marketplace_job_id')
