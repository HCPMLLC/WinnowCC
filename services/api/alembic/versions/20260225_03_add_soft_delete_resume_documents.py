"""Add deleted_at column to resume_documents for soft-delete.

Revision ID: 20260225_03
Revises: 20260225_02
"""

import sqlalchemy as sa
from alembic import op

revision = "20260225_03"
down_revision = "20260225_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_resume_documents_deleted_at",
        "resume_documents",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_resume_documents_deleted_at", table_name="resume_documents")
    op.drop_column("resume_documents", "deleted_at")
