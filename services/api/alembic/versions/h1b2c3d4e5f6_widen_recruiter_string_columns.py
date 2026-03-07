"""Widen recruiter model string columns to prevent truncation on CRM imports.

Revision ID: h1b2c3d4e5f6
Revises: 45c23c65fad1
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "h1b2c3d4e5f6"
down_revision = "45c23c65fad1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("recruiter_pipeline_candidates", "external_phone",
                    type_=sa.String(100), existing_type=sa.String(50))
    op.alter_column("recruiter_clients", "company_size",
                    type_=sa.String(100), existing_type=sa.String(50))
    op.alter_column("recruiter_clients", "contact_phone",
                    type_=sa.String(100), existing_type=sa.String(50))
    op.alter_column("recruiter_clients", "contract_type",
                    type_=sa.String(100), existing_type=sa.String(50))
    op.alter_column("recruiter_jobs", "remote_policy",
                    type_=sa.String(100), existing_type=sa.String(50))
    op.alter_column("recruiter_jobs", "employment_type",
                    type_=sa.String(100), existing_type=sa.String(50))


def downgrade() -> None:
    op.alter_column("recruiter_jobs", "employment_type",
                    type_=sa.String(50), existing_type=sa.String(100))
    op.alter_column("recruiter_jobs", "remote_policy",
                    type_=sa.String(50), existing_type=sa.String(100))
    op.alter_column("recruiter_clients", "contract_type",
                    type_=sa.String(50), existing_type=sa.String(100))
    op.alter_column("recruiter_clients", "contact_phone",
                    type_=sa.String(50), existing_type=sa.String(100))
    op.alter_column("recruiter_clients", "company_size",
                    type_=sa.String(50), existing_type=sa.String(100))
    op.alter_column("recruiter_pipeline_candidates", "external_phone",
                    type_=sa.String(50), existing_type=sa.String(100))
