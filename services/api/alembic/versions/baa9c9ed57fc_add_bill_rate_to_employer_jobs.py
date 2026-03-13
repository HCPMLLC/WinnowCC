"""add bill_rate to employer_jobs

Revision ID: baa9c9ed57fc
Revises: f0fed1b5bd4a
Create Date: 2026-03-13 08:37:32.406911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'baa9c9ed57fc'
down_revision: Union[str, None] = 'f0fed1b5bd4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('employer_jobs', sa.Column('bill_rate', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('employer_jobs', 'bill_rate')
