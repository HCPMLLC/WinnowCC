"""add hourly rate columns to recruiter_jobs

Revision ID: ebef80f7a590
Revises: e1f33de18b69
Create Date: 2026-03-05 09:19:12.016864

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ebef80f7a590'
down_revision: Union[str, None] = 'e1f33de18b69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recruiter_jobs', sa.Column('hourly_rate_min', sa.Integer(), nullable=True))
    op.add_column('recruiter_jobs', sa.Column('hourly_rate_max', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('recruiter_jobs', 'hourly_rate_max')
    op.drop_column('recruiter_jobs', 'hourly_rate_min')
