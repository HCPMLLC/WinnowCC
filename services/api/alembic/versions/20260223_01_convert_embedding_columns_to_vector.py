"""convert embedding columns from JSON to pgvector Vector type

Revision ID: 20260223_01
Revises: 20260222_01
Create Date: 2026-02-23

The previous migration (20260209_02) added embedding columns as plain JSON
because pgvector was not available locally. Now that we use the pgvector
Docker image, convert them to proper Vector(384) columns with HNSW indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260223_01"
down_revision: str | None = "20260222_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Drop existing JSON-typed embedding columns and recreate as Vector
    op.drop_column("jobs", "embedding")
    op.drop_column("candidate_profiles", "embedding")

    # Re-add as Vector(384)
    op.execute("ALTER TABLE jobs ADD COLUMN embedding vector(384)")
    op.execute("ALTER TABLE candidate_profiles ADD COLUMN embedding vector(384)")

    # Create HNSW indexes for fast approximate nearest-neighbor search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_embedding
        ON jobs
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_profiles_embedding
        ON candidate_profiles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_profiles_embedding")
    op.execute("DROP INDEX IF EXISTS idx_jobs_embedding")
    op.drop_column("candidate_profiles", "embedding")
    op.drop_column("jobs", "embedding")
    # Re-add as plain JSON (restore previous state)
    op.add_column("jobs", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column(
        "candidate_profiles", sa.Column("embedding", sa.JSON(), nullable=True)
    )
