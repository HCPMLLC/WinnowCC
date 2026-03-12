"""add submittal_packages table and link to candidate_submissions

Revision ID: d120632ff473
Revises: e6413d9a1dce
Create Date: 2026-03-12 10:50:24.398351

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd120632ff473'
down_revision: Union[str, None] = 'e6413d9a1dce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('submittal_packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recruiter_profile_id', sa.Integer(), nullable=False),
        sa.Column('recruiter_job_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('recipient_name', sa.String(length=255), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('candidate_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('pipeline_candidate_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('package_options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('merged_pdf_url', sa.String(length=1000), nullable=True),
        sa.Column('cover_email_subject', sa.String(length=500), nullable=True),
        sa.Column('cover_email_body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='building', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_message_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['recruiter_clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recruiter_job_id'], ['recruiter_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recruiter_profile_id'], ['recruiter_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('candidate_submissions',
        sa.Column('submittal_package_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_candidate_submissions_submittal_package',
        'candidate_submissions', 'submittal_packages',
        ['submittal_package_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_candidate_submissions_submittal_package', 'candidate_submissions', type_='foreignkey')
    op.drop_column('candidate_submissions', 'submittal_package_id')
    op.drop_table('submittal_packages')
