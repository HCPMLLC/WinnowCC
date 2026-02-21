"""add_employer_tables

Revision ID: 20260210_01
Revises: 20260209_02
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260210_01"
down_revision = "20260209_02"
branch_labels = None
depends_on = None


def upgrade():
    # Add role column to users table
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="candidate"),
    )

    # Create employer_profiles table
    op.create_table(
        "employer_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_size", sa.String(50)),
        sa.Column("industry", sa.String(100)),
        sa.Column("company_website", sa.String(500)),
        sa.Column("company_description", sa.Text()),
        sa.Column("company_logo_url", sa.String(500)),
        sa.Column("billing_email", sa.String(255)),
        sa.Column(
            "subscription_tier",
            sa.String(50),
            nullable=False,
            server_default="free",
        ),
        sa.Column("subscription_status", sa.String(50), server_default="active"),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("stripe_subscription_id", sa.String(255)),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create employer_jobs table
    op.create_table(
        "employer_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_id",
            sa.Integer,
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text()),
        sa.Column("nice_to_haves", sa.Text()),
        sa.Column("location", sa.String(255)),
        sa.Column("remote_policy", sa.String(50)),
        sa.Column("employment_type", sa.String(50)),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("salary_currency", sa.String(10), server_default="USD"),
        sa.Column("equity_offered", sa.Boolean(), server_default="false"),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("application_url", sa.String(500)),
        sa.Column("application_email", sa.String(255)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("closes_at", sa.DateTime(timezone=True)),
        sa.Column("view_count", sa.Integer(), server_default="0"),
        sa.Column("application_count", sa.Integer(), server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create employer_candidate_views table
    op.create_table(
        "employer_candidate_views",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_id",
            sa.Integer,
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.Integer,
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("source", sa.String(100)),
    )

    # Create employer_saved_candidates table
    op.create_table(
        "employer_saved_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_id",
            sa.Integer,
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.Integer,
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "saved_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "employer_id", "candidate_id", name="unique_employer_saved_candidate"
        ),
    )

    # Add columns to candidate_profiles for visibility
    op.add_column(
        "candidate_profiles",
        sa.Column("open_to_opportunities", sa.Boolean(), server_default="true"),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("profile_visibility", sa.String(50), server_default="public"),
    )

    # Create indexes for performance
    op.create_index("idx_employer_jobs_status", "employer_jobs", ["status"])
    op.create_index("idx_employer_jobs_employer_id", "employer_jobs", ["employer_id"])
    op.create_index(
        "idx_employer_candidate_views_employer",
        "employer_candidate_views",
        ["employer_id"],
    )
    op.create_index(
        "idx_employer_saved_candidates_employer",
        "employer_saved_candidates",
        ["employer_id"],
    )


def downgrade():
    # Drop indexes
    op.drop_index("idx_employer_saved_candidates_employer")
    op.drop_index("idx_employer_candidate_views_employer")
    op.drop_index("idx_employer_jobs_employer_id")
    op.drop_index("idx_employer_jobs_status")

    # Drop columns from candidate_profiles
    op.drop_column("candidate_profiles", "profile_visibility")
    op.drop_column("candidate_profiles", "open_to_opportunities")

    # Drop tables
    op.drop_table("employer_saved_candidates")
    op.drop_table("employer_candidate_views")
    op.drop_table("employer_jobs")
    op.drop_table("employer_profiles")

    # Drop role column
    op.drop_column("users", "role")
