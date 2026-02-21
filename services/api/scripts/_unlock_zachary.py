"""Run match refresh for Zachary Davis (user 215, profile v3)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.session import get_session_factory
from app.services.matching import compute_matches

USER_ID = 215
PROFILE_VERSION = 3

session = get_session_factory()()
try:
    print(f"Running compute_matches for user {USER_ID}, profile v{PROFILE_VERSION}...")
    matches = compute_matches(session, USER_ID, PROFILE_VERSION)
    print(f"Computed {len(matches)} matches for Zachary Davis\n")
    for i, m in enumerate(matches[:10], 1):
        job = session.execute(
            text("SELECT title, company, source FROM jobs WHERE id = :jid"),
            {"jid": m.job_id}
        ).fetchone()
        if job:
            print(f"  {i}. score={m.match_score} ips={m.interview_probability} — {job[0]} @ {job[1]} (source={job[2]})")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
