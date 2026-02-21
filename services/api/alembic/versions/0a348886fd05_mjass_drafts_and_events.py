"""mjass drafts and events

Revision ID: 0a348886fd05
Revises: 20260130_onboarding_v1
Create Date: 2026-01-31 05:36:18.413266

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a348886fd05"
down_revision: str | None = "20260130_onboarding_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # MJASS: Drafts (what will be submitted) + Events (audit trail)
    op.create_table(
        "mjass_application_drafts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Optional links (keep nullable + no FK constraints to avoid coupling to unknown table names)
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("match_id", sa.BigInteger(), nullable=True),
        # Job context
        sa.Column("job_url", sa.Text(), nullable=True),
        sa.Column("job_title", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column(
            "source", sa.Text(), nullable=True
        ),  # e.g. linkedin/indeed/company_site
        # State machine
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "application_mode",
            sa.Text(),
            nullable=False,
            server_default="review_required",
        ),
        # What we will submit + explainability payload (JSONB)
        sa.Column(
            "draft_payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "explain",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_mjass_drafts_user_id", "mjass_application_drafts", ["user_id"])
    op.create_index("ix_mjass_drafts_status", "mjass_application_drafts", ["status"])
    op.create_index(
        "ix_mjass_drafts_created_at", "mjass_application_drafts", ["created_at"]
    )
    op.create_index(
        "ix_mjass_drafts_match_id", "mjass_application_drafts", ["match_id"]
    )

    op.create_table(
        "mjass_application_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("draft_id", sa.BigInteger(), nullable=False),
        # Audit/event details
        sa.Column(
            "event_type", sa.Text(), nullable=False
        ),  # created/approved/rejected/changes_requested/submitted/note
        sa.Column(
            "actor_type", sa.Text(), nullable=False, server_default="candidate"
        ),  # candidate/system/admin
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_mjass_events_draft_id", "mjass_application_events", ["draft_id"]
    )
    op.create_index(
        "ix_mjass_events_created_at", "mjass_application_events", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_mjass_events_created_at", table_name="mjass_application_events")
    op.drop_index("ix_mjass_events_draft_id", table_name="mjass_application_events")
    op.drop_table("mjass_application_events")

    op.drop_index("ix_mjass_drafts_match_id", table_name="mjass_application_drafts")
    op.drop_index("ix_mjass_drafts_created_at", table_name="mjass_application_drafts")
    op.drop_index("ix_mjass_drafts_status", table_name="mjass_application_drafts")
    op.drop_index("ix_mjass_drafts_user_id", table_name="mjass_application_drafts")
    op.drop_table("mjass_application_drafts")
