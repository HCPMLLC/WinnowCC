"""Check all jobs for HTML content."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DB_URL"))
with engine.connect() as conn:
    # Count jobs with HTML by source
    result = conn.execute(
        text("""
        SELECT
            source,
            COUNT(*) as total,
            SUM(CASE WHEN description_text LIKE '%<%>%' THEN 1 ELSE 0 END) as with_html
        FROM jobs
        GROUP BY source
        ORDER BY with_html DESC
    """)
    )
    rows = result.fetchall()

    print("=== HTML CONTENT BY SOURCE ===")
    print(f"{'Source':<15} {'Total':<10} {'With HTML':<10} {'%':<10}")
    print("-" * 45)
    for row in rows:
        pct = (row.with_html / row.total * 100) if row.total > 0 else 0
        print(f"{row.source:<15} {row.total:<10} {row.with_html:<10} {pct:.1f}%")

    print("\n=== SAMPLE JOB WITH HTML ===")
    result = conn.execute(
        text("""
        SELECT source, title, company, LEFT(description_text, 1000) as desc
        FROM jobs
        WHERE description_text LIKE '%<%>%'
        LIMIT 1
    """)
    )
    row = result.fetchone()
    if row:
        print(f"Source: {row.source}")
        print(f"Title: {row.title}")
        print(f"Company: {row.company}")
        print(f"Description:\n{row.desc}")
    else:
        print("No jobs with HTML found")
