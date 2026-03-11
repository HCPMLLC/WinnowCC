"""add career pages tables for sieve-scape

Revision ID: 33d784d78434
Revises: 913ccd9ff7e8
Create Date: 2026-03-10 19:55:57.712808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '33d784d78434'
down_revision: Union[str, None] = '913ccd9ff7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Career pages
    op.create_table('career_pages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('tenant_type', sa.String(length=20), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('custom_domain', sa.String(length=255), nullable=True),
        sa.Column('custom_domain_verified', sa.Boolean(), nullable=True),
        sa.Column('custom_domain_ssl_provisioned', sa.Boolean(), nullable=True),
        sa.Column('cname_target', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('page_title', sa.String(length=200), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('published', sa.Boolean(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=True),
        sa.Column('application_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('custom_domain'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_career_pages_slug', 'career_pages', ['slug'], unique=False)
    op.create_index('ix_career_pages_tenant', 'career_pages', ['tenant_id', 'tenant_type'], unique=False)
    op.create_index(op.f('ix_career_pages_tenant_id'), 'career_pages', ['tenant_id'], unique=False)

    # Career page analytics
    op.create_table('career_page_analytics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('career_page_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('page_views', sa.Integer(), nullable=True),
        sa.Column('unique_visitors', sa.Integer(), nullable=True),
        sa.Column('job_views', sa.Integer(), nullable=True),
        sa.Column('applications_started', sa.Integer(), nullable=True),
        sa.Column('applications_completed', sa.Integer(), nullable=True),
        sa.Column('sieve_conversations', sa.Integer(), nullable=True),
        sa.Column('traffic_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['career_page_id'], ['career_pages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('career_page_id', 'date', name='uq_career_page_analytics_date'),
    )

    # Widget API keys
    op.create_table('widget_api_keys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('tenant_type', sa.String(length=20), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('key_suffix', sa.String(length=8), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('allowed_domains', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('request_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash'),
    )
    op.create_index('ix_widget_api_keys_hash', 'widget_api_keys', ['key_hash'], unique=False)
    op.create_index('ix_widget_api_keys_tenant', 'widget_api_keys', ['tenant_id', 'tenant_type'], unique=False)
    op.create_index(op.f('ix_widget_api_keys_tenant_id'), 'widget_api_keys', ['tenant_id'], unique=False)

    # Widget API key usage
    op.create_table('widget_api_key_usage',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('api_key_id', sa.UUID(), nullable=False),
        sa.Column('hour', sa.DateTime(), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['widget_api_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_widget_api_key_usage_key_hour', 'widget_api_key_usage', ['api_key_id', 'hour'], unique=False)

    # Job custom questions
    op.create_table('job_custom_questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(length=20), nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('required', sa.Boolean(), nullable=True),
        sa.Column('min_length', sa.Integer(), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('sieve_prompt_hint', sa.Text(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_custom_questions_job', 'job_custom_questions', ['job_id'], unique=False)

    # Candidate question responses
    op.create_table('candidate_question_responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('response_options', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('response_boolean', sa.Boolean(), nullable=True),
        sa.Column('answered_via', sa.String(length=20), nullable=True),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['job_custom_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('candidate_id', 'job_id', 'question_id', name='uq_candidate_question_response'),
    )

    # Cross-job recommendations
    op.create_table('cross_job_recommendations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('source_job_id', sa.Integer(), nullable=False),
        sa.Column('recommended_job_id', sa.Integer(), nullable=False),
        sa.Column('ips_score', sa.Integer(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidate.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommended_job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('candidate_id', 'source_job_id', 'recommended_job_id', name='uq_cross_job_recommendation'),
    )
    op.create_index('ix_cross_job_recommendations_candidate', 'cross_job_recommendations', ['candidate_id'], unique=False)
    op.create_index('ix_cross_job_recommendations_expires', 'cross_job_recommendations', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_table('cross_job_recommendations')
    op.drop_table('candidate_question_responses')
    op.drop_table('job_custom_questions')
    op.drop_table('widget_api_key_usage')
    op.drop_table('widget_api_keys')
    op.drop_table('career_page_analytics')
    op.drop_table('career_pages')
