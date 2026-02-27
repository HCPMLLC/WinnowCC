"""Debug: check why lakshmi@test.com was quarantined."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])

uid = 213

with engine.connect() as c:
    # Check candidate_trust columns
    cols = c.execute(
        text(
            "SELECT column_name "
            "FROM information_schema.columns "
            "WHERE table_name = 'candidate_trust' "
            "ORDER BY ordinal_position"
        )
    ).fetchall()
    print(f"candidate_trust columns: {[r[0] for r in cols]}")

    # Check trust_audit_log columns
    cols2 = c.execute(
        text(
            "SELECT column_name "
            "FROM information_schema.columns "
            "WHERE table_name = 'trust_audit_log' "
            "ORDER BY ordinal_position"
        )
    ).fetchall()
    print(f"trust_audit_log columns: {[r[0] for r in cols2]}")

    # Query candidate_trust for this user (use correct column)
    trust = c.execute(
        text("SELECT * FROM candidate_trust WHERE candidate_id = :uid"), {"uid": uid}
    ).fetchone()
    if trust:
        print(f"\nCandidate Trust: {dict(trust._mapping)}")
    else:
        print("\nNo candidate_trust record for candidate_id=213")

    # Check trust_audit_log
    logs = c.execute(
        text(
            "SELECT * FROM trust_audit_log "
            "WHERE candidate_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": uid},
    ).fetchall()
    if logs:
        print(f"\nTrust Audit Log ({len(logs)} entries):")
        for log in logs:
            print(f"  {dict(log._mapping)}")
    else:
        print("\nNo trust_audit_log entries for candidate_id=213")

    # Check resume_documents
    docs = c.execute(
        text(
            "SELECT id, filename, file_hash, "
            "trust_score, uploaded_at "
            "FROM resume_documents "
            "WHERE user_id = :uid "
            "ORDER BY uploaded_at DESC"
        ),
        {"uid": uid},
    ).fetchall()
    if docs:
        print(f"\nResume Documents ({len(docs)}):")
        for d in docs:
            print(f"  id={d[0]} file={d[1]} hash={d[2]} trust={d[3]} uploaded={d[4]}")
    else:
        print("\nNo resume documents")

    # Check candidate_profiles
    profiles = c.execute(
        text(
            "SELECT id, user_id, profile_version, "
            "trust_score, quarantine "
            "FROM candidate_profiles "
            "WHERE user_id = :uid ORDER BY id DESC"
        ),
        {"uid": uid},
    ).fetchall()
    if profiles:
        print(f"\nCandidate Profiles ({len(profiles)}):")
        for p in profiles:
            print(
                f"  id={p[0]} user={p[1]} version={p[2]} trust={p[3]} quarantine={p[4]}"
            )
    else:
        print("\nNo candidate profiles")
