"""Add job distribution tables (board_connections, job_distributions, distribution_events).

Revision ID: 20260210_03
Revises: 20260210_02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260210_03"
down_revision = "20260210_02"
branch_labels = None
depends_on = None


def upgrade():
    # --- board_connections ---
    op.create_table(
        "board_connections",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_id",
            sa.Integer,
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("board_type", sa.String(50), nullable=False),
        sa.Column("board_name", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("api_secret_encrypted", sa.Text, nullable=True),
        sa.Column("feed_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(50), nullable=True),
        sa.Column("last_sync_error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint("employer_id", "board_type", name="uq_board_connections_employer_board"),
    )
    op.create_index("idx_board_connections_employer_id", "board_connections", ["employer_id"])

    # --- job_distributions ---
    op.create_table(
        "job_distributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "employer_job_id",
            sa.Integer,
            sa.ForeignKey("employer_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "board_connection_id",
            sa.Integer,
            sa.ForeignKey("board_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_job_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("live_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feed_payload", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("impressions", sa.Integer, server_default="0", nullable=False),
        sa.Column("clicks", sa.Integer, server_default="0", nullable=False),
        sa.Column("applications", sa.Integer, server_default="0", nullable=False),
        sa.Column("cost_spent", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.UniqueConstraint(
            "employer_job_id",
            "board_connection_id",
            name="uq_job_distributions_job_board",
        ),
    )
    op.create_index("idx_job_distributions_status", "job_distributions", ["status"])
    op.create_index(
        "idx_job_distributions_employer_job_id",
        "job_distributions",
        ["employer_job_id"],
    )

    # --- distribution_events ---
    op.create_table(
        "distribution_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "distribution_id",
            sa.Integer,
            sa.ForeignKey("job_distributions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_distribution_events_distribution_id",
        "distribution_events",
        ["distribution_id"],
    )


def downgrade():
    op.drop_table("distribution_events")
    op.drop_table("job_distributions")
    op.drop_table("board_connections")
