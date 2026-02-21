"""add candidate preferences and consent fields

Revision ID: 20260130_01
Revises: 20260129_01
Create Date: 2026-01-30 09:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260130_01"
down_revision = "20260129_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate", sa.Column("plan_tier", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "candidate",
        sa.Column("plan_billing_cycle", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "candidate",
        sa.Column("alert_frequency", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "candidate",
        sa.Column(
            "communication_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "candidate",
        sa.Column(
            "consent_terms",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "candidate",
        sa.Column(
            "consent_privacy",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "candidate",
        sa.Column(
            "consent_auto_renewal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "candidate",
        sa.Column(
            "consent_marketing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("candidate", "consent_marketing")
    op.drop_column("candidate", "consent_auto_renewal")
    op.drop_column("candidate", "consent_privacy")
    op.drop_column("candidate", "consent_terms")
    op.drop_column("candidate", "communication_channels")
    op.drop_column("candidate", "alert_frequency")
    op.drop_column("candidate", "plan_billing_cycle")
    op.drop_column("candidate", "plan_tier")
