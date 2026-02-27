"""Debug trajectory parsing."""

import json
import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

engine = create_engine(
    os.getenv(
        "DB_URL",
        "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch",
    )
)

from app.models.career_intelligence import CareerTrajectory

with Session(engine) as s:
    ct = s.execute(
        select(CareerTrajectory).order_by(CareerTrajectory.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not ct:
        print("No records")
        exit()
    raw = ct.trajectory_json.get("raw_prediction", "")
    print(f"starts with: {repr(raw[:40])}")
    print(f"ends with: {repr(raw[-40:])}")
    stripped = raw.strip("`").removeprefix("json").strip()
    print(f"stripped starts: {repr(stripped[:60])}")
    print(f"stripped ends: {repr(stripped[-40:])}")
    try:
        parsed = json.loads(stripped)
        print(f"Parse OK, keys: {list(parsed.keys())}")
    except json.JSONDecodeError as e:
        print(f"Parse FAIL: {e}")
