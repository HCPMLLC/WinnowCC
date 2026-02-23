"""Set rlevi@hcpm.llc to admin role.

Revision ID: 20260222_01
Revises: 20260219_03
"""

from alembic import op

revision = "20260222_01"
down_revision = "20260219_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only set the is_admin flag — do NOT overwrite role (candidate/employer/recruiter)
    op.execute(
        "UPDATE users SET is_admin = true"
        " WHERE email = 'rlevi@hcpm.llc'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET is_admin = false"
        " WHERE email = 'rlevi@hcpm.llc'"
    )
