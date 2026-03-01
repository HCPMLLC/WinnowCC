"""Market intelligence — salary benchmarks, time-to-fill, competitive landscape."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer as SAInteger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.career_intelligence import MarketIntel
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail

logger = logging.getLogger(__name__)

_MIN_SAMPLE = 20  # Minimum sample size before we trust a segment
_CACHE_TTL_DAYS = 7


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
                role_title=title,
                location=location,
                db=session,
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


def compute_ttf_segment_stats(
    employment_type: str | None,
    seniority_level: str | None,
    work_mode: str | None,
    industry: str | None,
    session: Session,
) -> dict | None:
    """Compute time-to-fill statistics for a job segment.

    Uses tiered matching (narrow → wide) on historical scraped jobs.
    Duration proxy: ``(last_seen_at - first_seen_at).days`` for inactive jobs.
    Results are cached in ``MarketIntel`` with a 7-day TTL.

    Returns dict with median_days, p25_days, p75_days, avg_days, sample_size,
    tier_used — or ``None`` if even the global fallback has no data.
    """
    # --- Check cache first ---
    parts = [employment_type, seniority_level, work_mode, industry]
    scope_key = "|".join(str(v or "").lower().strip() for v in parts)
    cached = session.execute(
        select(MarketIntel).where(
            MarketIntel.scope_type == "ttf",
            MarketIntel.scope_key == scope_key,
            MarketIntel.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()
    if cached:
        return cached.data_json

    # --- Build tiered filter sets (narrow → wide) ---
    et = (employment_type or "").lower().strip() or None
    sl = (seniority_level or "").lower().strip() or None
    wm = (work_mode or "").lower().strip() or None
    ind = (industry or "").lower().strip() or None

    tiers: list[tuple[int, dict[str, str | None]]] = [
        (
            1,
            {
                "employment_type": et,
                "seniority_level": sl,
                "work_mode": wm,
                "inferred_industry": ind,
            },
        ),
        (
            2,
            {
                "employment_type": et,
                "seniority_level": sl,
                "work_mode": wm,
            },
        ),
        (3, {"employment_type": et, "seniority_level": sl}),
        (4, {"employment_type": et}),
        (5, {}),  # global
    ]

    # Duration expression: days between first_seen_at and last_seen_at
    duration_expr = (
        func.extract(
            "epoch",
            Job.last_seen_at - Job.first_seen_at,
        ).cast(SAInteger)
        / 86400
    )  # seconds → days

    for tier_num, filters in tiers:
        # Skip tiers whose key field is None (e.g., tier 4 when employment_type is None)
        if tier_num <= 4 and not et:
            continue

        stmt = (
            select(duration_expr.label("dur_days"))
            .select_from(Job)
            .join(JobParsedDetail, JobParsedDetail.job_id == Job.id)
            .where(
                Job.is_active.is_(False),
                Job.first_seen_at.isnot(None),
                Job.last_seen_at.isnot(None),
                duration_expr >= 3,
                duration_expr <= 365,
            )
        )

        for col_name, val in filters.items():
            if val is not None:
                stmt = stmt.where(func.lower(getattr(JobParsedDetail, col_name)) == val)

        try:
            rows = session.execute(stmt).scalars().all()
        except Exception:
            logger.warning(
                "TTF segment query failed at tier %d",
                tier_num,
                exc_info=True,
            )
            continue

        if len(rows) < _MIN_SAMPLE:
            continue

        durations = sorted(rows)
        n = len(durations)
        result = {
            "median_days": durations[n // 2],
            "p25_days": durations[int(n * 0.25)],
            "p75_days": durations[int(n * 0.75)],
            "avg_days": round(sum(durations) / n, 1),
            "sample_size": n,
            "tier_used": tier_num,
            "segment": scope_key,
        }

        # Cache the result
        try:
            mi = MarketIntel(
                scope_type="ttf",
                scope_key=scope_key,
                data_json=result,
                sample_size=n,
                expires_at=datetime.now(UTC) + timedelta(days=_CACHE_TTL_DAYS),
            )
            session.merge(mi)
            session.flush()
        except Exception:
            logger.warning("Failed to cache TTF segment stats", exc_info=True)

        return result

    return None


def get_time_to_fill_benchmarks(
    title: str,
    location: str | None,
    session: Session,
) -> dict:
    """Get estimated time-to-fill for similar roles.

    Based on how long similar jobs stay active in the database.
    Uses ``(last_seen_at - first_seen_at)`` as a proxy for fill duration.
    """
    stmt = select(Job.first_seen_at, Job.last_seen_at).where(
        Job.is_active.is_(False),
        Job.first_seen_at.isnot(None),
        Job.last_seen_at.isnot(None),
        func.lower(Job.title).contains(title.lower()),
    )

    if location:
        stmt = stmt.where(func.lower(Job.location).contains(location.lower()))

    stmt = stmt.limit(500)

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
        if row.first_seen_at and row.last_seen_at:
            days = (row.last_seen_at - row.first_seen_at).days
            if 3 <= days <= 365:
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
