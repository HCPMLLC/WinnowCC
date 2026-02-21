"""Quick DB diagnostics."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from app.db.session import get_session_factory
from sqlalchemy import text

s = get_session_factory()()

total = s.execute(text("SELECT COUNT(*) FROM jobs")).scalar()
active = s.execute(text("SELECT COUNT(*) FROM jobs WHERE is_active = true")).scalar()
print(f"Total jobs: {total}, Active: {active}")

dupes = s.execute(text(
    "SELECT content_hash, COUNT(*) c FROM jobs GROUP BY content_hash HAVING COUNT(*) > 1 LIMIT 10"
)).fetchall()
print(f"Duplicate content_hash groups: {len(dupes)}")
for row in dupes:
    print(f"  hash={row[0][:16]}... count={row[1]}")

by_source = s.execute(text(
    "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC"
)).fetchall()
print("By source:")
for row in by_source:
    print(f"  {row[0]}: {row[1]}")

s.close()
