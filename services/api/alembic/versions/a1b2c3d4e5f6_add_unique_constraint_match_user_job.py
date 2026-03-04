"""add unique constraint on matches(user_id, job_id)

Revision ID: a1b2c3d4e5f6
Revises: 90bb2277feb8
Create Date: 2026-03-03 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "90bb2277feb8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate (user_id, job_id) rows before adding the constraint.
    # Keep the row with the highest id (most recent) for each pair.
    op.execute(
        """
        DELETE FROM matches
        WHERE id NOT IN (
            SELECT MAX(id) FROM matches GROUP BY user_id, job_id
        )
        """
    )
    op.create_unique_constraint("uq_match_user_job", "matches", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_constraint("uq_match_user_job", "matches", type_="unique")
