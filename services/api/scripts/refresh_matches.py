"""Directly compute matches for user 9 using the new matching logic."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.services.matching import compute_matches

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    # Get latest profile version
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == 9)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if profile:
        print(f"Computing matches for user 9, profile version {profile.version}...")
        matches = compute_matches(session, user_id=9, profile_version=profile.version)
        print(f"Created {len(matches)} matches")

        if matches:
            print("\nTop 5 matches:")
            for m in matches[:5]:
                # Get job details
                from app.models.job import Job

                job = session.get(Job, m.job_id)
                print(f"  - {job.title} at {job.company}")
                print(
                    f"    IPS: {m.interview_probability}, Match Score: {m.match_score}"
                )
                print(f"    Matched Skills: {m.reasons.get('matched_skills', [])[:5]}")
    else:
        print("No profile found for user 9")
