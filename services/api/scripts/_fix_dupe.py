"""Fix duplicate content_hash rows by deleting the newer duplicate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import text

from app.db.session import get_session_factory

s = get_session_factory()()

dupes = s.execute(
    text("SELECT content_hash FROM jobs GROUP BY content_hash HAVING COUNT(*) > 1")
).fetchall()

for (ch,) in dupes:
    rows = s.execute(
        text("SELECT id FROM jobs WHERE content_hash = :h ORDER BY id"), {"h": ch}
    ).fetchall()
    # Keep the first, delete the rest
    for row in rows[1:]:
        print(f"Deleting duplicate job id={row[0]} with hash={ch[:16]}...")
        s.execute(
            text("DELETE FROM job_parsed_details WHERE job_id = :id"), {"id": row[0]}
        )
        s.execute(text("DELETE FROM matches WHERE job_id = :id"), {"id": row[0]})
        s.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": row[0]})

s.commit()
print("Done. Duplicates cleaned.")
s.close()
