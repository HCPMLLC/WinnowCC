"""add sha256 index to upload_batch_files

Revision ID: a62e952af39e
Revises: 161370905dc9
Create Date: 2026-03-02 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a62e952af39e"
down_revision: str | None = "161370905dc9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_upload_batch_files_sha256",
        "upload_batch_files",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_upload_batch_files_sha256", table_name="upload_batch_files")
