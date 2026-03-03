"""add cover_letters to usage_counters

Revision ID: 9005bcb85b82
Revises: ccf64a8b2205
Create Date: 2026-03-03 08:23:18.489512

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9005bcb85b82'
down_revision: Union[str, None] = 'ccf64a8b2205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usage_counters',
        sa.Column('cover_letters', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('usage_counters', 'cover_letters')
