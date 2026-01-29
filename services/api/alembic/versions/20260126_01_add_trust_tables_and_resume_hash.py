"""add trust tables and resume hash

Revision ID: 20260126_01
Revises: 20260125_01
Create Date: 2026-01-26 06:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260126_01"
down_revision = "20260125_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resume_documents", sa.Column("sha256", sa.String(length=64), nullable=True))

    op.create_table(
        "candidate_trust",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resume_document_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("allowed", "soft_quarantine", "hard_quarantine", name="trust_status"),
            nullable=False,
        ),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["resume_document_id"], ["resume_documents.id"]),
    )

    op.create_table(
        "trust_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trust_id", sa.Integer(), nullable=False),
        sa.Column(
            "actor_type",
            sa.Enum("system", "candidate", "admin", name="trust_actor_type"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("prev_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["trust_id"], ["candidate_trust.id"]),
    )


def downgrade() -> None:
    op.drop_table("trust_audit_log")
    op.drop_table("candidate_trust")
    op.drop_column("resume_documents", "sha256")

    sa.Enum("system", "candidate", "admin", name="trust_actor_type").drop(op.get_bind())
    sa.Enum("allowed", "soft_quarantine", "hard_quarantine", name="trust_status").drop(
        op.get_bind()
    )
