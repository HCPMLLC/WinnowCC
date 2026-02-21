"""Add intelligent resume parser tables

Revision ID: 7e681a4cfd1d
Revises: 20260201_02
Create Date: 2026-02-03 11:07:03.937423

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e681a4cfd1d"
down_revision: str | None = "20260201_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create parsed resume parser tables
    op.create_table(
        "parsed_resume_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("professional_summary", sa.Text(), nullable=True),
        sa.Column(
            "parsed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(length=20), nullable=True),
        sa.Column(
            "total_jobs_extracted", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "total_skills_extracted", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "core_skills_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.ForeignKeyConstraint(
            ["resume_document_id"], ["resume_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_document_id"),
    )
    op.create_index("ix_parsed_resume_user", "parsed_resume_documents", ["user_id"])
    op.create_index(
        "ix_parsed_resume_doc", "parsed_resume_documents", ["resume_document_id"]
    )

    op.create_table(
        "extracted_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("extraction_source", sa.String(length=100), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skill_resume", "extracted_skills", ["parsed_resume_id"])
    op.create_index("ix_skill_category", "extracted_skills", ["category"])
    op.create_index("ix_skill_name", "extracted_skills", ["skill_name"])

    op.create_table(
        "job_experiences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.String(length=50), nullable=True),
        sa.Column("end_date", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("duties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("environment_description", sa.Text(), nullable=True),
        sa.Column(
            "technologies_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("position_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_exp_resume", "job_experiences", ["parsed_resume_id"])
    op.create_index("ix_job_exp_company", "job_experiences", ["company_name"])

    op.create_table(
        "parsed_certifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("certification_name", sa.String(length=255), nullable=False),
        sa.Column("issuing_organization", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.String(length=50), nullable=True),
        sa.Column("expiration_date", sa.String(length=50), nullable=True),
        sa.Column("credential_id", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cert_resume", "parsed_certifications", ["parsed_resume_id"])

    op.create_table(
        "parsed_education",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("degree", sa.String(length=255), nullable=True),
        sa.Column("field_of_study", sa.String(length=255), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("graduation_date", sa.String(length=50), nullable=True),
        sa.Column("gpa", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_education_resume", "parsed_education", ["parsed_resume_id"])

    op.create_table(
        "job_skill_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_experience_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("skill_category", sa.String(length=50), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_experience_id"], ["job_experiences.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_skill_job", "job_skill_usage", ["job_experience_id"])

    op.create_table(
        "quantified_accomplishments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_experience_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("impact_category", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_experience_id"], ["job_experiences.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accomplishment_job", "quantified_accomplishments", ["job_experience_id"]
    )
    op.create_index(
        "ix_accomplishment_category", "quantified_accomplishments", ["impact_category"]
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign key dependencies)
    op.drop_index("ix_accomplishment_category", table_name="quantified_accomplishments")
    op.drop_index("ix_accomplishment_job", table_name="quantified_accomplishments")
    op.drop_table("quantified_accomplishments")

    op.drop_index("ix_job_skill_job", table_name="job_skill_usage")
    op.drop_table("job_skill_usage")

    op.drop_index("ix_education_resume", table_name="parsed_education")
    op.drop_table("parsed_education")

    op.drop_index("ix_cert_resume", table_name="parsed_certifications")
    op.drop_table("parsed_certifications")

    op.drop_index("ix_job_exp_company", table_name="job_experiences")
    op.drop_index("ix_job_exp_resume", table_name="job_experiences")
    op.drop_table("job_experiences")

    op.drop_index("ix_skill_name", table_name="extracted_skills")
    op.drop_index("ix_skill_category", table_name="extracted_skills")
    op.drop_index("ix_skill_resume", table_name="extracted_skills")
    op.drop_table("extracted_skills")

    op.drop_index("ix_parsed_resume_doc", table_name="parsed_resume_documents")
    op.drop_index("ix_parsed_resume_user", table_name="parsed_resume_documents")
    op.drop_table("parsed_resume_documents")
