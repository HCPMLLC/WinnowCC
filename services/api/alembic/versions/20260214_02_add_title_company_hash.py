"""Add title_company_hash column for cross-source dedup.

Revision ID: 20260214_02
Revises: 20260214_01
Create Date: 2026-02-14
"""

import hashlib

import sqlalchemy as sa

from alembic import op

revision = "20260214_02"
down_revision = "20260214_01"
branch_labels = None
depends_on = None


def _fingerprint_hash(title: str, company: str) -> str:
    norm = "|".join(
        [
            " ".join((title or "").lower().split()),
            " ".join((company or "").lower().split()),
        ]
    )
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("title_company_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_jobs_title_company_hash", "jobs", ["title_company_hash"]
    )

    # Backfill existing rows
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, title, company FROM jobs")
    ).fetchall()
    for row in rows:
        h = _fingerprint_hash(row.title, row.company)
        conn.execute(
            sa.text("UPDATE jobs SET title_company_hash = :h WHERE id = :id"),
            {"h": h, "id": row.id},
        )


def downgrade() -> None:
    op.drop_index("ix_jobs_title_company_hash", table_name="jobs")
    op.drop_column("jobs", "title_company_hash")
