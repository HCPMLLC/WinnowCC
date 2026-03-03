"""add match_explanation column

Revision ID: 20260302_03
Revises: 680867042f7c
Create Date: 2026-03-02 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260302_03"
down_revision: Union[str, None] = "680867042f7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("match_explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "match_explanation")
