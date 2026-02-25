"""add client_company_name to employer_jobs

Revision ID: 113f836b136b
Revises: 20260225_03
Create Date: 2026-02-25 12:30:34.825009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '113f836b136b'
down_revision: Union[str, None] = '20260225_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('employer_jobs', sa.Column('client_company_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('employer_jobs', 'client_company_name')
