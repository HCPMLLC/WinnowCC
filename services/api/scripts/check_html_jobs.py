"""Check if jobs from HTML sources have preserved formatting."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DB_URL"))
with engine.connect() as conn:
    # Check jobs from sources that should have HTML
    result = conn.execute(
        text("""
        SELECT source, title, company, LEFT(description_text, 800) as desc_preview
        FROM jobs
        WHERE source IN ('remotive', 'themuse', 'arbeitnow', 'greenhouse')
        ORDER BY ingested_at DESC
        LIMIT 4
    """)
    )
    rows = result.fetchall()

    for row in rows:
        print(f"=== {row.source.upper()}: {row.title} ({row.company}) ===")
        desc = row.desc_preview or ""
        has_html = any(
            tag in desc.lower()
            for tag in [
                "<p>",
                "<li>",
                "<ul>",
                "<strong>",
                "<br",
                "<div",
                "<h1",
                "<h2",
                "<h3",
            ]
        )
        print(f"Contains HTML: {has_html}")
        print(f"Preview:\n{desc[:600]}")
        print("\n" + "=" * 60 + "\n")
