"""Add billing_exempt to recruiter_profiles and upgrade Hill Country PM.

Revision ID: 20260224_01
Revises: 20260223_01
Create Date: 2026-02-24
"""

import sqlalchemy as sa  # noqa: I001

from alembic import op

revision = "20260224_01"
down_revision = "20260223_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_profiles",
        sa.Column(
            "billing_exempt",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # Upgrade "Hill Country Project Management LLC" to agency + billing_exempt
    op.execute(
        """
        UPDATE recruiter_profiles
        SET subscription_tier = 'agency',
            subscription_status = NULL,
            billing_exempt = true
        WHERE company_name = 'Hill Country Project Management LLC'
        """
    )


def downgrade() -> None:
    # Revert Hill Country back to trial
    op.execute(
        """
        UPDATE recruiter_profiles
        SET subscription_tier = 'trial',
            subscription_status = 'trialing',
            billing_exempt = false
        WHERE company_name = 'Hill Country Project Management LLC'
        """
    )

    op.drop_column("recruiter_profiles", "billing_exempt")
