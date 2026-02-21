"""Test required skills extraction from job descriptions."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.services.matching import (
    _extract_all_skills,
    _extract_required_skills,
    _extract_skills_from_text,
)

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    # Get candidate skills
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == 9)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    candidate_skills = (
        set(_extract_all_skills(profile.profile_json)) if profile else set()
    )
    print(
        f"Candidate skills ({len(candidate_skills)}): {list(candidate_skills)[:15]}...\n"
    )

    # Get a few PM jobs and check required skills
    jobs = (
        session.execute(
            select(Job).where(Job.title.ilike("%project manager%")).limit(3)
        )
        .scalars()
        .all()
    )

    for job in jobs:
        print(f"=== {job.title} at {job.company} ===")

        # All skills in job
        all_job_skills = _extract_skills_from_text(job.description_text or "")
        print(f"All job skills ({len(all_job_skills)}): {all_job_skills[:10]}")

        # Required skills only
        required = _extract_required_skills(job.description_text or "")
        print(f"Required skills ({len(required)}): {required}")

        # Skills to highlight (required skills candidate has)
        skills_to_highlight = [s for s in required if s.lower() in candidate_skills]
        print(f"Skills to highlight: {skills_to_highlight}")

        # Required skills candidate is missing
        missing_required = [s for s in required if s.lower() not in candidate_skills]
        print(f"Missing required: {missing_required}")

        print()
