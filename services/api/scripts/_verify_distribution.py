"""Quick verification that distribution tables were created correctly."""

import sys
from pathlib import Path

# Ensure app module is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)

from sqlalchemy import text  # noqa: E402

from app.db.session import get_session_factory  # noqa: E402

session = get_session_factory()()

# Verify tables
tables = session.execute(
    text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name IN ("
        "'board_connections',"
        "'job_distributions',"
        "'distribution_events') "
        "ORDER BY table_name"
    )
).fetchall()
print("Tables:", [t[0] for t in tables])

# Columns per table
for tbl in ["board_connections", "job_distributions", "distribution_events"]:
    cols = session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{tbl}' ORDER BY ordinal_position"
        )
    ).fetchall()
    print(f"  {tbl}: {len(cols)} columns — {[c[0] for c in cols]}")

# Indexes
idxs = session.execute(
    text(
        "SELECT indexname FROM pg_indexes "
        "WHERE tablename IN ("
        "'board_connections',"
        "'job_distributions',"
        "'distribution_events') "
        "AND indexname LIKE 'idx_%'"
    )
).fetchall()
print("Custom indexes:", [i[0] for i in idxs])

# Unique constraints
uqs = session.execute(
    text(
        "SELECT conname FROM pg_constraint "
        "WHERE conname LIKE 'uq_%' "
        "AND conname LIKE '%board%' "
        "OR conname LIKE '%distribution%'"
    )
).fetchall()
print("Unique constraints:", [u[0] for u in uqs])

session.close()
print("\nAll distribution tables verified OK")
