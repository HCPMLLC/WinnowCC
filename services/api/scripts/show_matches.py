"""Show all matches for user 9."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.match import Match

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    matches = session.execute(
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(Match.user_id == 9)
        .order_by(Match.interview_probability.desc().nulls_last())
    ).all()

    print(f"Total matches: {len(matches)}\n")

    for i, (match, job) in enumerate(matches, 1):
        print(f"{i}. {job.title}")
        print(f"   Company: {job.company}")
        print(f"   Location: {job.location}")
        print(
            f"   IPS: {match.interview_probability}, Match Score: {match.match_score}"
        )
        print(f"   Matched Skills: {match.reasons.get('matched_skills', [])}")
        print()
