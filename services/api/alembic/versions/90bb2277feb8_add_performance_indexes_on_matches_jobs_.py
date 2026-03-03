"""add performance indexes on matches jobs candidate_profiles

Revision ID: 90bb2277feb8
Revises: 9005bcb85b82
Create Date: 2026-03-03 08:39:34.602382

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "90bb2277feb8"
down_revision: Union[str, None] = "9005bcb85b82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_matches_user_created", "matches", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_jobs_source_source_job_id", "jobs", ["source", "source_job_id"]
    )
    op.create_index("ix_jobs_is_active", "jobs", ["is_active"])
    op.create_index(
        "ix_candidate_profiles_user_version",
        "candidate_profiles",
        ["user_id", "version"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_profiles_user_version", table_name="candidate_profiles")
    op.drop_index("ix_jobs_is_active", table_name="jobs")
    op.drop_index("ix_jobs_source_source_job_id", table_name="jobs")
    op.drop_index("ix_matches_user_created", table_name="matches")
