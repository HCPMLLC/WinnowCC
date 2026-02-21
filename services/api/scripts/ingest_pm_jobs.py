"""Ingest jobs specifically for Project Management roles."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.job_ingestion import ingest_jobs

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

# Search queries targeted for PM roles
queries = [
    {"search": "Project Manager", "location": "Remote"},
    {"search": "Program Manager", "location": "Remote"},
    {"search": "PMO Director", "location": "Remote"},
    {"search": "Scrum Master", "location": "Remote"},
    {"search": "Project Manager", "location": "Austin, TX"},
    {"search": "Project Manager", "location": "San Antonio, TX"},
]

with Session(engine) as session:
    total = 0
    for query in queries:
        print(f"Searching: {query['search']} in {query['location']}...")
        count = ingest_jobs(session, query)
        print(f"  Found {count} new jobs")
        total += count

    print(f"\nTotal new jobs ingested: {total}")
