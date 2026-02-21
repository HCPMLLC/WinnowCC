"""DEI sourcing recommendations — analyze diversity gaps and suggest channels."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)

# DEI sourcing channels by category
DEI_CHANNELS: list[dict] = [
    {
        "category": "hbcu",
        "name": "HBCU Career Network",
        "description": "Career boards at Historically Black Colleges and Universities",
        "url": "https://www.hbcuconnect.com/jobs/",
    },
    {
        "category": "veteran",
        "name": "Hire Heroes USA",
        "description": "Job board for military veterans and spouses",
        "url": "https://www.hireheroesusa.org/",
    },
    {
        "category": "veteran",
        "name": "Military.com",
        "description": "Career resources for military veterans",
        "url": "https://www.military.com/veteran-jobs",
    },
    {
        "category": "disability",
        "name": "AbilityJobs",
        "description": "Job board for people with disabilities",
        "url": "https://abilityjobs.com/",
    },
    {
        "category": "disability",
        "name": "Getting Hired",
        "description": "Inclusive employment board for people with disabilities",
        "url": "https://www.gettinghired.com/",
    },
    {
        "category": "women_in_tech",
        "name": "PowerToFly",
        "description": "Career platform for women and underrepresented talent",
        "url": "https://powertofly.com/",
    },
    {
        "category": "women_in_tech",
        "name": "Women Who Code",
        "description": "Global network for women in technology",
        "url": "https://www.womenwhocode.com/jobs",
    },
    {
        "category": "lgbtq",
        "name": "Out & Equal",
        "description": "LGBTQ+ workplace equality job board",
        "url": "https://outandequal.org/",
    },
    {
        "category": "indigenous",
        "name": "NativeJobs.com",
        "description": "Employment resources for Native Americans",
        "url": "https://www.nativejobs.com/",
    },
    {
        "category": "returning_citizens",
        "name": "70 Million Jobs",
        "description": "Job board for people with criminal records",
        "url": "https://www.70millionjobs.com/",
    },
]


def analyze_candidate_pool_diversity(
    employer_id: int,
    job_id: int,
    session: Session,
) -> dict:
    """Analyze the current applicant pool and identify sourcing gaps.

    Returns recommendations for additional DEI sourcing channels.
    """
    from app.models.distribution import JobDistribution

    job = session.get(EmployerJob, job_id)
    if not job:
        return {"error": "Job not found", "recommendations": []}

    # Get current distribution channels
    dist_stmt = select(JobDistribution).where(
        JobDistribution.employer_job_id == job_id,
    )
    distributions = list(session.execute(dist_stmt).scalars().all())

    # Get application count for context
    total_apps = sum(d.applications or 0 for d in distributions)

    # Build recommendations (all DEI channels not yet used)
    active_boards: set[str] = set()
    for d in distributions:
        if d.status in ("live", "pending"):
            from app.models.distribution import BoardConnection

            conn = session.get(BoardConnection, d.board_connection_id)
            if conn:
                active_boards.add(conn.board_type)

    recommendations = []
    for channel in DEI_CHANNELS:
        recommendations.append(
            {
                **channel,
                "priority": _compute_priority(channel, job, total_apps),
            }
        )

    # Sort by priority
    recommendations.sort(key=lambda r: r["priority"], reverse=True)

    return {
        "job_id": job_id,
        "total_applications": total_apps,
        "current_board_count": len(active_boards),
        "recommendations": recommendations[:5],
        "all_channels": recommendations,
    }


def _compute_priority(channel: dict, job: EmployerJob, total_apps: int) -> int:
    """Compute priority score (1-10) for a DEI channel recommendation."""
    priority = 5  # Base priority

    # Boost if few applications (needs more sourcing)
    if total_apps < 10:
        priority += 2
    elif total_apps < 25:
        priority += 1

    # Boost veteran channels for government-related roles
    title = (job.title or "").lower()
    desc = (job.description or "").lower()
    if channel["category"] == "veteran":
        if any(
            kw in title or kw in desc
            for kw in [
                "government",
                "federal",
                "military",
                "defense",
                "security clearance",
            ]
        ):
            priority += 2

    # Boost women_in_tech for tech roles
    if channel["category"] == "women_in_tech":
        if any(
            kw in title
            for kw in [
                "engineer",
                "developer",
                "programmer",
                "devops",
                "data scientist",
                "architect",
            ]
        ):
            priority += 2

    return min(10, priority)
