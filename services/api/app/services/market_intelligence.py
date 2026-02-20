"""Market intelligence — salary benchmarks, time-to-fill, competitive landscape."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.job import Job

logger = logging.getLogger(__name__)


def get_salary_benchmarks(
    title: str,
    location: str | None,
    session: Session,
) -> dict:
    """Get salary benchmarks for a role from Winnow's job database.

    Returns 25th, 50th, 75th percentile salaries for similar roles.
    """
    # Build query for similar jobs with salary data
    stmt = select(Job.salary_min, Job.salary_max).where(
        Job.is_active.is_(True),
        Job.salary_min.isnot(None),
    )

    # Title similarity via ILIKE
    stmt = stmt.where(func.lower(Job.title).contains(title.lower()))

    if location:
        stmt = stmt.where(func.lower(Job.location).contains(location.lower()))

    stmt = stmt.limit(500)

    try:
        rows = session.execute(stmt).all()
    except Exception as e:
        logger.warning("Salary benchmark query failed: %s", e)
        return {"error": "Query failed", "sample_size": 0}

    if not rows:
        # Fallback to unified salary_intelligence (Tiers 2-4: parsed salaries,
        # reference table, and LLM estimate) instead of returning empty.
        try:
            from app.services.career_intelligence import salary_intelligence

            fallback = salary_intelligence(
                role_title=title, location=location, db=session,
            )
            # If the fallback returned usable data (has p50), convert to our format
            if fallback.get("p50"):
                return {
                    "title": title,
                    "location": location,
                    "sample_size": fallback.get("sample_size", 0),
                    "source": fallback.get("source"),
                    "p25": fallback.get("p25"),
                    "p50": fallback.get("p50"),
                    "p75": fallback.get("p75"),
                    "min_salary": fallback.get("p10"),
                    "max_salary": fallback.get("p90"),
                }
        except Exception as e:
            logger.warning("Salary fallback failed: %s", e)

        return {
            "sample_size": 0,
            "message": "Insufficient data for this role/location.",
        }

    # Compute midpoints
    midpoints = []
    for row in rows:
        low = row.salary_min or 0
        high = row.salary_max or low
        mid = (low + high) / 2
        if mid > 0:
            midpoints.append(mid)

    if not midpoints:
        return {"sample_size": 0, "message": "No salary data found."}

    midpoints.sort()
    n = len(midpoints)

    def percentile(p: float) -> int:
        idx = int(n * p)
        return int(midpoints[min(idx, n - 1)])

    return {
        "title": title,
        "location": location,
        "sample_size": n,
        "p25": percentile(0.25),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "min_salary": int(min(midpoints)),
        "max_salary": int(max(midpoints)),
    }


def get_time_to_fill_benchmarks(
    title: str,
    location: str | None,
    session: Session,
) -> dict:
    """Get estimated time-to-fill for similar roles.

    Based on how long similar jobs stay active in the database.
    """
    # Find recently closed/filled jobs with similar titles
    stmt = select(Job.posted_at, Job.updated_at).where(
        Job.posted_at.isnot(None),
        func.lower(Job.title).contains(title.lower()),
    )

    if location:
        stmt = stmt.where(func.lower(Job.location).contains(location.lower()))

    stmt = stmt.limit(200)

    try:
        rows = session.execute(stmt).all()
    except Exception as e:
        logger.warning("Time-to-fill query failed: %s", e)
        return {"error": "Query failed", "sample_size": 0}

    if not rows:
        return {
            "sample_size": 0,
            "message": "Insufficient data for estimate.",
        }

    durations = []
    for row in rows:
        if row.posted_at and row.updated_at:
            days = (row.updated_at - row.posted_at).days
            if 1 <= days <= 365:
                durations.append(days)

    if not durations:
        return {
            "sample_size": 0,
            "message": "Insufficient data for estimate.",
        }

    durations.sort()
    n = len(durations)

    return {
        "title": title,
        "location": location,
        "sample_size": n,
        "avg_days": round(sum(durations) / n, 1),
        "median_days": durations[n // 2],
        "p25_days": durations[int(n * 0.25)],
        "p75_days": durations[int(n * 0.75)],
    }


def get_competitive_landscape(
    employer_id: int,
    job_id: int,
    session: Session,
) -> dict:
    """Analyze competitive landscape for a specific job."""
    from app.models.employer import EmployerJob

    job = session.get(EmployerJob, job_id)
    if not job:
        return {"error": "Job not found"}

    title = job.title or ""
    location = job.location

    # Count similar active jobs from all sources
    similar_stmt = (
        select(func.count())
        .select_from(Job)
        .where(
            Job.is_active.is_(True),
            func.lower(Job.title).contains(title.lower()),
        )
    )
    if location:
        similar_stmt = similar_stmt.where(
            func.lower(Job.location).contains(location.lower())
        )

    try:
        similar_count = session.execute(similar_stmt).scalar() or 0
    except Exception:
        similar_count = 0

    # Get salary benchmarks for context
    benchmarks = get_salary_benchmarks(title, location, session)

    # Determine competitiveness
    employer_salary = ((job.salary_min or 0) + (job.salary_max or 0)) / 2
    market_median = benchmarks.get("p50", 0)

    salary_position = "unknown"
    if employer_salary > 0 and market_median > 0:
        ratio = employer_salary / market_median
        if ratio >= 1.1:
            salary_position = "above_market"
        elif ratio >= 0.9:
            salary_position = "at_market"
        else:
            salary_position = "below_market"

    return {
        "job_id": job_id,
        "title": title,
        "location": location,
        "similar_active_jobs": similar_count,
        "salary_benchmarks": benchmarks,
        "employer_salary_midpoint": int(employer_salary),
        "salary_position": salary_position,
        "recommendation": (
            "Consider increasing salary to attract more candidates."
            if salary_position == "below_market"
            else "Your salary is competitive."
            if salary_position in ("at_market", "above_market")
            else "Add salary information to improve application rates."
        ),
    }
