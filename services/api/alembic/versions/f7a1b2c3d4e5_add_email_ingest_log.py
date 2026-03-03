"""add email ingest log

Revision ID: f7a1b2c3d4e5
Revises: e431d29a673e
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "f7a1b2c3d4e5"
down_revision = "e431d29a673e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_ingest_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sendgrid_message_id", sa.String(255), nullable=True),
        sa.Column("sender_email", sa.String(255), nullable=False),
        sa.Column("sender_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("status_detail", sa.Text, nullable=True),
        sa.Column("attachment_filename", sa.String(500), nullable=True),
        sa.Column("attachment_content_type", sa.String(100), nullable=True),
        sa.Column("attachment_size_bytes", sa.Integer, nullable=True),
        sa.Column("matched_user_id", sa.Integer, nullable=True),
        sa.Column("matched_employer_id", sa.Integer, nullable=True),
        sa.Column("created_job_id", sa.Integer, nullable=True),
        sa.Column("parsing_confidence", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_email_ingest_log_sender", "email_ingest_log", ["sender_email"])
    op.create_index("ix_email_ingest_log_status", "email_ingest_log", ["status"])
    op.create_index(
        "ix_email_ingest_log_received", "email_ingest_log", ["received_at"]
    )


def downgrade() -> None:
    op.drop_table("email_ingest_log")
