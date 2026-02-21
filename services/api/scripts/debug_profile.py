"""Debug script to check profile skills and matching."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.services.matching import _extract_all_skills, _extract_skills_from_text

# Connect to database
engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    # Get Ronald Levi's profile (user_id 9)
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == 9)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if profile:
        pj = profile.profile_json
        print("=== PROFILE STRUCTURE ===")
        print(f"Top-level keys: {list(pj.keys())}")

        print("\n=== TOP-LEVEL SKILLS ===")
        top_skills = pj.get("skills", [])
        print(f"Count: {len(top_skills)}")
        print(
            f"Skills: {top_skills[:15]}..."
            if len(top_skills) > 15
            else f"Skills: {top_skills}"
        )

        print("\n=== EXPERIENCE SKILLS (first 3 jobs) ===")
        for i, exp in enumerate(pj.get("experience", [])[:3]):
            print(f"\nJob {i + 1}: {exp.get('title')} at {exp.get('company')}")
            print(f"  skills_used: {exp.get('skills_used', [])}")
            print(f"  technologies_used: {exp.get('technologies_used', [])}")
            print(f"  duties count: {len(exp.get('duties', []))}")

        print("\n=== PREFERENCES ===")
        prefs = pj.get("preferences", {})
        print(f"target_titles: {prefs.get('target_titles', [])}")
        print(f"locations: {prefs.get('locations', [])}")
        print(f"remote_ok: {prefs.get('remote_ok')}")

        print("\n=== EXTRACTED SKILLS (using _extract_all_skills) ===")
        extracted = _extract_all_skills(pj)
        print(f"Count: {len(extracted)}")
        print(
            f"Skills: {extracted[:20]}..."
            if len(extracted) > 20
            else f"Skills: {extracted}"
        )
    else:
        print("No profile found for user 9")

    # Check candidate record
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == 9)
    ).scalar_one_or_none()

    if candidate:
        print("\n=== CANDIDATE ONBOARDING ===")
        print(f"desired_job_types: {candidate.desired_job_types}")
        print(f"desired_locations: {candidate.desired_locations}")
        print(f"years_experience: {candidate.years_experience}")
        print(f"remote_preference: {candidate.remote_preference}")

    # Check recent matches
    print("\n=== RECENT MATCHES ===")
    matches = session.execute(
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(Match.user_id == 9)
        .order_by(Match.interview_probability.desc().nulls_last())
        .limit(5)
    ).all()

    for match, job in matches:
        print(f"\n{job.title} at {job.company}")
        print(f"  IPS: {match.interview_probability}, Match Score: {match.match_score}")
        print(f"  Matched Skills: {match.reasons.get('matched_skills', [])}")

        # Extract skills from this job
        job_skills = _extract_skills_from_text(job.description_text or "")
        print(
            f"  Job Skills Found: {job_skills[:10]}..."
            if len(job_skills) > 10
            else f"  Job Skills Found: {job_skills}"
        )
