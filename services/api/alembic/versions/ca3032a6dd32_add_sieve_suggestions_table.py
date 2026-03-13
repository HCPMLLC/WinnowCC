"""add sieve_suggestions table

Revision ID: ca3032a6dd32
Revises: 898fb06bce0c
Create Date: 2026-03-13 12:56:18.244736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca3032a6dd32'
down_revision: Union[str, None] = '898fb06bce0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('sieve_suggestions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('source_user_id', sa.Integer(), nullable=True),
        sa.Column('conversation_snippet', sa.Text(), nullable=True),
        sa.Column('alignment_score', sa.Float(), nullable=True),
        sa.Column('value_score', sa.Float(), nullable=True),
        sa.Column('cost_estimate', sa.String(length=10), nullable=True),
        sa.Column('cost_score', sa.Float(), nullable=True),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('priority_label', sa.String(length=10), nullable=True),
        sa.Column('scoring_rationale', sa.Text(), nullable=True),
        sa.Column('implementation_prompt', sa.Text(), nullable=True),
        sa.Column('prompt_file_path', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('sieve_suggestions')
