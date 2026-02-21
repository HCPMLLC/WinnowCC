"""Backfill proxy Job rows for all active employer jobs, then re-match Zachary."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.session import get_session_factory
from app.services.job_pipeline import sync_employer_job_to_jobs

session = get_session_factory()()
try:
    rows = session.execute(
        text("""
            SELECT ej.id, ej.title, ep.company_name
            FROM employer_jobs ej
            JOIN employer_profiles ep ON ep.id = ej.employer_id
            WHERE ej.status = 'active' AND ej.archived = false
            ORDER BY ej.id
        """)
    ).fetchall()
    print(f"Syncing {len(rows)} active employer jobs...\n")
finally:
    session.close()

for r in rows:
    print(f"  Syncing EJ #{r[0]}: {r[1]} @ {r[2]}...")
    result = sync_employer_job_to_jobs(r[0])
    print(f"    -> {result}")

print("\nNow re-matching Zachary Davis...")
from app.services.matching import compute_matches

session = get_session_factory()()
try:
    matches = compute_matches(session, 215, 3)
    print(f"Computed {len(matches)} matches\n")
    for i, m in enumerate(matches[:15], 1):
        job = session.execute(
            text("SELECT title, company, source FROM jobs WHERE id = :jid"),
            {"jid": m.job_id}
        ).fetchone()
        if job:
            marker = " ** EMPLOYER **" if job[2] == "employer" else ""
            print(f"  {i}. score={m.match_score} ips={m.interview_probability} - {job[0]} @ {job[1]} (source={job[2]}){marker}")
finally:
    session.close()
