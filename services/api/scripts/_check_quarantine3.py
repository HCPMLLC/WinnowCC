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
        print(f"Resume Documents ({len(docs)}):")
        for d in docs:
            print(f"  id={d[0]} file={d[1]} hash={d[2]} trust={d[3]} uploaded={d[4]}")

        # Check candidate_trust for each document
        for d in docs:
            trust = c.execute(
                text("SELECT * FROM candidate_trust WHERE resume_document_id = :did"),
                {"did": d[0]},
            ).fetchone()
            if trust:
                print(f"\n  Trust for doc {d[0]}: {dict(trust._mapping)}")

                # Check audit log
                logs = c.execute(
                    text(
                        "SELECT * FROM trust_audit_log "
                        "WHERE trust_id = :tid "
                        "ORDER BY created_at DESC"
                    ),
                    {"tid": trust[0]},
                ).fetchall()
                if logs:
                    print(f"  Audit Log ({len(logs)} entries):")
                    for log in logs:
                        print(f"    {dict(log._mapping)}")
            else:
                print(f"\n  No trust record for doc {d[0]}")
    else:
        print("No resume documents")

    # Check candidate_profiles
    print()
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
        print(f"Candidate Profiles ({len(profiles)}):")
        for p in profiles:
            print(
                f"  id={p[0]} user={p[1]} version={p[2]} trust={p[3]} quarantine={p[4]}"
            )
    else:
        print("No candidate profiles")
