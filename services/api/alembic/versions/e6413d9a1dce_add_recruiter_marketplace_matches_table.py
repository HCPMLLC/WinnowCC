"""add recruiter_marketplace_matches table

Revision ID: e6413d9a1dce
Revises: 2e524eecc037
Create Date: 2026-03-11 14:40:19.461110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6413d9a1dce'
down_revision: Union[str, None] = '2e524eecc037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('recruiter_marketplace_matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recruiter_profile_id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('match_score', sa.Float(), nullable=False),
    sa.Column('matched_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['recruiter_profile_id'], ['recruiter_profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('recruiter_profile_id', 'job_id', 'candidate_profile_id', name='uq_recruiter_marketplace_match')
    )
    op.create_index('ix_marketplace_match_lookup', 'recruiter_marketplace_matches', ['recruiter_profile_id', 'job_id', 'match_score'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_marketplace_match_lookup', table_name='recruiter_marketplace_matches')
    op.drop_table('recruiter_marketplace_matches')
