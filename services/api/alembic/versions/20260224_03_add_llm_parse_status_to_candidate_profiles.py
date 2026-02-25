"""Add llm_parse_status to candidate_profiles.

Revision ID: 20260224_03
"""

import sqlalchemy as sa
from alembic import op

revision = "20260224_03"
down_revision = "20260224_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Idempotent: only add column if it doesn't already exist
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'candidate_profiles' "
            "AND column_name = 'llm_parse_status'"
        )
    )
    if not result.fetchone():
        op.add_column(
            "candidate_profiles",
            sa.Column("llm_parse_status", sa.String(20), nullable=True),
        )
    # Idempotent: only create index if it doesn't already exist
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE indexname = 'ix_cp_llm_parse_status'"
        )
    )
    if not result.fetchone():
        op.create_index(
            "ix_cp_llm_parse_status",
            "candidate_profiles",
            ["llm_parse_status"],
        )


def downgrade() -> None:
    op.drop_index("ix_cp_llm_parse_status", table_name="candidate_profiles")
    op.drop_column("candidate_profiles", "llm_parse_status")
