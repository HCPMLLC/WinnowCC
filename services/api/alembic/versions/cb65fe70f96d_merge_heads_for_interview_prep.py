"""merge heads for interview prep

Revision ID: cb65fe70f96d
Revises: 20260302_01, a62e952af39e
Create Date: 2026-03-02 13:31:54.719156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb65fe70f96d'
down_revision: Union[str, None] = ('20260302_01', 'a62e952af39e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
