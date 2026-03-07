"""add bulk attach columns to recruiter_pipeline_candidates

Revision ID: 45c23c65fad1
Revises: ebef80f7a590
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision = "45c23c65fad1"
down_revision = "ebef80f7a590"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recruiter_pipeline_candidates",
        sa.Column("bulk_attach_batch_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "recruiter_pipeline_candidates",
        sa.Column("bulk_attach_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "recruiter_pipeline_candidates",
        sa.Column("bulk_attach_matched_by", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_rpc_bulk_attach_batch_id",
        "recruiter_pipeline_candidates",
        ["bulk_attach_batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rpc_bulk_attach_batch_id",
        table_name="recruiter_pipeline_candidates",
    )
    op.drop_column("recruiter_pipeline_candidates", "bulk_attach_matched_by")
    op.drop_column("recruiter_pipeline_candidates", "bulk_attach_status")
    op.drop_column("recruiter_pipeline_candidates", "bulk_attach_batch_id")
