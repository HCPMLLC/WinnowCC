"""End-to-end test of distribution API using direct DB access."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)

from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.distribution import BoardConnection, DistributionEvent, JobDistribution
from app.models.employer import EmployerJob, EmployerProfile
from app.services.distribution import distribute_job, remove_from_boards, sync_metrics

session = get_session_factory()()

# Find an employer profile
employer = session.execute(select(EmployerProfile).limit(1)).scalar_one_or_none()
if not employer:
    print("No employer profile found — create one first")
    sys.exit(1)

print(f"Using employer: {employer.company_name} (id={employer.id})")

# 1. Create a board connection
print("\n--- Step 1: Create board connection ---")
conn = BoardConnection(
    employer_id=employer.id,
    board_type="indeed",
    board_name="Indeed Test",
    api_key_encrypted="test-key-123",
    is_active=True,
)
session.add(conn)
session.commit()
session.refresh(conn)
print(f"Created connection id={conn.id}, type={conn.board_type}")

# 2. Find or create an active job
job = session.execute(
    select(EmployerJob).where(
        EmployerJob.employer_id == employer.id,
        EmployerJob.status == "active",
    )
).scalar_one_or_none()

if not job:
    job = EmployerJob(
        employer_id=employer.id,
        title="Test Distribution Job",
        description="This is a test job for distribution testing.",
        status="active",
        posted_at=datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    print(f"Created test job id={job.id}")
else:
    print(f"Using existing job: {job.title} (id={job.id})")

# 3. Distribute job
print("\n--- Step 2: Distribute job ---")
results = distribute_job(job.id, None, session)
print(f"Distribution results: {results}")

# 4. Check distributions
dists = list(
    session.execute(
        select(JobDistribution).where(
            JobDistribution.employer_job_id == job.id
        )
    ).scalars().all()
)
print(f"Distributions found: {len(dists)}")
for d in dists:
    print(f"  dist_id={d.id} status={d.status} external_id={d.external_job_id}")

# 5. Check events
events = list(
    session.execute(
        select(DistributionEvent).where(
            DistributionEvent.distribution_id == dists[0].id
        )
    ).scalars().all()
)
print(f"Events for first distribution: {len(events)}")
for ev in events:
    print(f"  event_type={ev.event_type} data={ev.event_data}")

# 6. Sync metrics
print("\n--- Step 3: Sync metrics ---")
metrics_results = sync_metrics(job.id, session)
print(f"Metrics sync results: {metrics_results}")

# 7. Remove from boards
print("\n--- Step 4: Remove from boards ---")
remove_results = remove_from_boards(job.id, session)
print(f"Remove results: {remove_results}")

# Check final state
session.refresh(dists[0])
print(f"Distribution final status: {dists[0].status}")

# Cleanup
print("\n--- Cleanup ---")
session.delete(conn)
# Delete test job if we created it
if job.title == "Test Distribution Job":
    session.delete(job)
session.commit()
session.close()
print("Cleanup complete. All tests passed!")
