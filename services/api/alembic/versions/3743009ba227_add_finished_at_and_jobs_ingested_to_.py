"""add finished_at and jobs_ingested to job_runs

Revision ID: 3743009ba227
Revises: f6ead5847f50
Create Date: 2026-02-26 10:48:43.028203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3743009ba227'
down_revision: Union[str, None] = 'f6ead5847f50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('job_runs', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('job_runs', sa.Column('jobs_ingested', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('job_runs', 'jobs_ingested')
    op.drop_column('job_runs', 'finished_at')
