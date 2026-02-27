"""Add contact fields to employer_profiles.

Revision ID: 20260218_03
Revises: 20260218_02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260218_03"
down_revision = "20260218_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employer_profiles",
        sa.Column("contact_first_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("contact_last_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "employer_profiles", sa.Column("contact_email", sa.String(255), nullable=True)
    )
    op.add_column(
        "employer_profiles", sa.Column("contact_phone", sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("employer_profiles", "contact_phone")
    op.drop_column("employer_profiles", "contact_email")
    op.drop_column("employer_profiles", "contact_last_name")
    op.drop_column("employer_profiles", "contact_first_name")
