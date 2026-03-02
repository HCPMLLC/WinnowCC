"""add ip_allowlist to employer_profiles

Revision ID: 161370905dc9
Revises: fcf1c15ad2be
Create Date: 2026-03-02 14:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "161370905dc9"
down_revision: Union[str, None] = "fcf1c15ad2be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employer_profiles",
        sa.Column("ip_allowlist", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employer_profiles", "ip_allowlist")
