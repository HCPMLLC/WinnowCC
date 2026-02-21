"""Employer analytics — cross-board funnel, cost, and attribution."""

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.distribution import JobDistribution
from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)


def get_funnel_by_board(
    employer_id: int,
    job_id: int | None,
    start_date: datetime | None,
    end_date: datetime | None,
    session: Session,
) -> dict:
    """Return funnel metrics grouped by board.

    Keys per board: impressions, clicks, applications, cost_spent.
    """
    stmt = (
        select(
            JobDistribution.board_connection_id,
            func.sum(JobDistribution.impressions).label("impressions"),
            func.sum(JobDistribution.clicks).label("clicks"),
            func.sum(JobDistribution.applications).label("applications"),
            func.sum(JobDistribution.cost_spent).label("cost_spent"),
        )
        .join(
            EmployerJob,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(EmployerJob.employer_id == employer_id)
        .group_by(JobDistribution.board_connection_id)
    )

    if job_id:
        stmt = stmt.where(EmployerJob.id == job_id)
    if start_date:
        stmt = stmt.where(JobDistribution.submitted_at >= start_date)
    if end_date:
        stmt = stmt.where(JobDistribution.submitted_at <= end_date)

    rows = session.execute(stmt).all()
    result: dict[str, dict] = {}
    for row in rows:
        board_id = str(row.board_connection_id)
        result[board_id] = {
            "impressions": int(row.impressions or 0),
            "clicks": int(row.clicks or 0),
            "applications": int(row.applications or 0),
            "cost_spent": float(row.cost_spent or 0),
        }
    return result


def get_cost_per_outcome(
    employer_id: int,
    start_date: datetime | None,
    end_date: datetime | None,
    session: Session,
) -> dict:
    """Return cost-per-outcome metrics.

    Includes cost_per_application, cost_per_click, and per-board breakdown.
    """
    stmt = (
        select(
            func.sum(JobDistribution.cost_spent).label("total_cost"),
            func.sum(JobDistribution.clicks).label("total_clicks"),
            func.sum(JobDistribution.applications).label("total_apps"),
        )
        .join(
            EmployerJob,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(EmployerJob.employer_id == employer_id)
    )
    if start_date:
        stmt = stmt.where(JobDistribution.submitted_at >= start_date)
    if end_date:
        stmt = stmt.where(JobDistribution.submitted_at <= end_date)

    row = session.execute(stmt).one_or_none()
    total_cost = float(row.total_cost or 0) if row else 0
    total_clicks = int(row.total_clicks or 0) if row else 0
    total_apps = int(row.total_apps or 0) if row else 0

    return {
        "total_cost": total_cost,
        "total_clicks": total_clicks,
        "total_applications": total_apps,
        "cost_per_click": (round(total_cost / total_clicks, 2) if total_clicks else 0),
        "cost_per_application": (
            round(total_cost / total_apps, 2) if total_apps else 0
        ),
    }


def get_overview(employer_id: int, session: Session) -> dict:
    """Summary analytics for the employer dashboard."""
    active_stmt = (
        select(func.count())
        .select_from(EmployerJob)
        .where(
            EmployerJob.employer_id == employer_id,
            EmployerJob.status == "active",
        )
    )
    active_jobs = session.execute(active_stmt).scalar() or 0

    dist_stmt = (
        select(
            func.sum(JobDistribution.impressions),
            func.sum(JobDistribution.clicks),
            func.sum(JobDistribution.applications),
            func.sum(JobDistribution.cost_spent),
        )
        .join(
            EmployerJob,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(EmployerJob.employer_id == employer_id)
    )
    row = session.execute(dist_stmt).one_or_none()

    return {
        "active_jobs": active_jobs,
        "total_impressions": int(row[0] or 0) if row else 0,
        "total_clicks": int(row[1] or 0) if row else 0,
        "total_applications": int(row[2] or 0) if row else 0,
        "total_cost": float(row[3] or 0) if row else 0,
    }


def get_board_recommendations(employer_id: int, session: Session) -> list[dict]:
    """Recommend boards based on historical performance data."""
    stmt = (
        select(
            JobDistribution.board_connection_id,
            func.sum(JobDistribution.applications).label("apps"),
            func.sum(JobDistribution.clicks).label("clicks"),
            func.sum(JobDistribution.cost_spent).label("cost"),
        )
        .join(
            EmployerJob,
            JobDistribution.employer_job_id == EmployerJob.id,
        )
        .where(EmployerJob.employer_id == employer_id)
        .group_by(JobDistribution.board_connection_id)
        .order_by(func.sum(JobDistribution.applications).desc())
    )
    rows = session.execute(stmt).all()

    recommendations = []
    for row in rows:
        apps = int(row.apps or 0)
        cost = float(row.cost or 0)
        cpa = round(cost / apps, 2) if apps > 0 else 0

        recommendations.append(
            {
                "board_connection_id": str(row.board_connection_id),
                "total_applications": apps,
                "total_clicks": int(row.clicks or 0),
                "cost_per_application": cpa,
                "recommendation": (
                    "high_performer"
                    if apps > 10 and cpa < 50
                    else "moderate"
                    if apps > 0
                    else "insufficient_data"
                ),
            }
        )

    return recommendations
