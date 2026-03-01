"""Recruiter pipeline analytics: funnel, time-to-hire, conversions, sources."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

STAGES = ["sourced", "qualified", "interviewing", "offered", "hired", "rejected"]


def get_pipeline_funnel(
    session: Session,
    recruiter_profile_id: int,
    job_id: int | None = None,
) -> list[dict]:
    """Count candidates at each pipeline stage."""
    stmt = (
        select(
            RecruiterPipelineCandidate.stage,
            func.count(RecruiterPipelineCandidate.id),
        )
        .where(RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id)
        .group_by(RecruiterPipelineCandidate.stage)
    )
    if job_id:
        stmt = stmt.where(RecruiterPipelineCandidate.recruiter_job_id == job_id)
    rows = session.execute(stmt).all()
    counts = {stage: 0 for stage in STAGES}
    for stage_name, count in rows:
        counts[stage_name] = count
    return [{"stage": s, "count": counts.get(s, 0)} for s in STAGES]


def get_time_to_hire(
    session: Session,
    recruiter_profile_id: int,
) -> dict:
    """Compute time-to-hire stats from pipeline entry to 'hired' stage.

    Uses RecruiterActivity stage_change events with new_stage='hired',
    combined with pipeline candidate created_at.
    """
    # Find hired events
    hired_activities = (
        session.execute(
            select(RecruiterActivity).where(
                RecruiterActivity.recruiter_profile_id == recruiter_profile_id,
                RecruiterActivity.activity_type == "stage_change",
            )
        )
        .scalars()
        .all()
    )

    days_list: list[float] = []
    for activity in hired_activities:
        meta = activity.activity_metadata or {}
        if meta.get("new_stage") != "hired":
            continue
        if not activity.pipeline_candidate_id:
            continue

        pc = session.get(RecruiterPipelineCandidate, activity.pipeline_candidate_id)
        if not pc or not pc.created_at:
            continue

        hired_at = activity.created_at
        if not hired_at:
            continue
        delta = (hired_at - pc.created_at).total_seconds() / 86400
        if delta >= 0:
            days_list.append(delta)

    if not days_list:
        return {
            "count": 0,
            "avg_days": None,
            "median_days": None,
            "p75_days": None,
        }

    days_list.sort()
    n = len(days_list)
    avg = sum(days_list) / n
    median = days_list[n // 2]
    p75_idx = int(n * 0.75)
    p75 = days_list[min(p75_idx, n - 1)]

    return {
        "count": n,
        "avg_days": round(avg, 1),
        "median_days": round(median, 1),
        "p75_days": round(p75, 1),
    }


def get_stage_conversion_rates(
    session: Session,
    recruiter_profile_id: int,
) -> list[dict]:
    """Compute conversion rates between adjacent pipeline stages."""
    funnel = get_pipeline_funnel(session, recruiter_profile_id)
    counts = {item["stage"]: item["count"] for item in funnel}

    # Cumulative: each stage includes all candidates who passed through it
    # (candidates at later stages also passed earlier stages)
    stage_order = [s for s in STAGES if s != "rejected"]
    cumulative: dict[str, int] = {}
    running = 0
    for s in reversed(stage_order):
        running += counts.get(s, 0)
        cumulative[s] = running

    conversions = []
    for i in range(len(stage_order) - 1):
        from_stage = stage_order[i]
        to_stage = stage_order[i + 1]
        from_count = cumulative.get(from_stage, 0)
        to_count = cumulative.get(to_stage, 0)
        rate = round(to_count / from_count * 100, 1) if from_count else 0
        conversions.append(
            {
                "from_stage": from_stage,
                "to_stage": to_stage,
                "from_count": from_count,
                "to_count": to_count,
                "rate": rate,
            }
        )
    return conversions


def get_source_effectiveness(
    session: Session,
    recruiter_profile_id: int,
) -> list[dict]:
    """Group pipeline candidates by source and compare outcomes."""
    stmt = (
        select(
            RecruiterPipelineCandidate.source,
            RecruiterPipelineCandidate.stage,
            func.count(RecruiterPipelineCandidate.id),
        )
        .where(RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id)
        .group_by(
            RecruiterPipelineCandidate.source,
            RecruiterPipelineCandidate.stage,
        )
    )
    rows = session.execute(stmt).all()

    sources: dict[str, dict] = {}
    for source, stage_name, count in rows:
        src = source or "unknown"
        if src not in sources:
            sources[src] = {"source": src, "total": 0, "hired": 0}
        sources[src]["total"] += count
        if stage_name == "hired":
            sources[src]["hired"] += count

    result = []
    for data in sources.values():
        total = data["total"]
        hired = data["hired"]
        data["hire_rate"] = round(hired / total * 100, 1) if total else 0
        result.append(data)

    result.sort(key=lambda x: x["total"], reverse=True)
    return result
