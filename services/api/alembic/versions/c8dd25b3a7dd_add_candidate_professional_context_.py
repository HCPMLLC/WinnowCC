"""add candidate professional context columns

Revision ID: c8dd25b3a7dd
Revises: h1b2c3d4e5f6
Create Date: 2026-03-08 20:20:22.247862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8dd25b3a7dd'
down_revision: Union[str, None] = 'h1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recruiter_pipeline_candidates', sa.Column('current_company', sa.String(length=255), nullable=True))
    op.add_column('recruiter_pipeline_candidates', sa.Column('current_title', sa.String(length=255), nullable=True))
    op.add_column('recruiter_pipeline_candidates', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('recruiter_pipeline_candidates', sa.Column('skills', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('recruiter_pipeline_candidates', 'skills')
    op.drop_column('recruiter_pipeline_candidates', 'location')
    op.drop_column('recruiter_pipeline_candidates', 'current_title')
    op.drop_column('recruiter_pipeline_candidates', 'current_company')
