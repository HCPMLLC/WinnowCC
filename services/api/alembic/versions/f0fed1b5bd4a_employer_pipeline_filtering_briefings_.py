"""employer pipeline: filtering, briefings, outreach, submittals

Revision ID: f0fed1b5bd4a
Revises: d120632ff473
Create Date: 2026-03-12 22:03:37.365139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f0fed1b5bd4a'
down_revision: Union[str, None] = 'd120632ff473'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Denormalized filter columns on employer_job_candidates
    op.add_column('employer_job_candidates', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('employer_job_candidates', sa.Column('years_experience', sa.Integer(), nullable=True))
    op.add_column('employer_job_candidates', sa.Column('work_authorization', sa.String(length=100), nullable=True))
    op.add_column('employer_job_candidates', sa.Column('remote_preference', sa.String(length=50), nullable=True))
    op.add_column('employer_job_candidates', sa.Column('current_title', sa.String(length=255), nullable=True))
    op.add_column('employer_job_candidates', sa.Column('headline', sa.String(length=500), nullable=True))

    # 2. Usage counters on employer_profiles
    op.add_column('employer_profiles', sa.Column('briefings_used', sa.Integer(), server_default='0', nullable=False))
    op.add_column('employer_profiles', sa.Column('outreach_enrollments_used', sa.Integer(), server_default='0', nullable=False))

    # 3. Employer outreach sequences table
    op.create_table('employer_outreach_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employer_profile_id', sa.Integer(), nullable=False),
        sa.Column('employer_job_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['employer_job_id'], ['employer_jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Employer outreach enrollments table
    op.create_table('employer_outreach_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sequence_id', sa.Integer(), nullable=False),
        sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
        sa.Column('employer_profile_id', sa.Integer(), nullable=False),
        sa.Column('current_step', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('unsubscribe_token', sa.String(length=64), nullable=False),
        sa.Column('next_send_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('career_page_application_id', sa.Integer(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sequence_id'], ['employer_outreach_sequences.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sequence_id', 'candidate_profile_id', name='uq_employer_enrollment_seq_candidate')
    )
    op.create_index('ix_employer_enrollment_employer', 'employer_outreach_enrollments', ['employer_profile_id'], unique=False)
    op.create_index('ix_employer_enrollment_status_next_send', 'employer_outreach_enrollments', ['status', 'next_send_at'], unique=False)

    # 5. Employer submittal packages table
    op.create_table('employer_submittal_packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employer_profile_id', sa.Integer(), nullable=False),
        sa.Column('employer_job_id', sa.Integer(), nullable=False),
        sa.Column('recipient_name', sa.String(length=255), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_company', sa.String(length=255), nullable=True),
        sa.Column('candidate_profile_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('filled_form_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(['employer_job_id'], ['employer_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('employer_submittal_packages')
    op.drop_index('ix_employer_enrollment_status_next_send', table_name='employer_outreach_enrollments')
    op.drop_index('ix_employer_enrollment_employer', table_name='employer_outreach_enrollments')
    op.drop_table('employer_outreach_enrollments')
    op.drop_table('employer_outreach_sequences')
    op.drop_column('employer_profiles', 'outreach_enrollments_used')
    op.drop_column('employer_profiles', 'briefings_used')
    op.drop_column('employer_job_candidates', 'headline')
    op.drop_column('employer_job_candidates', 'current_title')
    op.drop_column('employer_job_candidates', 'remote_preference')
    op.drop_column('employer_job_candidates', 'work_authorization')
    op.drop_column('employer_job_candidates', 'years_experience')
    op.drop_column('employer_job_candidates', 'location')
