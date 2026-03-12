"""Deduplicate candidate_profiles that share the same email.

For each email with multiple profiles:
  1. Pick the "best" profile (most skills, has resume, lowest ID as tiebreak)
  2. Re-point all recruiter_pipeline_candidates to the keeper
  3. Delete duplicate profiles (CASCADE handles recruiter_job_candidates, etc.)

Usage:
    cd services/api
    python scripts/deduplicate_profiles.py --dry-run   # preview
    python scripts/deduplicate_profiles.py              # execute
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dotenv; dotenv.load_dotenv()

from sqlalchemy import text
from app.db.session import get_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    Session = get_session_factory()
    session = Session()

    # Step 1: Find all duplicate email groups
    logger.info("Finding duplicate email groups...")
    dupe_groups = session.execute(text("""
        SELECT profile_json->'basics'->>'email' as email,
               array_agg(id ORDER BY id) as ids
        FROM candidate_profiles
        WHERE user_id IS NULL
          AND profile_json->'basics'->>'email' IS NOT NULL
          AND profile_json->'basics'->>'email' <> ''
        GROUP BY profile_json->'basics'->>'email'
        HAVING COUNT(*) > 1
    """)).fetchall()

    logger.info("Found %d email groups with duplicates", len(dupe_groups))

    total_deleted = 0
    total_repointed = 0

    for email, ids in dupe_groups:
        # Step 2: Pick the best profile (most skills, then lowest ID)
        profiles = session.execute(text("""
            SELECT id,
                   resume_document_id,
                   jsonb_array_length(COALESCE(profile_json->'skills', '[]'::jsonb)) as skill_count,
                   jsonb_array_length(COALESCE(profile_json->'experience', '[]'::jsonb)) as exp_count,
                   embedding IS NOT NULL as has_embedding
            FROM candidate_profiles
            WHERE id = ANY(:ids)
            ORDER BY
                (embedding IS NOT NULL) DESC,
                jsonb_array_length(COALESCE(profile_json->'skills', '[]'::jsonb)) DESC,
                (resume_document_id IS NOT NULL) DESC,
                id ASC
        """), {"ids": ids}).fetchall()

        keeper_id = profiles[0][0]
        dupe_ids = [p[0] for p in profiles[1:]]

        if args.dry_run:
            logger.info("  %s: keep %d (skills=%d, exp=%d, emb=%s), delete %d dupes",
                        email, keeper_id, profiles[0][2], profiles[0][3], profiles[0][4],
                        len(dupe_ids))
        else:
            # Step 3: Re-point pipeline candidates from dupes to keeper
            for dupe_id in dupe_ids:
                updated = session.execute(text("""
                    UPDATE recruiter_pipeline_candidates
                    SET candidate_profile_id = :keeper
                    WHERE candidate_profile_id = :dupe
                      AND id NOT IN (
                          SELECT id FROM recruiter_pipeline_candidates
                          WHERE candidate_profile_id = :keeper
                      )
                """), {"keeper": keeper_id, "dupe": dupe_id}).rowcount
                total_repointed += updated

                # For pipeline candidates that already point to keeper,
                # just NULL out the dupe reference (avoid unique constraint issues)
                session.execute(text("""
                    UPDATE recruiter_pipeline_candidates
                    SET candidate_profile_id = NULL
                    WHERE candidate_profile_id = :dupe
                """), {"dupe": dupe_id})

            # Step 4: Delete duplicate profiles (CASCADE handles FK children)
            deleted = session.execute(text("""
                DELETE FROM candidate_profiles
                WHERE id = ANY(:dupe_ids)
            """), {"dupe_ids": dupe_ids}).rowcount
            total_deleted += deleted

        if not args.dry_run and (total_deleted % 500 == 0) and total_deleted > 0:
            session.commit()
            logger.info("  Committed at %d deleted...", total_deleted)

    if not args.dry_run:
        session.commit()

    logger.info("=== Done ===")
    logger.info("  Duplicate profiles deleted: %d", total_deleted)
    logger.info("  Pipeline candidates re-pointed: %d", total_repointed)

    # Final counts
    remaining = session.execute(text(
        "SELECT COUNT(*) FROM candidate_profiles WHERE user_id IS NULL"
    )).scalar()
    unique_emails = session.execute(text(
        "SELECT COUNT(DISTINCT profile_json->'basics'->>'email') FROM candidate_profiles "
        "WHERE user_id IS NULL AND profile_json->'basics'->>'email' IS NOT NULL"
    )).scalar()
    logger.info("  Remaining sourced profiles: %d", remaining)
    logger.info("  Unique emails: %d", unique_emails)

    session.close()


if __name__ == "__main__":
    main()
