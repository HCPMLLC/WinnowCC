"""
Alembic Migration: Add Intelligent Resume Parser Tables
=========================================================

Revision ID: add_intelligent_parser
Revises: [previous_revision]
Create Date: 2026-02-03

This migration adds tables for the intelligent resume parser that distinguishes
core skills from environmental/technology-adjacent knowledge.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "add_intelligent_parser"
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Create skill_category enum type
    skill_category_enum = postgresql.ENUM(
        "core", "technical", "environmental", "soft", name="skill_category"
    )
    skill_category_enum.create(op.get_bind())

    # Create parsed_resume_documents table
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
            "parsed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("parser_version", sa.String(length=20), nullable=True),
        sa.Column(
            "total_jobs_extracted", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column(
            "total_skills_extracted", sa.Integer(), server_default="0", nullable=True
        ),
        sa.Column("core_skills_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["resume_document_id"], ["resume_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_document_id"),
    )
    op.create_index("idx_parsed_resume_user", "parsed_resume_documents", ["user_id"])
    op.create_index(
        "idx_parsed_resume_doc", "parsed_resume_documents", ["resume_document_id"]
    )

    # Create job_experiences table
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
        sa.Column("position_order", sa.Integer(), server_default="0", nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_exp_resume", "job_experiences", ["parsed_resume_id"])
    op.create_index("idx_job_exp_company", "job_experiences", ["company_name"])

    # Create quantified_accomplishments table
    op.create_table(
        "quantified_accomplishments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_experience_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("impact_category", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["job_experience_id"], ["job_experiences.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_accomplishment_job", "quantified_accomplishments", ["job_experience_id"]
    )
    op.create_index(
        "idx_accomplishment_category", "quantified_accomplishments", ["impact_category"]
    )

    # Create extracted_skills table
    op.create_table(
        "extracted_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("category", skill_category_enum, nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0.5", nullable=True),
        sa.Column("extraction_source", sa.String(length=100), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_skill_resume", "extracted_skills", ["parsed_resume_id"])
    op.create_index("idx_skill_category", "extracted_skills", ["category"])
    op.create_index("idx_skill_name", "extracted_skills", ["skill_name"])

    # Create job_skill_usage table
    op.create_table(
        "job_skill_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_experience_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("skill_category", skill_category_enum, nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["job_experience_id"], ["job_experiences.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_skill_job", "job_skill_usage", ["job_experience_id"])

    # Create certifications table
    op.create_table(
        "certifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("certification_name", sa.String(length=255), nullable=False),
        sa.Column("issuing_organization", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.String(length=50), nullable=True),
        sa.Column("expiration_date", sa.String(length=50), nullable=True),
        sa.Column("credential_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cert_resume", "certifications", ["parsed_resume_id"])

    # Create education_records table
    op.create_table(
        "education_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_resume_id", sa.Integer(), nullable=False),
        sa.Column("degree", sa.String(length=255), nullable=True),
        sa.Column("field_of_study", sa.String(length=255), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("graduation_date", sa.String(length=50), nullable=True),
        sa.Column("gpa", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["parsed_resume_id"], ["parsed_resume_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_education_resume", "education_records", ["parsed_resume_id"])


def downgrade():
    # Drop tables in reverse order
    op.drop_index("idx_education_resume", table_name="education_records")
    op.drop_table("education_records")

    op.drop_index("idx_cert_resume", table_name="certifications")
    op.drop_table("certifications")

    op.drop_index("idx_job_skill_job", table_name="job_skill_usage")
    op.drop_table("job_skill_usage")

    op.drop_index("idx_skill_name", table_name="extracted_skills")
    op.drop_index("idx_skill_category", table_name="extracted_skills")
    op.drop_index("idx_skill_resume", table_name="extracted_skills")
    op.drop_table("extracted_skills")

    op.drop_index(
        "idx_accomplishment_category", table_name="quantified_accomplishments"
    )
    op.drop_index("idx_accomplishment_job", table_name="quantified_accomplishments")
    op.drop_table("quantified_accomplishments")

    op.drop_index("idx_job_exp_company", table_name="job_experiences")
    op.drop_index("idx_job_exp_resume", table_name="job_experiences")
    op.drop_table("job_experiences")

    op.drop_index("idx_parsed_resume_doc", table_name="parsed_resume_documents")
    op.drop_index("idx_parsed_resume_user", table_name="parsed_resume_documents")
    op.drop_table("parsed_resume_documents")

    # Drop enum type
    skill_category_enum = postgresql.ENUM(name="skill_category")
    skill_category_enum.drop(op.get_bind())
