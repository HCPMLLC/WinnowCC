"""Backfill proxy Job rows for all active employer and recruiter jobs."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.db.session import get_session_factory
from app.services.job_pipeline import (
    sync_employer_job_to_jobs,
    sync_recruiter_job_to_jobs,
)

# ── Employer jobs ────────────────────────────────────────────────────────

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

# ── Recruiter jobs ───────────────────────────────────────────────────────

session = get_session_factory()()
try:
    rj_rows = session.execute(
        text("""
            SELECT rj.id, rj.title, rj.client_company_name, rp.company_name
            FROM recruiter_jobs rj
            JOIN recruiter_profiles rp ON rp.id = rj.recruiter_profile_id
            WHERE rj.status = 'active'
            ORDER BY rj.id
        """)
    ).fetchall()
    print(f"\nSyncing {len(rj_rows)} active recruiter jobs...\n")
finally:
    session.close()

for r in rj_rows:
    company = r[2] or r[3] or "Unknown"
    print(f"  Syncing RJ #{r[0]}: {r[1]} @ {company}...")
    result = sync_recruiter_job_to_jobs(r[0])
    print(f"    -> {result}")

# ── Re-match sample candidate ───────────────────────────────────────────

print("\nNow re-matching Zachary Davis...")
from app.services.matching import compute_matches

session = get_session_factory()()
try:
    matches = compute_matches(session, 215, 3)
    print(f"Computed {len(matches)} matches\n")
    for i, m in enumerate(matches[:15], 1):
        job = session.execute(
            text("SELECT title, company, source FROM jobs WHERE id = :jid"),
            {"jid": m.job_id},
        ).fetchone()
        if job:
            marker = ""
            if job[2] == "employer":
                marker = " ** EMPLOYER **"
            elif job[2] == "recruiter":
                marker = " ** RECRUITER **"
            print(
                f"  {i}. score={m.match_score}"
                f" ips={m.interview_probability}"
                f" - {job[0]} @ {job[1]}"
                f" (source={job[2]}){marker}"
            )
finally:
    session.close()
