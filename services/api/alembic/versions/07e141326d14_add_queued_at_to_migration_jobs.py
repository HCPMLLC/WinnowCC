"""add queued_at to migration_jobs

Revision ID: 07e141326d14
Revises: e6bf81254774
Create Date: 2026-03-02 10:01:12.866052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '07e141326d14'
down_revision: Union[str, None] = 'e6bf81254774'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'migration_jobs',
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_migration_jobs_queued_fifo',
        'migration_jobs',
        ['queued_at'],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    op.drop_index('ix_migration_jobs_queued_fifo', table_name='migration_jobs')
    op.drop_column('migration_jobs', 'queued_at')
