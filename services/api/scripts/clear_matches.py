"""Clear old matches for user 9 so fresh matches can be computed."""

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.models.match import Match

engine = create_engine(
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch"
)

with Session(engine) as session:
    # Count existing matches
    count = session.query(Match).filter(Match.user_id == 9).count()
    print(f"Found {count} existing matches for user 9")

    # Delete them
    result = session.execute(delete(Match).where(Match.user_id == 9))
    session.commit()
    print(f"Deleted {result.rowcount} matches")
    print("\nNow restart the worker and refresh matches to get proper PM job matches.")
