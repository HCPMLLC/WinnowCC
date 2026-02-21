"""Check what skills are extracted from PM job descriptions."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.services.matching import SKILL_DATABASE, _extract_skills_from_text

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

# PM skills that should be recognized
pm_skills_to_check = [
    "project management",
    "program management",
    "stakeholder management",
    "budget management",
    "resource planning",
    "risk management",
    "pmp",
    "agile",
    "scrum",
    "waterfall",
    "jira",
    "ms project",
    "smartsheet",
    "communication",
    "leadership",
    "vendor management",
    "change management",
]

print("=== PM Skills in SKILL_DATABASE ===")
for skill in pm_skills_to_check:
    in_db = skill.lower() in SKILL_DATABASE
    print(f"  {skill}: {'YES' if in_db else 'NO'}")

with Session(engine) as session:
    # Get a PM job
    job = session.execute(
        select(Job).where(Job.title.ilike("%project manager%")).limit(1)
    ).scalar_one_or_none()

    if job:
        print(f"\n=== Sample Job: {job.title} ===")
        print(f"Description length: {len(job.description_text or '')} chars")

        # Extract skills
        extracted = _extract_skills_from_text(job.description_text or "")
        print(f"\nExtracted skills ({len(extracted)}):")
        for s in extracted[:20]:
            print(f"  - {s}")

        # Show first 500 chars of description
        print("\nDescription preview:")
        print(job.description_text[:800] if job.description_text else "No description")
