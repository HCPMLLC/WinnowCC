"""Drop all objects in the public schema and run Alembic migrations from scratch."""
import os
import subprocess
import sys

from sqlalchemy import create_engine, text

db_url = os.environ.get("DB_URL", "")
if not db_url:
    print("ERROR: DB_URL not set")
    sys.exit(1)

engine = create_engine(db_url)

print("Dropping public schema...")
with engine.begin() as conn:
    conn.execute(text("DROP SCHEMA public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO winnow_user"))

print("Schema reset complete. Running migrations...")
result = subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd="/app",
)
sys.exit(result.returncode)
