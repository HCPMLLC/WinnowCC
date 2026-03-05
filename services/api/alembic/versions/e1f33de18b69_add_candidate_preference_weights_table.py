"""add candidate_preference_weights table

Revision ID: e1f33de18b69
Revises: c3d4e5f6a7b8
Create Date: 2026-03-04 18:09:51.379723

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e1f33de18b69'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('candidate_preference_weights',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('skill_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('title_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('location_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('salary_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('years_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('learned_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('positive_events', sa.Integer(), server_default='0', nullable=False),
    sa.Column('negative_events', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_recalculated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('candidate_preference_weights')
