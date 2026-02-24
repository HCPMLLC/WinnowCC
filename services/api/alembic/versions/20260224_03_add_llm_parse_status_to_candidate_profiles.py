"""Add llm_parse_status to candidate_profiles.

Revision ID: 20260224_03
"""

import sqlalchemy as sa
from alembic import op

revision = "20260224_03"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("llm_parse_status", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_cp_llm_parse_status",
        "candidate_profiles",
        ["llm_parse_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_cp_llm_parse_status", table_name="candidate_profiles")
    op.drop_column("candidate_profiles", "llm_parse_status")
