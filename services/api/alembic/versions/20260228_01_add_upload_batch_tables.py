"""Add upload_batches and upload_batch_files tables for async bulk processing.

Revision ID: 20260228_01
Revises: 20260226_01
"""

import sqlalchemy as sa

from alembic import op

revision = "20260228_01"
down_revision = "20260226_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.String(36), unique=True, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("batch_type", sa.String(50), nullable=False),
        sa.Column("owner_profile_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_files", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_succeeded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upload_batches_batch_id", "upload_batches", ["batch_id"])
    op.create_index(
        "ix_upload_batches_user_status", "upload_batches", ["user_id", "status"]
    )

    op.create_table(
        "upload_batch_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("file_index", sa.Integer, nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("staged_path", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_upload_batch_files_batch_id", "upload_batch_files", ["batch_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_upload_batch_files_batch_id", table_name="upload_batch_files")
    op.drop_table("upload_batch_files")
    op.drop_index("ix_upload_batches_user_status", table_name="upload_batches")
    op.drop_index("ix_upload_batches_batch_id", table_name="upload_batches")
    op.drop_table("upload_batches")
