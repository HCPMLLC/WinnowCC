"""add stage_rules table

Revision ID: 898fb06bce0c
Revises: baa9c9ed57fc
Create Date: 2026-03-13 12:03:37.388436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '898fb06bce0c'
down_revision: Union[str, None] = 'baa9c9ed57fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('stage_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recruiter_profile_id', sa.Integer(), nullable=False),
    sa.Column('recruiter_job_id', sa.Integer(), nullable=True),
    sa.Column('from_stage', sa.String(length=50), nullable=False),
    sa.Column('to_stage', sa.String(length=50), nullable=False),
    sa.Column('condition_type', sa.String(length=50), nullable=False),
    sa.Column('condition_value', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['recruiter_job_id'], ['recruiter_jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recruiter_profile_id'], ['recruiter_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('stage_rules')
