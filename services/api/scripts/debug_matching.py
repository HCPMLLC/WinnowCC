"""Debug why some PM jobs aren't matching."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.services.matching import (
    _extract_all_skills,
    _extract_skills_from_text,
    _is_title_compatible,
    _merge_preferences,
    _passes_preference_filters,
)

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
    # Get profile and candidate
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == 9)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == 9)
    ).scalar_one_or_none()

    preferences = _merge_preferences(profile.profile_json, candidate)
    candidate_skills = set(_extract_all_skills(profile.profile_json))

    print(f"Candidate target_titles: {preferences.get('target_titles', [])}")
    print(f"Candidate skills count: {len(candidate_skills)}")
    print(f"Sample skills: {list(candidate_skills)[:10]}")

    # Get PM jobs
    all_jobs = (
        session.execute(
            select(Job).where(Job.posted_at.is_not(None), Job.posted_at >= cutoff)
        )
        .scalars()
        .all()
    )

    pm_jobs = [j for j in all_jobs if any(kw in j.title.lower() for kw in pm_keywords)]

    print(f"\n=== Checking {len(pm_jobs)} PM jobs ===\n")

    for job in pm_jobs:
        print(f"Job: {job.title} at {job.company}")

        # Check title compatibility
        title_compat = _is_title_compatible(
            job.title.lower(), preferences.get("target_titles", [])
        )
        print(f"  Title compatible: {title_compat}")

        # Check preference filters
        passes_filters = _passes_preference_filters(job, preferences, candidate)
        print(f"  Passes filters: {passes_filters}")

        # Check skill overlap
        job_skills = set(
            s.lower() for s in _extract_skills_from_text(job.description_text or "")
        )
        skill_overlap = candidate_skills & job_skills
        print(
            f"  Skill overlap: {len(skill_overlap)} skills - {list(skill_overlap)[:5]}"
        )

        # Would it match?
        would_match = title_compat and passes_filters and len(skill_overlap) >= 1
        print(f"  WOULD MATCH: {would_match}")
        print()
