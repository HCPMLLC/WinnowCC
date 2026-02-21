"""
Bulk job seeder for Winnow.

Usage::

    python scripts/seed_jobs.py [--categories all|tech|...]
                                [--max-per-source 100]
                                [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import get_session_factory
from app.services.job_ingestion import ingest_jobs
from app.services.job_sources import get_job_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEED_CATEGORIES = {
    "tech": {"search": "software engineer"},
    "project_management": {"search": "project manager"},
    "business": {"search": "business strategy"},
    "marketing": {"search": "marketing"},
    "data": {"search": "data science"},
    "design": {"search": "design UX"},
    "finance": {"search": "finance"},
    "healthcare": {"search": "healthcare"},
}


def seed_jobs(categories: list[str], max_per_source: int, dry_run: bool) -> None:
    session = get_session_factory()()
    total_fetched = 0
    total_new = 0
    total_errors = 0

    try:
        for cat_name in categories:
            if cat_name not in SEED_CATEGORIES:
                logger.warning("Unknown category: %s, skipping", cat_name)
                continue

            logger.info("Category: %s", cat_name)
            query = dict(SEED_CATEGORIES[cat_name])

            try:
                if dry_run:
                    sources = get_job_sources()
                    for source in sources:
                        try:
                            postings = source.fetch_jobs(query)
                            count = min(len(postings), max_per_source)
                            logger.info(
                                "  %s: would fetch %d jobs (dry-run)",
                                source.name,
                                count,
                            )
                            total_fetched += count
                        except Exception as exc:
                            logger.error("  %s: error — %s", source.name, exc)
                            total_errors += 1
                else:
                    new = ingest_jobs(session, query)
                    total_new += new
                    total_fetched += new
                    logger.info("  %d new jobs ingested for %s", new, cat_name)
            except Exception as exc:
                logger.error("  %s: error — %s", cat_name, exc)
                total_errors += 1

        logger.info("=" * 50)
        logger.info("SEED COMPLETE")
        logger.info("  Total new inserted: %d", total_new)
        logger.info("  Errors:             %d", total_errors)
        logger.info("=" * 50)

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Bulk job seeder for Winnow")
    parser.add_argument(
        "--categories",
        default="all",
        help="Comma-separated list of categories, or 'all'",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=100,
        help="Maximum jobs to fetch per source per category",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate but do not insert",
    )
    args = parser.parse_args()

    if args.categories == "all":
        categories = list(SEED_CATEGORIES.keys())
    else:
        categories = [c.strip() for c in args.categories.split(",")]

    logger.info("Starting bulk ingestion...")
    logger.info("Categories: %s", ", ".join(categories))
    logger.info("Max per source: %d", args.max_per_source)
    logger.info("Dry run: %s", args.dry_run)

    seed_jobs(categories, args.max_per_source, args.dry_run)


if __name__ == "__main__":
    main()
