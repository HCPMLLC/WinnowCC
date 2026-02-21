"""Test job ingestion with HTML preservation."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.db.session import get_session_factory
from app.services.job_ingestion import ingest_jobs

session = get_session_factory()()
try:
    # Ingest some jobs
    count = ingest_jobs(session, {"search": "project manager"})
    print(f"Ingested {count} new jobs")

    # Check if any have HTML now
    result = session.execute(
        text("""
        SELECT source, title, company,
               CASE WHEN description_html IS NOT NULL THEN 'YES' ELSE 'NO' END as has_html,
               LEFT(description_html, 200) as html_preview
        FROM jobs
        WHERE description_html IS NOT NULL
        ORDER BY ingested_at DESC
        LIMIT 5
    """)
    )
    rows = result.fetchall()

    print(f"\n=== JOBS WITH HTML ({len(rows)} found) ===")
    for row in rows:
        print(f"\n{row.source}: {row.title} ({row.company})")
        print(f"HTML Preview: {row.html_preview}")
finally:
    session.close()
