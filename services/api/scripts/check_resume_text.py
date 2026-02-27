import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "DB_URL", "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)
from pathlib import Path

from sqlalchemy import create_engine, text

from app.services.profile_parser import extract_text

engine = create_engine(os.environ["DB_URL"])
with engine.connect() as conn:
    # First check table structure
    cols = conn.execute(
        text(
            "SELECT column_name "
            "FROM information_schema.columns "
            "WHERE table_name = 'resume_documents'"
        )
    ).fetchall()
    print("Columns:", [c[0] for c in cols])

    row = (
        conn.execute(
            text(
                "SELECT * FROM resume_documents "
                "WHERE user_id = 10 "
                "ORDER BY id DESC LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    if row:
        print("Row keys:", list(row.keys()))
        # Find the path column
        for k in row.keys():
            if "path" in k.lower() or "file" in k.lower() or "storage" in k.lower():
                print(f"  {k}: {row[k]}")
        # Try to extract text from whatever path column exists
        path_val = row.get("file_path") or row.get("storage_path") or row.get("path")
        if path_val:
            path = Path(path_val)
            print(f"File: {path}")
            raw = extract_text(path)
            for i, line in enumerate(raw.splitlines()[:30]):
                print(f"  {i:3d}: {repr(line)}")
