"""Show job description to understand format."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.job import Job

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    job = session.execute(
        select(Job).where(Job.title.ilike("%project manager%")).limit(1)
    ).scalar_one_or_none()

    if job:
        print(f"=== {job.title} at {job.company} ===\n")
        desc = job.description_text or "No description"
        # Print first 2000 chars
        print(desc[:2000])
        print("\n... (truncated)")
