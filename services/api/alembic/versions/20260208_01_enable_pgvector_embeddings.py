"""enable pgvector and add embedding columns

Revision ID: 20260208_01
Revises: ea5d6435ed5e
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260208_01"
down_revision: str | None = "ea5d6435ed5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add embedding columns
    op.add_column("jobs", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column(
        "candidate_profiles", sa.Column("embedding", Vector(384), nullable=True)
    )

    # Add semantic_similarity to matches
    op.add_column(
        "matches", sa.Column("semantic_similarity", sa.Float(), nullable=True)
    )

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
    op.drop_column("matches", "semantic_similarity")
    op.drop_column("candidate_profiles", "embedding")
    op.drop_column("jobs", "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
