"""Check active employer jobs and whether proxy Job rows exist."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.session import get_session_factory

session = get_session_factory()()
try:
    # Active employer jobs
    rows = session.execute(
        text("""
            SELECT ej.id, ej.title, ep.company_name, ej.status, ej.posted_at,
                   ej.location, ej.remote_policy
            FROM employer_jobs ej
            JOIN employer_profiles ep ON ep.id = ej.employer_id
            WHERE ej.status = 'active' AND ej.archived = false
            ORDER BY ej.id
        """)
    ).fetchall()
    print(f"Active employer jobs: {len(rows)}\n")
    for r in rows:
        print(f"  EJ #{r[0]}: {r[1]} @ {r[2]} (status={r[3]}, posted={r[4]}, loc={r[5]}, remote={r[6]})")

    # Check for existing proxy Job rows
    proxies = session.execute(
        text("SELECT id, source_job_id, title, company, is_active FROM jobs WHERE source = 'employer'")
    ).fetchall()
    print(f"\nExisting proxy Job rows (source='employer'): {len(proxies)}")
    for p in proxies:
        print(f"  Job #{p[0]}: {p[1]} — {p[2]} @ {p[3]} (active={p[4]})")
finally:
    session.close()
