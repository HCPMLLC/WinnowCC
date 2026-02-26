"""add embedding column to recruiter_jobs

Revision ID: f6ead5847f50
Revises: 113f836b136b
Create Date: 2026-02-26 05:28:27.943847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy.vector

# revision identifiers, used by Alembic.
revision: str = 'f6ead5847f50'
down_revision: Union[str, None] = '113f836b136b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recruiter_jobs',
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('recruiter_jobs', 'embedding')
