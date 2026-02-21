"""add notes to matches

Revision ID: ea5d6435ed5e
Revises: 20260207_03
Create Date: 2026-02-08 08:14:32.262444

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea5d6435ed5e"
down_revision: str | None = "20260207_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "notes")
