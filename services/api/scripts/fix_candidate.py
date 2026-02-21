"""Fix candidate onboarding data for user 9 (Ronald Levi)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.candidate import Candidate

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    candidate = session.query(Candidate).filter(Candidate.user_id == 9).first()

    if candidate:
        print("Current values:")
        print(f"  desired_job_types: {candidate.desired_job_types}")
        print(f"  desired_locations: {candidate.desired_locations}")
        print(f"  years_experience: {candidate.years_experience}")
        print(f"  remote_preference: {candidate.remote_preference}")

        # Fix the values
        candidate.desired_job_types = [
            "Project Manager",
            "Program Manager",
            "PMO Director",
        ]
        candidate.desired_locations = ["Remote", "Austin, TX", "San Antonio, TX"]
        candidate.years_experience = 15  # Adjust to actual years
        candidate.remote_preference = "remote"

        session.commit()

        print("\nUpdated values:")
        print(f"  desired_job_types: {candidate.desired_job_types}")
        print(f"  desired_locations: {candidate.desired_locations}")
        print(f"  years_experience: {candidate.years_experience}")
        print(f"  remote_preference: {candidate.remote_preference}")
    else:
        print("Candidate not found")
