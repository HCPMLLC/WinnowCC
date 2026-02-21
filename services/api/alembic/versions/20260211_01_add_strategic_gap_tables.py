"""Add strategic gap exploitation tables (P45-P54).

Creates:
- candidate_notifications (P48)
- employer_compliance_log (P49)
- talent_pipeline (P50)
- employer_team_members (P53)
- interview_feedback (P53)

Revision ID: 20260211_01
Revises: 20260210_03
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260211_01"
down_revision = "20260210_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- candidate_notifications (P48) ---
    op.create_table(
        "candidate_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_notifications_candidate_id",
        "candidate_notifications",
        ["candidate_id"],
    )

    # --- employer_compliance_log (P49) ---
    op.create_table(
        "employer_compliance_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employer_id",
            sa.Integer(),
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", postgresql.JSONB(), nullable=True),
        sa.Column("board_type", sa.String(50), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employer_compliance_log_employer_id",
        "employer_compliance_log",
        ["employer_id"],
    )
    op.create_index(
        "ix_employer_compliance_log_event_type",
        "employer_compliance_log",
        ["event_type"],
    )
    op.create_index(
        "ix_employer_compliance_log_created_at",
        "employer_compliance_log",
        ["created_at"],
    )

    # --- talent_pipeline (P50) ---
    op.create_table(
        "talent_pipeline",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employer_id",
            sa.Integer(),
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pipeline_status",
            sa.String(50),
            nullable=False,
            server_default="warm_lead",
        ),
        sa.Column(
            "source_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "last_contacted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "next_followup_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "consent_given", sa.Boolean(), server_default="false"
        ),
        sa.Column(
            "consent_date", sa.DateTime(timezone=True), nullable=True
        ),
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
        sa.UniqueConstraint(
            "employer_id",
            "candidate_profile_id",
            name="uq_pipeline_employer_candidate",
        ),
    )
    op.create_index(
        "ix_talent_pipeline_employer_id",
        "talent_pipeline",
        ["employer_id"],
    )
    op.create_index(
        "ix_talent_pipeline_candidate_profile_id",
        "talent_pipeline",
        ["candidate_profile_id"],
    )
    op.create_index(
        "ix_talent_pipeline_status",
        "talent_pipeline",
        ["pipeline_status"],
    )

    # --- employer_team_members (P53) ---
    op.create_table(
        "employer_team_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employer_id",
            sa.Integer(),
            sa.ForeignKey("employer_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role", sa.String(50), nullable=False, server_default="viewer"
        ),
        sa.Column("job_access", postgresql.JSONB(), nullable=True),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "accepted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employer_team_members_employer_id",
        "employer_team_members",
        ["employer_id"],
    )

    # --- interview_feedback (P53) ---
    op.create_table(
        "interview_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "employer_job_id",
            sa.Integer(),
            sa.ForeignKey("employer_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_profile_id",
            sa.Integer(),
            sa.ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interviewer_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "interview_type",
            sa.String(50),
            nullable=False,
            server_default="phone_screen",
        ),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("recommendation", sa.String(50), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("concerns", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_feedback_job_id",
        "interview_feedback",
        ["employer_job_id"],
    )


def downgrade() -> None:
    op.drop_table("interview_feedback")
    op.drop_table("employer_team_members")
    op.drop_table("talent_pipeline")
    op.drop_table("employer_compliance_log")
    op.drop_table("candidate_notifications")
