"""Find matches with posting red flags for a specific user."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.match import Match
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail

USER_ID = 215

SessionFactory = get_session_factory()
session = SessionFactory()

try:
    # Query matches joined with jobs and job_parsed_details
    stmt = (
        select(Match, Job, JobParsedDetail)
        .join(Job, Match.job_id == Job.id)
        .outerjoin(JobParsedDetail, JobParsedDetail.job_id == Job.id)
        .where(Match.user_id == USER_ID)
        .where(
            # Has red flags (non-null, non-empty list) OR fraud score > 0 OR is_likely_fraudulent
            (JobParsedDetail.red_flags.isnot(None))
            | (JobParsedDetail.fraud_score > 0)
            | (JobParsedDetail.is_likely_fraudulent == True)
        )
        .order_by(Match.match_score.desc())
    )

    results = session.execute(stmt).all()

    if not results:
        print(f"No matches with red flags found for user_id={USER_ID}")
        # Let's also check what parsed details exist at all for this user's matches
        count_stmt = (
            select(Match.id)
            .where(Match.user_id == USER_ID)
        )
        total = len(session.execute(count_stmt).all())

        detail_stmt = (
            select(Match.id, JobParsedDetail.id)
            .join(Job, Match.job_id == Job.id)
            .outerjoin(JobParsedDetail, JobParsedDetail.job_id == Job.id)
            .where(Match.user_id == USER_ID)
            .where(JobParsedDetail.id.isnot(None))
        )
        with_details = len(session.execute(detail_stmt).all())
        print(f"  Total matches: {total}")
        print(f"  Matches with parsed details: {with_details}")
    else:
        print(f"Found {len(results)} matches with red flags for user_id={USER_ID}")
        print("=" * 100)
        for match, job, detail in results:
            print(f"\nMatch ID: {match.id} | Job ID: {job.id}")
            print(f"  Title:    {job.title}")
            print(f"  Company:  {job.company}")
            print(f"  Source:   {job.source}")
            print(f"  Match Score:       {match.match_score}")
            print(f"  Interview Prob:    {match.interview_probability}")
            print(f"  App Status:        {match.application_status}")
            if detail:
                print(f"  --- Quality & Fraud ---")
                print(f"  Posting Quality:   {detail.posting_quality_score}")
                print(f"  Fraud Score:       {detail.fraud_score}")
                print(f"  Likely Fraud:      {detail.is_likely_fraudulent}")
                print(f"  Red Flags:         {detail.red_flags}")
            print("-" * 100)

finally:
    session.close()
