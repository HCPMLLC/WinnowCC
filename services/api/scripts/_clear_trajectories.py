"""Delete all career trajectory records so fresh ones are generated."""
import os
from sqlalchemy import create_engine, text

engine = create_engine(
    os.getenv("DB_URL", "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch")
)
with engine.begin() as conn:
    r = conn.execute(text("DELETE FROM career_trajectories"))
    print(f"Deleted {r.rowcount} trajectory records")
