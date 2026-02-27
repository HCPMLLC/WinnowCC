"""One-off script: deactivate the SSP Innovations LLC job from Jooble.

Usage:
    cd services/api
    python scripts/deactivate_ssp_job.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.job import Job

session = get_session_factory()()

stmt = select(Job).where(
    Job.company.ilike("%SSP Innovations%"),
    Job.source == "jooble",
    Job.is_active.is_not(False),
)
jobs = session.execute(stmt).scalars().all()

if not jobs:
    print("No active SSP Innovations jobs from Jooble found.")
else:
    for job in jobs:
        print(
            f"Deactivating job #{job.id}: {job.title}"
            f" at {job.company} (source={job.source})"
        )
        job.is_active = False
    session.commit()
    print(f"Done. Deactivated {len(jobs)} job(s).")

session.close()
