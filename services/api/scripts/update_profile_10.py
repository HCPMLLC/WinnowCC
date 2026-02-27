import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DB_URL", "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)
from pathlib import Path

from sqlalchemy import create_engine, text

from app.services.profile_parser import extract_text, parse_profile_from_text

path = Path(
    r"C:\Users\ronle\Documents\resumematch\services\api"
    r"\data\uploads"
    r"\b2b2b7ca627548018f0814a39e485fb8"
    r"_Frances W Levi Resume 2019.docx"
)
raw = extract_text(path)
new_profile = parse_profile_from_text(raw)

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    # Get existing profile to preserve user edits (preferences, skill_categories, etc.)
    row = (
        conn.execute(
            text(
                "SELECT profile_json "
                "FROM candidate_profiles "
                "WHERE user_id = 10 "
                "ORDER BY id DESC LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    if row:
        existing = (
            row["profile_json"]
            if isinstance(row["profile_json"], dict)
            else json.loads(row["profile_json"])
        )
        # Merge: update basics fields from parser, keep everything else
        for key in ("first_name", "last_name", "location", "total_years_experience"):
            val = new_profile["basics"].get(key)
            if val is not None:
                existing["basics"][key] = val
        conn.execute(
            text(
                "UPDATE candidate_profiles "
                "SET profile_json = CAST(:pj AS jsonb) "
                "WHERE user_id = 10"
            ),
            {"pj": json.dumps(existing)},
        )
        conn.commit()
        print("Updated profile for user 10")
        print("  location:", existing["basics"].get("location"))
        print(
            "  total_years_experience:",
            existing["basics"].get("total_years_experience"),
        )
    else:
        print("No profile found for user 10")
