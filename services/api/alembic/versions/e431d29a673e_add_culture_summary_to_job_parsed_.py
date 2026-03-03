"""add culture_summary to job_parsed_details

Revision ID: e431d29a673e
Revises: f671b889e8c0
Create Date: 2026-03-03 04:45:38.807539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e431d29a673e'
down_revision: Union[str, None] = 'f671b889e8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'job_parsed_details',
        sa.Column('culture_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('job_parsed_details', 'culture_summary')
