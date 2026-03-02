"""add billing_interval to employer_profiles

Revision ID: e6bf81254774
Revises: 435465e7a3f9
Create Date: 2026-03-02 05:53:18.205447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6bf81254774'
down_revision: Union[str, None] = '435465e7a3f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'employer_profiles',
        sa.Column('billing_interval', sa.String(length=20), server_default='monthly', nullable=True),
    )


def downgrade() -> None:
    op.drop_column('employer_profiles', 'billing_interval')
