"""Backfill embeddings for candidate profiles that have resume data but no embedding.

Usage:
    cd services/api
    python scripts/backfill_embeddings.py
    python scripts/backfill_embeddings.py --limit 100  # test with subset
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dotenv
dotenv.load_dotenv()

from sqlalchemy import text
from app.db.session import get_session_factory
from app.services.embedding import generate_embeddings, prepare_profile_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=128)
    args = parser.parse_args()

    Session = get_session_factory()
    session = Session()

    query = (
        "SELECT id, profile_json FROM candidate_profiles "
        "WHERE embedding IS NULL AND resume_document_id IS NOT NULL "
        "ORDER BY id"
    )
    if args.limit > 0:
        query += f" LIMIT {args.limit}"

    rows = session.execute(text(query)).fetchall()
    logger.info("Profiles needing embeddings: %d", len(rows))

    if not rows:
        logger.info("Nothing to do.")
        session.close()
        return

    start = time.time()
    done = 0
    skipped = 0

    for i in range(0, len(rows), args.batch_size):
        batch = rows[i : i + args.batch_size]
        texts = []
        ids = []
        for row in batch:
            pj = row[1] if isinstance(row[1], dict) else json.loads(row[1])
            t = prepare_profile_text(pj)
            if t.strip():
                texts.append(t)
                ids.append(row[0])
            else:
                skipped += 1

        if not texts:
            continue

        embeddings = generate_embeddings(texts)

        for pid, emb in zip(ids, embeddings):
            emb_str = "[" + ",".join(str(x) for x in emb) + "]"
            session.execute(
                text("UPDATE candidate_profiles SET embedding = :emb WHERE id = :pid"),
                {"emb": emb_str, "pid": pid},
            )

        session.commit()
        done += len(ids)

        elapsed = time.time() - start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(rows) - done - skipped) / rate if rate > 0 else 0
        logger.info(
            "  Embedded %d/%d | %.0f/sec | ETA %.0fs",
            done, len(rows), rate, eta,
        )

    elapsed = time.time() - start
    logger.info("=== Done ===")
    logger.info("  Embedded: %d", done)
    logger.info("  Skipped (empty text): %d", skipped)
    logger.info("  Time: %.1fs (%.0f/sec)", elapsed, done / elapsed if elapsed > 0 else 0)
    session.close()


if __name__ == "__main__":
    main()
