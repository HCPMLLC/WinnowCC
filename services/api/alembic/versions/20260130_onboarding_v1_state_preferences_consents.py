"""onboarding v1 state preferences consents

Revision ID: 20260130_onboarding_v1
Revises: 20260130_01
Create Date: 2026-01-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260130_onboarding_v1"
down_revision = "20260130_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres enum
    application_mode_enum = sa.Enum(
        "review_required",
        "auto_apply_limited",
        name="application_mode",
    )
    application_mode_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "onboarding_state",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "current_step",
            sa.String(length=32),
            nullable=False,
            server_default="welcome",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_onboarding_state_completed_at", "onboarding_state", ["completed_at"]
    )

    op.create_table(
        "candidate_preferences_v1",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "work_mode", sa.String(length=16), nullable=False, server_default="any"
        ),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column(
            "salary_currency", sa.String(length=8), nullable=False, server_default="USD"
        ),
        sa.Column(
            "employment_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("travel_percent_max", sa.Integer(), nullable=True),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_candidate_preferences_v1_user_active",
        "candidate_preferences_v1",
        ["user_id", "active"],
    )

    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("terms_version", sa.String(length=64), nullable=False),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mjass_consent", sa.Boolean(), nullable=False),
        sa.Column("mjass_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_processing_consent", sa.Boolean(), nullable=False),
        sa.Column(
            "data_processing_consent_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("application_mode", sa.Enum(name="application_mode"), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_consents_user_active", "consents", ["user_id", "active"])


def downgrade() -> None:
    op.drop_index("ix_consents_user_active", table_name="consents")
    op.drop_table("consents")

    op.drop_index(
        "ix_candidate_preferences_v1_user_active", table_name="candidate_preferences_v1"
    )
    op.drop_table("candidate_preferences_v1")

    op.drop_index("ix_onboarding_state_completed_at", table_name="onboarding_state")
    op.drop_table("onboarding_state")

    application_mode_enum = sa.Enum(
        "review_required",
        "auto_apply_limited",
        name="application_mode",
    )
    application_mode_enum.drop(op.get_bind(), checkfirst=True)
