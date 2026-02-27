"""Quick verification that title_company_hash backfill completed."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    total = conn.execute(text("SELECT count(*) FROM jobs")).scalar()
    nulls = conn.execute(
        text("SELECT count(*) FROM jobs WHERE title_company_hash IS NULL")
    ).scalar()
    print(f"Total jobs: {total}")
    print(f"NULL title_company_hash: {nulls}")
    rows = conn.execute(
        text(
            "SELECT id, title, company, substring(title_company_hash,1,16) "
            "FROM jobs LIMIT 3"
        )
    ).fetchall()
    for r in rows:
        print(f"  Job #{r[0]}: {r[1]} @ {r[2]} -> {r[3]}...")
