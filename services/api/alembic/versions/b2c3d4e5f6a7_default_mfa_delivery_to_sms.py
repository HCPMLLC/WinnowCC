"""default mfa delivery to sms

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Change server default for new rows from 'email' to 'sms'
    op.alter_column(
        "users",
        "mfa_delivery_method",
        server_default="sms",
    )
    # Switch existing users who still have the old default to sms
    op.execute(
        "UPDATE users SET mfa_delivery_method = 'sms' "
        "WHERE mfa_delivery_method = 'email'"
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "mfa_delivery_method",
        server_default="email",
    )
    op.execute(
        "UPDATE users SET mfa_delivery_method = 'email' "
        "WHERE mfa_delivery_method = 'sms'"
    )
