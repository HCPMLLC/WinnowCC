import argparse
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text


def _load_db_url() -> str:
    db_url = os.getenv("DB_URL", "").strip()
    if db_url:
        return db_url
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("DB_URL="):
                    return line.strip().split("=", 1)[1]
    raise RuntimeError("DB_URL is not set.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge stale jobs and dependent records."
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Keep jobs from last N days."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show counts without deleting."
    )
    args = parser.parse_args()

    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    db_url = _load_db_url()
    engine = create_engine(db_url)

    with engine.begin() as conn:
        job_ids = conn.execute(
            text("select id from jobs where posted_at is null or posted_at < :cutoff"),
            {"cutoff": cutoff},
        ).fetchall()
        stale_ids = [row[0] for row in job_ids]

        if not stale_ids:
            print("No stale jobs found.")
            return 0

        params = {"ids": stale_ids}
        match_count = conn.execute(
            text("select count(*) from matches where job_id = any(:ids)"), params
        ).scalar_one()
        resume_count = conn.execute(
            text("select count(*) from tailored_resumes where job_id = any(:ids)"),
            params,
        ).scalar_one()

        print(
            f"Stale jobs: {len(stale_ids)}"
            f" | Matches: {match_count}"
            f" | Tailored: {resume_count}"
        )

        if args.dry_run:
            return 0

        conn.execute(text("delete from matches where job_id = any(:ids)"), params)
        conn.execute(
            text("delete from tailored_resumes where job_id = any(:ids)"), params
        )
        conn.execute(text("delete from jobs where id = any(:ids)"), params)
        print("Deleted stale jobs and dependent records.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
