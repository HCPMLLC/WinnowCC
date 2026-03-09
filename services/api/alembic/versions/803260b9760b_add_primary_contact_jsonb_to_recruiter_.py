"""add primary_contact JSONB to recruiter_jobs

Revision ID: 803260b9760b
Revises: c8dd25b3a7dd
Create Date: 2026-03-09 06:45:10.116640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '803260b9760b'
down_revision: Union[str, None] = 'c8dd25b3a7dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recruiter_jobs',
        sa.Column('primary_contact', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('recruiter_jobs', 'primary_contact')
