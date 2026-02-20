"""Recruiter CRM service: clients, pipeline, activities, team, dashboard."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.recruiter import RecruiterProfile, RecruiterTeamMember
from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def create_client(
    session: Session, profile: RecruiterProfile, data: dict
) -> RecruiterClient:
    client = RecruiterClient(recruiter_profile_id=profile.id, **data)
    session.add(client)
    session.flush()
    _log_activity(
        session,
        profile,
        activity_type="client_created",
        client_id=client.id,
        subject=f"Created client: {client.company_name}",
    )
    session.commit()
    session.refresh(client)
    return client


def list_clients(
    session: Session,
    profile: RecruiterProfile,
    status_filter: str | None = None,
) -> list[RecruiterClient]:
    stmt = select(RecruiterClient).where(
        RecruiterClient.recruiter_profile_id == profile.id
    )
    if status_filter:
        stmt = stmt.where(RecruiterClient.status == status_filter)
    stmt = stmt.order_by(RecruiterClient.created_at.desc())
    return list(session.execute(stmt).scalars().all())


def get_client(
    session: Session, profile: RecruiterProfile, client_id: int
) -> RecruiterClient | None:
    return session.execute(
        select(RecruiterClient).where(
            RecruiterClient.id == client_id,
            RecruiterClient.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()


def update_client(
    session: Session,
    profile: RecruiterProfile,
    client_id: int,
    data: dict,
) -> RecruiterClient | None:
    client = get_client(session, profile, client_id)
    if client is None:
        return None
    for field, value in data.items():
        setattr(client, field, value)
    session.commit()
    session.refresh(client)
    return client


def delete_client(
    session: Session, profile: RecruiterProfile, client_id: int
) -> bool:
    client = get_client(session, profile, client_id)
    if client is None:
        return False
    session.delete(client)
    session.commit()
    return True


def get_client_job_count(session: Session, client_id: int) -> int:
    return (
        session.execute(
            select(func.count(RecruiterJob.id)).where(
                RecruiterJob.client_id == client_id
            )
        ).scalar()
        or 0
    )


# ---------------------------------------------------------------------------
# Pipeline Candidates
# ---------------------------------------------------------------------------


def add_to_pipeline(
    session: Session, profile: RecruiterProfile, data: dict
) -> RecruiterPipelineCandidate:
    pc = RecruiterPipelineCandidate(recruiter_profile_id=profile.id, **data)
    session.add(pc)
    session.flush()
    name = _resolve_candidate_name(session, pc)
    _log_activity(
        session,
        profile,
        activity_type="pipeline_added",
        pipeline_candidate_id=pc.id,
        recruiter_job_id=pc.recruiter_job_id,
        subject=f"Added {name} to pipeline",
    )
    session.commit()
    session.refresh(pc)
    return pc


def list_pipeline(
    session: Session,
    profile: RecruiterProfile,
    stage: str | None = None,
    job_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[RecruiterPipelineCandidate]:
    stmt = select(RecruiterPipelineCandidate).where(
        RecruiterPipelineCandidate.recruiter_profile_id == profile.id
    )
    if stage:
        stmt = stmt.where(RecruiterPipelineCandidate.stage == stage)
    if job_id:
        stmt = stmt.where(RecruiterPipelineCandidate.recruiter_job_id == job_id)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                RecruiterPipelineCandidate.external_name.ilike(pattern),
                RecruiterPipelineCandidate.external_email.ilike(pattern),
            )
        )
    stmt = stmt.order_by(RecruiterPipelineCandidate.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def update_pipeline_candidate(
    session: Session,
    profile: RecruiterProfile,
    candidate_id: int,
    data: dict,
) -> RecruiterPipelineCandidate | None:
    pc = session.execute(
        select(RecruiterPipelineCandidate).where(
            RecruiterPipelineCandidate.id == candidate_id,
            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if pc is None:
        return None

    old_stage = pc.stage
    for field, value in data.items():
        setattr(pc, field, value)

    # Auto-log stage changes
    new_stage = data.get("stage")
    if new_stage and new_stage != old_stage:
        name = _resolve_candidate_name(session, pc)
        _log_activity(
            session,
            profile,
            activity_type="stage_change",
            pipeline_candidate_id=pc.id,
            recruiter_job_id=pc.recruiter_job_id,
            subject=f"{name}: {old_stage} → {new_stage}",
            activity_metadata={"old_stage": old_stage, "new_stage": new_stage},
        )

    session.commit()
    session.refresh(pc)
    return pc


def delete_pipeline_candidate(
    session: Session, profile: RecruiterProfile, candidate_id: int
) -> bool:
    pc = session.execute(
        select(RecruiterPipelineCandidate).where(
            RecruiterPipelineCandidate.id == candidate_id,
            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if pc is None:
        return False
    session.delete(pc)
    session.commit()
    return True


def bulk_delete_pipeline(
    session: Session, profile: RecruiterProfile, ids: list[int]
) -> int:
    """Delete multiple pipeline candidates owned by this recruiter."""
    pcs = (
        session.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.id.in_(ids),
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
            )
        )
        .scalars()
        .all()
    )
    for pc in pcs:
        session.delete(pc)
    session.commit()
    return len(pcs)


def bulk_update_pipeline_stage(
    session: Session, profile: RecruiterProfile, ids: list[int], new_stage: str
) -> int:
    """Update stage on multiple pipeline candidates, logging each change."""
    pcs = (
        session.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.id.in_(ids),
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
            )
        )
        .scalars()
        .all()
    )
    updated = 0
    for pc in pcs:
        old_stage = pc.stage
        if old_stage != new_stage:
            pc.stage = new_stage
            name = _resolve_candidate_name(session, pc)
            _log_activity(
                session,
                profile,
                activity_type="stage_change",
                pipeline_candidate_id=pc.id,
                recruiter_job_id=pc.recruiter_job_id,
                subject=f"{name}: {old_stage} → {new_stage}",
                activity_metadata={"old_stage": old_stage, "new_stage": new_stage},
            )
            updated += 1
    session.commit()
    return updated


def resolve_candidate_name(
    session: Session, pc: RecruiterPipelineCandidate
) -> str:
    """Public version of name resolution."""
    return _resolve_candidate_name(session, pc)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


def log_activity(
    session: Session,
    profile: RecruiterProfile,
    user_id: int | None,
    data: dict,
) -> RecruiterActivity:
    # Remap 'metadata' → 'activity_metadata' (reserved in SQLAlchemy)
    if "metadata" in data:
        data["activity_metadata"] = data.pop("metadata")
    activity = RecruiterActivity(
        recruiter_profile_id=profile.id, user_id=user_id, **data
    )
    session.add(activity)
    session.commit()
    session.refresh(activity)
    return activity


def list_activities(
    session: Session,
    profile: RecruiterProfile,
    limit: int = 20,
    pipeline_candidate_id: int | None = None,
    job_id: int | None = None,
    client_id: int | None = None,
    since: datetime | None = None,
) -> list[RecruiterActivity]:
    stmt = select(RecruiterActivity).where(
        RecruiterActivity.recruiter_profile_id == profile.id
    )
    if pipeline_candidate_id:
        stmt = stmt.where(
            RecruiterActivity.pipeline_candidate_id == pipeline_candidate_id
        )
    if job_id:
        stmt = stmt.where(RecruiterActivity.recruiter_job_id == job_id)
    if client_id:
        stmt = stmt.where(RecruiterActivity.client_id == client_id)
    if since:
        stmt = stmt.where(RecruiterActivity.created_at >= since)
    stmt = stmt.order_by(RecruiterActivity.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


def invite_team_member(
    session: Session,
    profile: RecruiterProfile,
    email: str,
    role: str,
) -> RecruiterTeamMember | None:
    """Invite a team member. Returns None if seat limit exceeded."""
    from app.services.billing import RECRUITER_PLAN_LIMITS

    tier = profile.subscription_tier or "trial"
    limits = RECRUITER_PLAN_LIMITS.get(tier, RECRUITER_PLAN_LIMITS["trial"])
    max_seats = limits.get("seats", 1)
    if profile.seats_used >= max_seats:
        return None

    # Find or create the user
    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if user is None:
        return None  # User must exist on the platform

    # Check not already a member
    existing = session.execute(
        select(RecruiterTeamMember).where(
            RecruiterTeamMember.recruiter_profile_id == profile.id,
            RecruiterTeamMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    member = RecruiterTeamMember(
        recruiter_profile_id=profile.id,
        user_id=user.id,
        role=role,
    )
    session.add(member)
    profile.seats_used += 1
    session.commit()
    session.refresh(member)
    return member


def list_team_members(
    session: Session, profile: RecruiterProfile
) -> list[RecruiterTeamMember]:
    return list(
        session.execute(
            select(RecruiterTeamMember).where(
                RecruiterTeamMember.recruiter_profile_id == profile.id
            )
        )
        .scalars()
        .all()
    )


def remove_team_member(
    session: Session, profile: RecruiterProfile, member_id: int
) -> bool:
    member = session.execute(
        select(RecruiterTeamMember).where(
            RecruiterTeamMember.id == member_id,
            RecruiterTeamMember.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if member is None:
        return False
    session.delete(member)
    profile.seats_used = max(1, profile.seats_used - 1)
    session.commit()
    return True


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def get_dashboard_stats(session: Session, profile: RecruiterProfile) -> dict:
    total_active_jobs = (
        session.execute(
            select(func.count(RecruiterJob.id)).where(
                RecruiterJob.recruiter_profile_id == profile.id,
                RecruiterJob.status == "active",
            )
        ).scalar()
        or 0
    )
    total_pipeline = (
        session.execute(
            select(func.count(RecruiterPipelineCandidate.id)).where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
            )
        ).scalar()
        or 0
    )
    total_clients = (
        session.execute(
            select(func.count(RecruiterClient.id)).where(
                RecruiterClient.recruiter_profile_id == profile.id,
                RecruiterClient.status == "active",
            )
        ).scalar()
        or 0
    )
    total_placements = (
        session.execute(
            select(func.count(RecruiterPipelineCandidate.id)).where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                RecruiterPipelineCandidate.stage == "placed",
            )
        ).scalar()
        or 0
    )

    # Pipeline by stage
    stage_rows = (
        session.execute(
            select(
                RecruiterPipelineCandidate.stage,
                func.count(RecruiterPipelineCandidate.id),
            )
            .where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
            )
            .group_by(RecruiterPipelineCandidate.stage)
        )
        .all()
    )
    pipeline_by_stage = [
        {"stage": stage, "count": count} for stage, count in stage_rows
    ]

    # Recent activities
    recent = list_activities(session, profile, limit=10)

    return {
        "total_active_jobs": total_active_jobs,
        "total_pipeline_candidates": total_pipeline,
        "total_clients": total_clients,
        "total_placements": total_placements,
        "pipeline_by_stage": pipeline_by_stage,
        "recent_activities": recent,
        "subscription_tier": profile.subscription_tier or "trial",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_candidate_name(
    session: Session, pc: RecruiterPipelineCandidate
) -> str:
    """Resolve a display name from internal profile or external fields."""
    if pc.external_name:
        return pc.external_name
    if pc.candidate_profile_id:
        cp = session.get(CandidateProfile, pc.candidate_profile_id)
        if cp:
            pj = cp.profile_json or {}
            basics = pj.get("basics") or {}
            first = basics.get("first_name", "")
            last = basics.get("last_name", "")
            name = basics.get("name") or f"{first} {last}".strip()
            if name:
                return name
    return f"Candidate #{pc.id}"


def _log_activity(
    session: Session,
    profile: RecruiterProfile,
    *,
    activity_type: str,
    pipeline_candidate_id: int | None = None,
    recruiter_job_id: int | None = None,
    client_id: int | None = None,
    subject: str | None = None,
    activity_metadata: dict | None = None,
) -> None:
    """Internal helper to log an activity without committing."""
    activity = RecruiterActivity(
        recruiter_profile_id=profile.id,
        activity_type=activity_type,
        pipeline_candidate_id=pipeline_candidate_id,
        recruiter_job_id=recruiter_job_id,
        client_id=client_id,
        subject=subject,
        activity_metadata=activity_metadata,
    )
    session.add(activity)
