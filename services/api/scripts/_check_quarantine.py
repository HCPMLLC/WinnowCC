"""Debug: check why lakshmi@test.com was quarantined."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DB_URL"])

with engine.connect() as c:
    # Find user
    user = c.execute(
        text(
            "SELECT id, email, role, created_at "
            "FROM users WHERE email = 'lakshmi@test.com'"
        )
    ).fetchone()
    if not user:
        print("User lakshmi@test.com not found")
        exit()
    print(f"User: id={user[0]} email={user[1]} role={user[2]} created={user[3]}")

    uid = user[0]

    # Check candidate_trust
    trust = c.execute(
        text("SELECT * FROM candidate_trust WHERE user_id = :uid"), {"uid": uid}
    ).fetchone()
    if trust:
        print(f"\nCandidate Trust: {dict(trust._mapping)}")
    else:
        print("\nNo candidate_trust record")

    # Check trust_audit_log
    logs = c.execute(
        text(
            "SELECT * FROM trust_audit_log "
            "WHERE user_id = :uid "
            "ORDER BY created_at DESC"
        ),
        {"uid": uid},
    ).fetchall()
    if logs:
        print(f"\nTrust Audit Log ({len(logs)} entries):")
        for log in logs:
            print(f"  {dict(log._mapping)}")
    else:
        print("\nNo trust_audit_log entries")

    # Check if there are any resume_documents
    docs = c.execute(
        text(
            "SELECT id, filename, file_hash, trust_score, "
            "uploaded_at FROM resume_documents "
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
