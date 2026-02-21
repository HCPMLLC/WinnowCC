"""Quick script to check DB columns."""

import os

from dotenv import load_dotenv

load_dotenv()

import sqlalchemy

db_url = os.getenv("DB_URL")
engine = sqlalchemy.create_engine(db_url)
with engine.connect() as conn:
    r = conn.execute(
        sqlalchemy.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'candidate_profiles' ORDER BY ordinal_position"
        )
    )
    print("candidate_profiles columns:", [row[0] for row in r])

    r2 = conn.execute(
        sqlalchemy.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'jobs' AND column_name = 'embedding'"
        )
    )
    print("jobs.embedding exists:", len(r2.fetchall()) > 0)

    r3 = conn.execute(
        sqlalchemy.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'matches' AND column_name = 'semantic_similarity'"
        )
    )
    print("matches.semantic_similarity exists:", len(r3.fetchall()) > 0)
