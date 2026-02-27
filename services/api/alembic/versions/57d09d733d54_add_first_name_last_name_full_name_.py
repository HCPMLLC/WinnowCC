"""Add first_name, last_name, full_name, phone to users

Revision ID: 57d09d733d54
Revises: 3743009ba227
Create Date: 2026-02-26 11:27:32.720494

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57d09d733d54"
down_revision: str | None = "3743009ba227"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("first_name", sa.String(length=100), nullable=True)
    )
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
    op.drop_column("users", "full_name")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
