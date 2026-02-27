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
    # Resume documents
    docs = c.execute(
        text("SELECT * FROM resume_documents WHERE user_id = :uid"), {"uid": uid}
    ).fetchall()
    if docs:
        print(f"Resume Documents ({len(docs)}):")
        for d in docs:
            m = dict(d._mapping)
            print(f"  {m}")
            # Trust record
            trust = c.execute(
                text("SELECT * FROM candidate_trust WHERE resume_document_id = :did"),
                {"did": m["id"]},
            ).fetchone()
            if trust:
                tm = dict(trust._mapping)
                print(
                    f"  -> Trust: status={tm.get('status')}"
                    f" score={tm.get('score')}"
                    f" reasons={tm.get('reasons')}"
                    f" message={tm.get('user_message')}"
                )
                # Audit log
                logs = c.execute(
                    text(
                        "SELECT * FROM trust_audit_log "
                        "WHERE trust_id = :tid "
                        "ORDER BY created_at DESC"
                    ),
                    {"tid": tm["id"]},
                ).fetchall()
                for log in logs:
                    print(f"     Audit: {dict(log._mapping)}")
            else:
                print("  -> No trust record")
    else:
        print("No resume documents for user 213")

    # Candidate profiles
    profiles = c.execute(
        text("SELECT * FROM candidate_profiles WHERE user_id = :uid"), {"uid": uid}
    ).fetchall()
    if profiles:
        print(f"\nCandidate Profiles ({len(profiles)}):")
        for p in profiles:
            m = dict(p._mapping)
            print(
                f"  id={m['id']}"
                f" version={m.get('profile_version')}"
                f" trust={m.get('trust_score')}"
                f" quarantine={m.get('quarantine')}"
            )
    else:
        print("\nNo candidate profiles")
