"""Add FK constraint on candidate_profiles.resume_document_id.

Revision ID: 20260225_02
Revises: 20260225_01
"""

from alembic import op

revision = "20260225_02"
down_revision = "20260225_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean orphaned references first
    op.execute(
        "UPDATE candidate_profiles SET resume_document_id = NULL "
        "WHERE resume_document_id IS NOT NULL "
        "AND resume_document_id NOT IN (SELECT id FROM resume_documents)"
    )
    # Add FK constraint (idempotent check)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_candidate_profiles_resume_document_id'
                  AND table_name = 'candidate_profiles'
            ) THEN
                ALTER TABLE candidate_profiles
                ADD CONSTRAINT fk_candidate_profiles_resume_document_id
                FOREIGN KEY (resume_document_id) REFERENCES resume_documents(id)
                ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE candidate_profiles
        DROP CONSTRAINT IF EXISTS fk_candidate_profiles_resume_document_id;
        """
    )
