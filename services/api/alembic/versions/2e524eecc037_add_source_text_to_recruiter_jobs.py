"""add source_text to recruiter_jobs

Revision ID: 2e524eecc037
Revises: a7b2c3d4e5f6
Create Date: 2026-03-11 08:16:55.552009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e524eecc037'
down_revision: Union[str, None] = 'a7b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recruiter_jobs', sa.Column('source_text', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('recruiter_jobs', 'source_text')
