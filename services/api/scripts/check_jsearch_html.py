"""Check JSearch jobs for formatted HTML from highlights."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.db.session import get_session_factory

session = get_session_factory()()
try:
    result = session.execute(
        text("""
        SELECT source, title, company,
               CASE WHEN description_html IS NOT NULL
                    THEN 'YES' ELSE 'NO' END as has_html,
               LEFT(description_html, 400) as html_preview
        FROM jobs
        WHERE source = 'jsearch'
        ORDER BY ingested_at DESC
        LIMIT 3
    """)
    )
    rows = result.fetchall()

    print(f"=== JSEARCH JOBS ({len(rows)} found) ===")
    for row in rows:
        print(f"\n{row.title} ({row.company})")
        print(f"Has HTML: {row.has_html}")
        if row.html_preview:
            print(f"HTML Preview:\n{row.html_preview}")
        else:
            print("No HTML content")
finally:
    session.close()
