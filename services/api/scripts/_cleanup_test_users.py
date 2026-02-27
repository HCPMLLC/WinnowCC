"""Remove leftover test validation users."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import text

from app.db.session import get_session_factory

s = get_session_factory()()

test_emails = [
    "test-alex@example.com",
    "test-maria@example.com",
    "test-jordan@example.com",
    "test-priya@example.com",
    "test-sam@example.com",
]

for email in test_emails:
    row = s.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": email}
    ).fetchone()
    if row:
        uid = row[0]
        s.execute(text("DELETE FROM matches WHERE user_id = :id"), {"id": uid})
        s.execute(text("DELETE FROM tailored_resumes WHERE user_id = :id"), {"id": uid})
        s.execute(
            text("DELETE FROM candidate_profiles WHERE user_id = :id"), {"id": uid}
        )
        s.execute(text("DELETE FROM candidate WHERE user_id = :id"), {"id": uid})
        s.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        print(f"Deleted test user: {email} (id={uid})")
    else:
        print(f"Not found: {email}")

s.commit()
s.close()
print("Cleanup done.")
