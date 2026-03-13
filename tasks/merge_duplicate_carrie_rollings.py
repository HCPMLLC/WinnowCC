"""One-time script: merge duplicate candidate_profile records.

Keeps the richer record, reassigns all FK references from the duplicate,
then deletes the duplicate profile and its placeholder user.

Usage:
    cd services/api
    .venv/Scripts/python.exe ../../tasks/merge_duplicate_carrie_rollings.py --dry-run
    .venv/Scripts/python.exe ../../tasks/merge_duplicate_carrie_rollings.py
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add services/api to path so we can import app modules
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "services", "api")
)

# Load env vars from services/api/.env
_api_dir = Path(__file__).resolve().parent.parent / "services" / "api"
load_dotenv(_api_dir / ".env", override=False)

from sqlalchemy import text  # noqa: E402

from app.db.session import get_session_factory  # noqa: E402

DEFAULT_ID_A = 15541
DEFAULT_ID_B = 23970

# All tables with a candidate_profile_id FK
FK_TABLES = [
    ("employer_job_candidates", "candidate_profile_id"),
    ("employer_outreach_enrollments", "candidate_profile_id"),
    ("candidate_submissions", "candidate_profile_id"),
    ("recruiter_marketplace_matches", "candidate_profile_id"),
    ("recruiter_pipeline_candidates", "candidate_profile_id"),
    ("employer_introduction_requests", "candidate_profile_id"),
    ("introduction_requests", "candidate_profile_id"),
    ("recruiter_job_candidates", "candidate_profile_id"),
    ("recruiter_candidate_briefs", "candidate_profile_id"),
    ("career_trajectories", "candidate_profile_id"),
    ("talent_pipeline", "candidate_profile_id"),
    ("interview_feedback", "candidate_profile_id"),
    ("employer_candidate_views", "candidate_id"),
    ("employer_saved_candidates", "candidate_id"),
]

JSONB_TABLE = "employer_submittal_packages"


def pick_keeper(db, id_a, id_b):
    """Compare both profiles and return (keep_id, delete_id)."""
    rows = db.execute(
        text(
            "SELECT id, user_id, profile_json, updated_at "
            "FROM candidate_profiles WHERE id IN (:a, :b)"
        ),
        {"a": id_a, "b": id_b},
    ).fetchall()

    if len(rows) != 2:
        found = [r[0] for r in rows]
        print(
            f"ERROR: Expected 2 profiles, found {len(rows)}: {found}"
        )
        sys.exit(1)

    profiles = {r[0]: r for r in rows}
    a = profiles[id_a]
    b = profiles[id_b]

    def richness(row):
        pj = row[2] or {}
        score = 0
        for key in (
            "experience", "education", "skills",
            "certifications", "volunteer", "projects",
            "publications",
        ):
            items = pj.get(key, [])
            score += len(items) if isinstance(items, list) else 0
        basics = pj.get("basics", {})
        for field in ("email", "phone", "headline", "location"):
            if basics.get(field):
                score += 1
        if pj.get("about"):
            score += 1
        if pj.get("contact_info"):
            score += 1
        return score

    ra, rb = richness(a), richness(b)
    print(f"Profile {id_a}: richness={ra}, updated={a[3]}")
    print(f"Profile {id_b}: richness={rb}, updated={b[3]}")

    # Keep the richer one; tie-break by older (lower ID)
    if ra >= rb:
        return id_a, id_b
    return id_b, id_a


def merge(id_a, id_b, dry_run=True):
    db = get_session_factory()()
    try:
        keep_id, delete_id = pick_keeper(db, id_a, id_b)
        print(
            f"\nKeeping profile {keep_id}, "
            f"merging from & deleting profile {delete_id}"
        )

        # 1. Merge unique data from delete_id into keep_id
        row = db.execute(
            text(
                "SELECT profile_json FROM candidate_profiles "
                "WHERE id = :id"
            ),
            {"id": keep_id},
        ).fetchone()
        keep_json = row[0] or {}

        row = db.execute(
            text(
                "SELECT profile_json FROM candidate_profiles "
                "WHERE id = :id"
            ),
            {"id": delete_id},
        ).fetchone()
        delete_json = row[0] or {}

        # Merge basics fields that are missing in keeper
        keep_basics = keep_json.get("basics", {})
        delete_basics = delete_json.get("basics", {})
        for field, val in delete_basics.items():
            if val and not keep_basics.get(field):
                keep_basics[field] = val
        keep_json["basics"] = keep_basics

        # Merge top-level fields that are missing
        for field in ("about", "contact_info", "photo_url"):
            if delete_json.get(field) and not keep_json.get(field):
                keep_json[field] = delete_json[field]

        if not dry_run:
            db.execute(
                text(
                    "UPDATE candidate_profiles "
                    "SET profile_json = :pj WHERE id = :id"
                ),
                {"pj": keep_json, "id": keep_id},
            )
        print(f"  Merged profile_json fields into {keep_id}")

        # 2. Reassign FK references
        for table, col in FK_TABLES:
            count = db.execute(
                text(
                    f"SELECT COUNT(*) FROM {table} "
                    f"WHERE {col} = :did"
                ),
                {"did": delete_id},
            ).scalar()
            if count:
                print(
                    f"  {table}.{col}: "
                    f"{count} rows -> reassign to {keep_id}"
                )
                if not dry_run:
                    # Remove conflicts first, then reassign
                    db.execute(
                        text(
                            f"DELETE FROM {table} "
                            f"WHERE {col} = :did "
                            f"AND EXISTS ("
                            f"SELECT 1 FROM {table} t2 "
                            f"WHERE t2.{col} = :kid "
                            f"AND t2.id != {table}.id)"
                        ),
                        {"did": delete_id, "kid": keep_id},
                    )
                    db.execute(
                        text(
                            f"UPDATE {table} "
                            f"SET {col} = :kid "
                            f"WHERE {col} = :did"
                        ),
                        {"kid": keep_id, "did": delete_id},
                    )

        # 3. Handle JSONB list in submittal packages
        pkg_count = db.execute(
            text(
                f"SELECT COUNT(*) FROM {JSONB_TABLE} "
                f"WHERE candidate_profile_ids @> :arr::jsonb"
            ),
            {"arr": f"[{delete_id}]"},
        ).scalar()
        if pkg_count:
            print(
                f"  {JSONB_TABLE}: {pkg_count} rows "
                f"contain {delete_id} in JSONB array"
            )
            if not dry_run:
                db.execute(
                    text(
                        f"UPDATE {JSONB_TABLE} "
                        f"SET candidate_profile_ids = "
                        f"(SELECT jsonb_agg(DISTINCT v) FROM ("
                        f"  SELECT CASE "
                        f"    WHEN v::int = :did "
                        f"    THEN :kid::int "
                        f"    ELSE v::int END AS v "
                        f"  FROM jsonb_array_elements_text("
                        f"candidate_profile_ids) AS v"
                        f") sub) "
                        f"WHERE candidate_profile_ids "
                        f"@> :arr::jsonb"
                    ),
                    {
                        "did": delete_id,
                        "kid": keep_id,
                        "arr": f"[{delete_id}]",
                    },
                )

        # 4. Get the user_id of the profile to delete
        del_user_id = db.execute(
            text(
                "SELECT user_id FROM candidate_profiles "
                "WHERE id = :id"
            ),
            {"id": delete_id},
        ).scalar()

        # 5. Delete the duplicate profile
        print(f"  Deleting candidate_profile {delete_id}")
        if not dry_run:
            db.execute(
                text(
                    "DELETE FROM candidate_profiles WHERE id = :id"
                ),
                {"id": delete_id},
            )

        # 6. Delete placeholder user if sourced
        if del_user_id:
            del_email = db.execute(
                text("SELECT email FROM users WHERE id = :id"),
                {"id": del_user_id},
            ).scalar()
            if del_email and del_email.endswith("@sourced.winnow"):
                other = db.execute(
                    text(
                        "SELECT COUNT(*) FROM candidate_profiles "
                        "WHERE user_id = :uid"
                    ),
                    {"uid": del_user_id},
                ).scalar()
                if other == 0:
                    print(
                        f"  Deleting placeholder user "
                        f"{del_user_id} ({del_email})"
                    )
                    if not dry_run:
                        db.execute(
                            text(
                                "DELETE FROM users "
                                "WHERE id = :id"
                            ),
                            {"id": del_user_id},
                        )

        if dry_run:
            print(
                "\n** DRY RUN -- no changes made. "
                "Run without --dry-run to execute. **"
            )
            db.rollback()
        else:
            db.commit()
            print("\nDone! Duplicate merged and deleted.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge duplicate candidate_profile records",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    parser.add_argument(
        "--id-a",
        type=int,
        default=DEFAULT_ID_A,
        help=f"First profile ID (default: {DEFAULT_ID_A})",
    )
    parser.add_argument(
        "--id-b",
        type=int,
        default=DEFAULT_ID_B,
        help=f"Second profile ID (default: {DEFAULT_ID_B})",
    )
    args = parser.parse_args()
    merge(args.id_a, args.id_b, dry_run=args.dry_run)
