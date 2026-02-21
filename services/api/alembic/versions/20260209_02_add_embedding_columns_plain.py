"""add embedding columns as plain arrays (pgvector not available)

Revision ID: 20260209_02
Revises: 20260209_01
Create Date: 2026-02-09

The pgvector migration (20260208_01) was stamped but never ran because
the vector extension is not installed. This adds the columns the ORM
models expect as regular nullable columns so queries don't fail.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260209_02"
down_revision: str | None = "20260209_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add embedding as a plain JSON column (stores array of floats)
    op.add_column(
        "jobs",
        sa.Column("embedding", sa.JSON(), nullable=True),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("embedding", sa.JSON(), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column("semantic_similarity", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matches", "semantic_similarity")
    op.drop_column("candidate_profiles", "embedding")
    op.drop_column("jobs", "embedding")
