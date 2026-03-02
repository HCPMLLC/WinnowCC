"""add sms_consent columns to consents table

Revision ID: 20260302_02
Revises: 4eecf72db4c6
Create Date: 2026-03-02 18:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "20260302_02"
down_revision = "4eecf72db4c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consents",
        sa.Column(
            "sms_consent",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "consents",
        sa.Column(
            "sms_consent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("consents", "sms_consent_at")
    op.drop_column("consents", "sms_consent")
