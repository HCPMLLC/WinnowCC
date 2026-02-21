"""add enhanced job fields

Revision ID: 20260210_02
Revises: 20260210_01
Create Date: 2026-02-10

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260210_02"
down_revision = "20260210_01"
branch_labels = None
depends_on = None


def upgrade():
    # Enhanced job fields
    op.add_column(
        "employer_jobs",
        sa.Column("job_id_external", sa.String(100), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("close_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("job_category", sa.String(100), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("department", sa.String(100), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("certifications_required", JSONB, nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("job_type", sa.String(50), nullable=True),
    )

    # Archival fields
    op.add_column(
        "employer_jobs",
        sa.Column(
            "archived", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("archived_reason", sa.String(50), nullable=True),
    )

    # Document source tracking
    op.add_column(
        "employer_jobs",
        sa.Column("source_document_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "employer_jobs",
        sa.Column(
            "parsed_from_document",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "employer_jobs",
        sa.Column("parsing_confidence", sa.Float(), nullable=True),
    )

    # Indexes for common queries
    op.create_index(
        "idx_employer_jobs_archived", "employer_jobs", ["archived"]
    )
    op.create_index(
        "idx_employer_jobs_close_date", "employer_jobs", ["close_date"]
    )
    op.create_index(
        "idx_employer_jobs_job_category", "employer_jobs", ["job_category"]
    )


def downgrade():
    op.drop_index("idx_employer_jobs_job_category")
    op.drop_index("idx_employer_jobs_close_date")
    op.drop_index("idx_employer_jobs_archived")

    op.drop_column("employer_jobs", "parsing_confidence")
    op.drop_column("employer_jobs", "parsed_from_document")
    op.drop_column("employer_jobs", "source_document_url")
    op.drop_column("employer_jobs", "archived_reason")
    op.drop_column("employer_jobs", "archived_at")
    op.drop_column("employer_jobs", "archived")
    op.drop_column("employer_jobs", "job_type")
    op.drop_column("employer_jobs", "certifications_required")
    op.drop_column("employer_jobs", "department")
    op.drop_column("employer_jobs", "job_category")
    op.drop_column("employer_jobs", "close_date")
    op.drop_column("employer_jobs", "start_date")
    op.drop_column("employer_jobs", "job_id_external")
