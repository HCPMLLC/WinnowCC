"""Add contacts JSONB column to recruiter_clients.

Revision ID: 20260217_02
Revises: 20260217_01
Create Date: 2026-02-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260217_02"
down_revision = "20260217_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_clients",
        sa.Column("contacts", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recruiter_clients", "contacts")
