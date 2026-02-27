import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DB_URL", "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    row = (
        conn.execute(
            text(
                "SELECT id, user_id, profile_json "
                "FROM candidate_profiles "
                "ORDER BY id DESC LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    if row:
        p = (
            row["profile_json"]
            if isinstance(row["profile_json"], dict)
            else json.loads(row["profile_json"])
        )
        print("User:", row["user_id"])
        print("Basics:", json.dumps(p.get("basics", {}), indent=2))
        exps = p.get("experience", [])
        for i, e in enumerate(exps):
            print(
                f"Exp {i}: {e.get('company')}"
                f" | start={e.get('start_date')}"
                f" | end={e.get('end_date')}"
            )
