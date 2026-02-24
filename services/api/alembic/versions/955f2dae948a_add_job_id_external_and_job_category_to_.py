"""add job_id_external and job_category to recruiter_jobs

Revision ID: 955f2dae948a
Revises: 20260224_01
Create Date: 2026-02-24 08:21:27.731693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '955f2dae948a'
down_revision: Union[str, None] = '20260224_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recruiter_jobs', sa.Column('job_id_external', sa.String(length=100), nullable=True))
    op.add_column('recruiter_jobs', sa.Column('job_category', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('recruiter_jobs', 'job_category')
    op.drop_column('recruiter_jobs', 'job_id_external')
