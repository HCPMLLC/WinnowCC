"""Debug: check employer_job_candidates match counts."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DB_URL"])

with engine.connect() as c:
    # Check employer_job_candidates for all jobs with match_score > 0.5
    rows = c.execute(text(
        "SELECT ejc.employer_job_id, ej.title, COUNT(*) as cnt, array_agg(ejc.match_score) "
        "FROM employer_job_candidates ejc "
        "JOIN employer_jobs ej ON ej.id = ejc.employer_job_id "
        "WHERE ejc.match_score > 0.5 "
        "GROUP BY ejc.employer_job_id, ej.title"
    )).fetchall()
    print("=== Matches with score > 0.5 ===")
    for r in rows:
        print(f"  Job {r[0]}: {r[1]} -> {r[2]} matches (scores: {r[3]})")
    if not rows:
        print("  (none)")

    # Also check all employer_job_candidates
    print("\n=== All employer_job_candidates ===")
    all_rows = c.execute(text(
        "SELECT employer_job_id, candidate_profile_id, match_score "
        "FROM employer_job_candidates ORDER BY employer_job_id"
    )).fetchall()
    for r in all_rows:
        print(f"  job={r[0]} profile={r[1]} score={r[2]}")
    if not all_rows:
        print("  (none)")

    # Check employer_jobs exist
    print("\n=== Employer Jobs ===")
    jobs = c.execute(text(
        "SELECT id, title, status, employer_id FROM employer_jobs ORDER BY id"
    )).fetchall()
    for j in jobs:
        print(f"  id={j[0]} title={j[1]} status={j[2]} employer_id={j[3]}")

    # Check employer_profiles
    print("\n=== Employer Profiles ===")
    profiles = c.execute(text(
        "SELECT id, user_id, company_name FROM employer_profiles"
    )).fetchall()
    for p in profiles:
        print(f"  id={p[0]} user_id={p[1]} company={p[2]}")
