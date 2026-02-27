import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DB_URL", "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)
from sqlalchemy import create_engine, text


def format_phone(value):
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return value


engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
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
        p = (
            row["profile_json"]
            if isinstance(row["profile_json"], dict)
            else json.loads(row["profile_json"])
        )
        old_phone = p["basics"].get("phone", "")
        new_phone = format_phone(old_phone) if old_phone else old_phone
        p["basics"]["phone"] = new_phone
        conn.execute(
            text(
                "UPDATE candidate_profiles "
                "SET profile_json = CAST(:pj AS jsonb) "
                "WHERE user_id = 10"
            ),
            {"pj": json.dumps(p)},
        )
        conn.commit()
        print(f"Phone: {old_phone!r} -> {new_phone!r}")
