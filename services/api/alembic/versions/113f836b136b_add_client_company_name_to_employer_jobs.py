"""add client_company_name to employer_jobs

Revision ID: 113f836b136b
Revises: 20260225_03
Create Date: 2026-02-25 12:30:34.825009

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "113f836b136b"
down_revision: str | None = "20260225_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employer_jobs",
        sa.Column("client_company_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employer_jobs", "client_company_name")
