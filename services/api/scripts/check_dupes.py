"""Check for duplicate candidate profiles."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dotenv; dotenv.load_dotenv()
os.environ['DB_URL'] = 'postgresql+psycopg://winnow_user:cz1ADiUqCvusFyvmLPyirOalj0ZWPmDC@127.0.0.1:5433/winnow'

from sqlalchemy import text
from app.db.session import get_session_factory

session = get_session_factory()()

# Check source tags
print("=== By source tag ===")
rows = session.execute(text(
    "SELECT profile_json->>'source' as src, COUNT(*) as cnt "
    "FROM candidate_profiles WHERE user_id IS NULL "
    "GROUP BY profile_json->>'source' ORDER BY cnt DESC"
)).fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}")

# Profiles with/without resume
with_resume = session.execute(text(
    "SELECT COUNT(*) FROM candidate_profiles WHERE user_id IS NULL AND resume_document_id IS NOT NULL"
)).scalar()
without_resume = session.execute(text(
    "SELECT COUNT(*) FROM candidate_profiles WHERE user_id IS NULL AND resume_document_id IS NULL"
)).scalar()
print(f"\nWith resume_document_id: {with_resume}")
print(f"Without resume_document_id: {without_resume}")

# Check for duplicate emails
print("\n=== Duplicate emails (top 20) ===")
rows = session.execute(text(
    "SELECT profile_json->'basics'->>'email' as email, COUNT(*) as cnt "
    "FROM candidate_profiles WHERE user_id IS NULL "
    "AND profile_json->'basics'->>'email' IS NOT NULL "
    "GROUP BY profile_json->'basics'->>'email' "
    "HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT 20"
)).fetchall()
total_dupes = 0
for r in rows:
    print(f"  {r[0]}: {r[1]} copies")
    total_dupes += r[1] - 1  # excess copies

print(f"\nTotal excess duplicate profiles: {total_dupes}")

# Count total unique vs total
total_with_email = session.execute(text(
    "SELECT COUNT(*) FROM candidate_profiles WHERE user_id IS NULL "
    "AND profile_json->'basics'->>'email' IS NOT NULL"
)).scalar()
unique_emails = session.execute(text(
    "SELECT COUNT(DISTINCT profile_json->'basics'->>'email') FROM candidate_profiles "
    "WHERE user_id IS NULL AND profile_json->'basics'->>'email' IS NOT NULL"
)).scalar()
no_email = session.execute(text(
    "SELECT COUNT(*) FROM candidate_profiles WHERE user_id IS NULL "
    "AND (profile_json->'basics'->>'email' IS NULL OR profile_json->'basics'->>'email' = '')"
)).scalar()
print(f"\nTotal sourced profiles with email: {total_with_email}")
print(f"Unique emails: {unique_emails}")
print(f"Profiles with no email: {no_email}")
print(f"Duplicates (total - unique): {total_with_email - unique_emails}")

session.close()
