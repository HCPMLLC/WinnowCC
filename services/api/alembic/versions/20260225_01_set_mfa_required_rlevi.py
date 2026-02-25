"""Set mfa_required=true for rlevi@hcpm.llc.

Revision ID: 20260225_01
Revises: 20260224_03
"""

from alembic import op

revision = "20260225_01"
down_revision = "20260224_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET mfa_required = true"
        " WHERE email = 'rlevi@hcpm.llc'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET mfa_required = false"
        " WHERE email = 'rlevi@hcpm.llc'"
    )
