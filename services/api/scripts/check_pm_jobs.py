"""Check how many PM-related jobs are in the database."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.job import Job

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

cutoff = datetime.now(UTC) - timedelta(days=7)

pm_keywords = [
    "project manager",
    "program manager",
    "pmo",
    "scrum master",
    "agile coach",
    "delivery manager",
    "project coordinator",
    "project lead",
]

with Session(engine) as session:
    # Get all jobs from last 7 days
    all_jobs = (
        session.execute(
            select(Job).where(Job.posted_at.is_not(None), Job.posted_at >= cutoff)
        )
        .scalars()
        .all()
    )

    print(f"Total jobs from last 7 days: {len(all_jobs)}")

    # Filter for PM-related titles
    pm_jobs = []
    for job in all_jobs:
        title_lower = job.title.lower()
        if any(kw in title_lower for kw in pm_keywords):
            pm_jobs.append(job)

    print(f"PM-related jobs: {len(pm_jobs)}")

    if pm_jobs:
        print("\nPM Jobs found:")
        for job in pm_jobs[:20]:
            print(f"  - {job.title} at {job.company}")
            print(f"    Posted: {job.posted_at}, Location: {job.location}")

    # Also show some non-PM jobs to see what's available
    print("\nSample of other job titles:")
    non_pm = [j for j in all_jobs if j not in pm_jobs][:10]
    for job in non_pm:
        print(f"  - {job.title}")
