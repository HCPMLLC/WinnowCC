"""Add employer forms handler tables (P45).

Creates:
- job_forms (employer form templates associated with jobs)
- filled_forms (candidate-specific filled form instances)
- merged_packets (final merged PDF application packets)
- has_references column on candidate_profiles

Revision ID: 20260211_02
Revises: 20260211_01
Create Date: 2026-02-11
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "20260211_02"
down_revision = "20260211_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- has_references flag on candidate_profiles ---
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='candidate_profiles' AND column_name='has_references'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "candidate_profiles",
            sa.Column(
                "has_references",
                sa.Boolean(),
                server_default="false",
                nullable=True,
            ),
        )

    # --- job_forms ---
    op.create_table(
        "job_forms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_url", sa.String(1000), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False, server_default="docx"),
        sa.Column("form_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("parsed_structure", postgresql.JSONB(), nullable=True),
        sa.Column("is_parsed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_forms_job_id", "job_forms", ["job_id"])

    # --- filled_forms ---
    op.create_table(
        "filled_forms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "job_form_id",
            sa.Integer(),
            sa.ForeignKey("job_forms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Integer(),
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filled_data", postgresql.JSONB(), nullable=True),
        sa.Column("unfilled_fields", postgresql.JSONB(), nullable=True),
        sa.Column("gaps_detected", postgresql.JSONB(), nullable=True),
        sa.Column("output_storage_url", sa.String(1000), nullable=True),
        sa.Column(
            "output_format",
            sa.String(10),
            nullable=False,
            server_default="docx",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- merged_packets ---
    op.create_table(
        "merged_packets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "match_id",
            sa.Integer(),
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_order", postgresql.JSONB(), nullable=True),
        sa.Column("merged_pdf_url", sa.String(1000), nullable=True),
        sa.Column("naming_convention", sa.String(500), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("merged_packets")
    op.drop_table("filled_forms")
    op.drop_table("job_forms")
    op.drop_column("candidate_profiles", "has_references")
