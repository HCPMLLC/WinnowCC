"""Recruiter CRM service: clients, pipeline, activities, team, dashboard."""

from __future__ import annotations

import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import asc, desc, func, or_, select
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
    contract_vehicle: str | None = None,
    search: str | None = None,
    sort_by: str = "company_name",
    sort_dir: str = "asc",
) -> list[RecruiterClient]:
    from sqlalchemy import asc as sa_asc
    from sqlalchemy import desc as sa_desc

    stmt = select(RecruiterClient).where(
        RecruiterClient.recruiter_profile_id == profile.id
    )
    if status_filter:
        stmt = stmt.where(RecruiterClient.status == status_filter)
    if contract_vehicle:
        stmt = stmt.where(RecruiterClient.contract_vehicle == contract_vehicle)
    if search:
        pattern = f"%{search}%"
        # Alias for parent join
        ParentClient = select(
            RecruiterClient.id,
            RecruiterClient.company_name.label("parent_name"),
        ).subquery()
        stmt = stmt.outerjoin(
            ParentClient,
            RecruiterClient.parent_client_id == ParentClient.c.id,
        )
        stmt = stmt.where(
            or_(
                RecruiterClient.company_name.ilike(pattern),
                RecruiterClient.industry.ilike(pattern),
                RecruiterClient.contract_vehicle.ilike(pattern),
                RecruiterClient.contact_name.ilike(pattern),
                RecruiterClient.contacts.cast(
                    sa.Text
                ).ilike(pattern),
                ParentClient.c.parent_name.ilike(pattern),
            )
        )

    # Sorting
    _sort_cols = {
        "company_name": RecruiterClient.company_name,
        "industry": RecruiterClient.industry,
        "contract_vehicle": RecruiterClient.contract_vehicle,
        "status": RecruiterClient.status,
        "created_at": RecruiterClient.created_at,
    }
    col = _sort_cols.get(sort_by, RecruiterClient.company_name)
    direction = sa_desc if sort_dir == "desc" else sa_asc
    stmt = stmt.order_by(direction(col))
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


def delete_client(session: Session, profile: RecruiterProfile, client_id: int) -> bool:
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


def get_client_job_summary(
    session: Session, profile_id: int, client_id: int
) -> dict:
    """Build job summary for a client and its children.

    Returns data shaped for ``ClientJobSummaryResponse``.
    """
    from app.schemas.recruiter_crm import (
        ClientJobGroup,
        ClientJobSummaryResponse,
        ContactJobGroup,
        JobSummaryItem,
    )

    # Fetch the client
    client = session.execute(
        select(RecruiterClient).where(
            RecruiterClient.id == client_id,
            RecruiterClient.recruiter_profile_id == profile_id,
        )
    ).scalar_one_or_none()
    if client is None:
        return None

    # Collect client IDs: self + children
    children = session.execute(
        select(RecruiterClient).where(
            RecruiterClient.parent_client_id == client_id,
            RecruiterClient.recruiter_profile_id == profile_id,
        )
    ).scalars().all()

    client_map = {client.id: (client.company_name, True)}
    for ch in children:
        client_map[ch.id] = (ch.company_name, False)

    all_ids = list(client_map.keys())

    # Fetch all jobs for these clients
    jobs = session.execute(
        select(RecruiterJob).where(
            RecruiterJob.client_id.in_(all_ids),
            RecruiterJob.recruiter_profile_id == profile_id,
        ).order_by(RecruiterJob.closes_at.desc().nulls_last())
    ).scalars().all()

    def _to_item(j: RecruiterJob) -> JobSummaryItem:
        cname = None
        cemail = None
        if j.primary_contact:
            cname = j.primary_contact.get("name")
            cemail = j.primary_contact.get("email")
        return JobSummaryItem(
            id=j.id,
            title=j.title,
            status=j.status,
            job_id_external=j.job_id_external,
            closes_at=j.closes_at,
            contact_name=cname,
            contact_email=cemail,
            positions_to_fill=j.positions_to_fill or 1,
            positions_filled=j.positions_filled or 0,
        )

    # Group by client + status
    by_client: dict[int, dict[str, list]] = {}
    for j in jobs:
        cid = j.client_id
        if cid not in by_client:
            by_client[cid] = {}
        by_client[cid].setdefault(j.status, []).append(_to_item(j))

    groups = []
    # Self first, then children alphabetically
    ordered_ids = [client.id] + sorted(
        [ch.id for ch in children],
        key=lambda cid: client_map[cid][0].lower(),
    )
    for cid in ordered_ids:
        if cid not in by_client:
            continue
        name, is_self = client_map[cid]
        status_jobs = by_client[cid]
        total = sum(len(v) for v in status_jobs.values())
        groups.append(ClientJobGroup(
            client_id=cid,
            client_name=name,
            is_self=is_self,
            jobs_by_status=status_jobs,
            total_jobs=total,
        ))

    # Group by primary contact
    by_contact: dict[str, list] = {}
    for j in jobs:
        key = "Unassigned"
        if j.primary_contact and j.primary_contact.get("name"):
            key = j.primary_contact["name"]
        by_contact.setdefault(key, []).append(j)

    contact_groups = []
    for cname in sorted(by_contact.keys()):
        cjobs = by_contact[cname]
        cemail = None
        for cj in cjobs:
            if cj.primary_contact and cj.primary_contact.get("email"):
                cemail = cj.primary_contact["email"]
                break
        items = [_to_item(j) for j in cjobs]
        contact_groups.append(ContactJobGroup(
            contact_name=cname,
            contact_email=cemail,
            jobs=items,
            total_jobs=len(items),
        ))

    return ClientJobSummaryResponse(
        client_id=client.id,
        client_name=client.company_name,
        groups=groups,
        by_contact=contact_groups,
        total_jobs=len(jobs),
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
    # Auto-evaluate stage rules (use savepoint so a missing table
    # or other DB error doesn't abort the outer transaction)
    try:
        from app.services.stage_rules import evaluate_rules

        nested = session.begin_nested()
        try:
            evaluate_rules(session, pc)
            nested.commit()
        except Exception:
            nested.rollback()
            logger.warning("Stage rule evaluation failed for pc %s", pc.id)
    except Exception:
        logger.warning("Stage rule evaluation failed for pc %s", pc.id)
    session.commit()
    session.refresh(pc)
    return pc


def _pipeline_base_query(
    profile: RecruiterProfile,
    stage: str | None = None,
    job_id: int | None = None,
    search: str | None = None,
    tags: list[str] | None = None,
    location: str | None = None,
    title: str | None = None,
    work_authorization: str | None = None,
    remote_preference: str | None = None,
    sort_by: str | None = None,
):
    """Build the shared WHERE clause for pipeline queries."""
    from app.models.candidate import Candidate

    # Determine if we need joins for filtering or sorting
    needs_profile_join = bool(
        location
        or title
        or work_authorization
        or remote_preference
        or sort_by in ("location", "title", "work_authorization", "remote_preference")
    )
    needs_candidate_join = bool(
        work_authorization
        or remote_preference
        or sort_by in ("work_authorization", "remote_preference")
    )

    stmt = select(RecruiterPipelineCandidate).where(
        RecruiterPipelineCandidate.recruiter_profile_id == profile.id
    )

    if needs_profile_join:
        stmt = stmt.outerjoin(
            CandidateProfile,
            RecruiterPipelineCandidate.candidate_profile_id == CandidateProfile.id,
        )
    if needs_candidate_join:
        stmt = stmt.outerjoin(
            Candidate,
            CandidateProfile.user_id == Candidate.user_id,
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
    if tags:
        for tag in tags:
            stmt = stmt.where(RecruiterPipelineCandidate.tags.contains([tag]))
    if location:
        pattern = f"%{location}%"
        stmt = stmt.where(
            or_(
                RecruiterPipelineCandidate.location.ilike(pattern),
                CandidateProfile.profile_json["location"].astext.ilike(pattern),
                CandidateProfile.profile_json["basics"]["location"].astext.ilike(pattern),
            )
        )
    if title:
        pattern = f"%{title}%"
        stmt = stmt.where(
            or_(
                RecruiterPipelineCandidate.current_title.ilike(pattern),
                CandidateProfile.profile_json["experience"][0]["title"].astext.ilike(pattern),
            )
        )
    if work_authorization:
        stmt = stmt.where(Candidate.work_authorization.ilike(f"%{work_authorization}%"))
    if remote_preference:
        stmt = stmt.where(Candidate.remote_preference.ilike(f"%{remote_preference}%"))
    return stmt


def count_pipeline(
    session: Session,
    profile: RecruiterProfile,
    stage: str | None = None,
    job_id: int | None = None,
    search: str | None = None,
    tags: list[str] | None = None,
    location: str | None = None,
    title: str | None = None,
    work_authorization: str | None = None,
    remote_preference: str | None = None,
) -> int:
    """Return the total count of pipeline candidates matching filters."""
    from sqlalchemy import func as sa_func

    base = _pipeline_base_query(
        profile, stage, job_id, search, tags,
        location, title, work_authorization, remote_preference,
    )
    count_stmt = select(sa_func.count()).select_from(base.subquery())
    return session.execute(count_stmt).scalar_one()


def list_pipeline(
    session: Session,
    profile: RecruiterProfile,
    stage: str | None = None,
    job_id: int | None = None,
    search: str | None = None,
    tags: list[str] | None = None,
    location: str | None = None,
    title: str | None = None,
    work_authorization: str | None = None,
    remote_preference: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[RecruiterPipelineCandidate]:
    from app.models.candidate import Candidate
    from app.models.recruiter_job_candidate import RecruiterJobCandidate as RJC

    stmt = _pipeline_base_query(
        profile, stage, job_id, search, tags,
        location, title, work_authorization, remote_preference,
        sort_by=sort_by,
    )

    # Determine sort column
    order_col: sa.ColumnElement = RecruiterPipelineCandidate.created_at
    if sort_by == "location":
        order_col = func.coalesce(
            CandidateProfile.profile_json["location"].astext,
            RecruiterPipelineCandidate.location,
        )
    elif sort_by == "title":
        order_col = func.coalesce(
            CandidateProfile.profile_json["experience"][0]["title"].astext,
            RecruiterPipelineCandidate.current_title,
        )
    elif sort_by == "work_authorization":
        order_col = Candidate.work_authorization
    elif sort_by == "remote_preference":
        order_col = Candidate.remote_preference
    elif sort_by == "job_match_count":
        order_col = (
            select(func.count(RJC.id))
            .where(
                RJC.candidate_profile_id
                == RecruiterPipelineCandidate.candidate_profile_id
            )
            .correlate(RecruiterPipelineCandidate)
            .scalar_subquery()
        )

    if sort_dir == "asc":
        stmt = stmt.order_by(asc(order_col).nulls_last())
    else:
        stmt = stmt.order_by(desc(order_col).nulls_last())

    stmt = stmt.offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def add_tags(
    session: Session,
    profile: RecruiterProfile,
    candidate_id: int,
    tags: list[str],
) -> RecruiterPipelineCandidate | None:
    """Add tags to a pipeline candidate (deduplicates)."""
    pc = session.execute(
        select(RecruiterPipelineCandidate).where(
            RecruiterPipelineCandidate.id == candidate_id,
            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if pc is None:
        return None
    existing = pc.tags or []
    merged = list(dict.fromkeys(existing + tags))
    pc.tags = merged
    session.flush()
    return pc


def remove_tags(
    session: Session,
    profile: RecruiterProfile,
    candidate_id: int,
    tags: list[str],
) -> RecruiterPipelineCandidate | None:
    """Remove tags from a pipeline candidate."""
    pc = session.execute(
        select(RecruiterPipelineCandidate).where(
            RecruiterPipelineCandidate.id == candidate_id,
            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
        )
    ).scalar_one_or_none()
    if pc is None:
        return None
    existing = pc.tags or []
    remove_set = set(tags)
    pc.tags = [t for t in existing if t not in remove_set]
    session.flush()
    return pc


def list_unique_tags(
    session: Session,
    profile: RecruiterProfile,
) -> list[str]:
    """Get all unique tags used by this recruiter (for autocomplete)."""
    rows = (
        session.execute(
            select(RecruiterPipelineCandidate.tags).where(
                RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
                RecruiterPipelineCandidate.tags.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    all_tags: set[str] = set()
    for tag_list in rows:
        if isinstance(tag_list, list):
            all_tags.update(tag_list)
    return sorted(all_tags)


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


def resolve_candidate_name(session: Session, pc: RecruiterPipelineCandidate) -> str:
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
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
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
    stage_rows = session.execute(
        select(
            RecruiterPipelineCandidate.stage,
            func.count(RecruiterPipelineCandidate.id),
        )
        .where(
            RecruiterPipelineCandidate.recruiter_profile_id == profile.id,
        )
        .group_by(RecruiterPipelineCandidate.stage)
    ).all()
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


def _resolve_candidate_name(session: Session, pc: RecruiterPipelineCandidate) -> str:
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


# ---------------------------------------------------------------------------
# Notifications & @mentions
# ---------------------------------------------------------------------------

import re

_MENTION_RE = re.compile(r"@(\w+)")


def create_note_with_mentions(
    session: Session,
    profile: RecruiterProfile,
    sender_user_id: int,
    pipeline_candidate_id: int,
    body: str,
) -> RecruiterActivity:
    """Create a note on a pipeline candidate, parsing @mentions.

    Mentioned team members receive notifications.
    """
    from app.models.recruiter_notification import RecruiterNotification

    activity = RecruiterActivity(
        recruiter_profile_id=profile.id,
        user_id=sender_user_id,
        pipeline_candidate_id=pipeline_candidate_id,
        activity_type="note",
        body=body,
        subject="Note added",
    )
    session.add(activity)
    session.flush()

    # Parse @mentions
    mentions = _MENTION_RE.findall(body)
    if mentions:
        # Resolve team member user IDs by email prefix or name
        team = (
            session.execute(
                select(RecruiterTeamMember).where(
                    RecruiterTeamMember.recruiter_profile_id == profile.id
                )
            )
            .scalars()
            .all()
        )

        team_user_ids: set[int] = set()
        for tm in team:
            if tm.user_id:
                user = session.get(User, tm.user_id)
                if user:
                    email_prefix = user.email.split("@")[0].lower()
                    name_lower = (user.name or "").lower().replace(" ", "")
                    for m in mentions:
                        if m.lower() in (email_prefix, name_lower):
                            team_user_ids.add(tm.user_id)

        for uid in team_user_ids:
            if uid == sender_user_id:
                continue
            notif = RecruiterNotification(
                recipient_user_id=uid,
                sender_user_id=sender_user_id,
                activity_id=activity.id,
                notification_type="mention",
                message=body[:500],
            )
            session.add(notif)

    return activity


def get_notifications(
    session: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> list:
    """Get notifications for a user."""
    from app.models.recruiter_notification import RecruiterNotification

    stmt = (
        select(RecruiterNotification)
        .where(RecruiterNotification.recipient_user_id == user_id)
        .order_by(RecruiterNotification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(RecruiterNotification.is_read.is_(False))
    return list(session.execute(stmt).scalars().all())


def mark_notification_read(
    session: Session,
    user_id: int,
    notification_id: int,
) -> bool:
    """Mark a notification as read. Returns True if found."""
    from app.models.recruiter_notification import RecruiterNotification

    notif = session.execute(
        select(RecruiterNotification).where(
            RecruiterNotification.id == notification_id,
            RecruiterNotification.recipient_user_id == user_id,
        )
    ).scalar_one_or_none()
    if notif is None:
        return False
    notif.is_read = True
    session.flush()
    return True


# ---------------------------------------------------------------------------
# Contact-Account Recognition (Phase 2)
# ---------------------------------------------------------------------------


def check_signup_email_matches(
    session: Session,
    new_user_email: str,
    new_user_id: int,
    new_user_role: str,
) -> None:
    """Check if a newly signed-up user's email matches any recruiter contacts
    or pipeline candidates. Creates notifications + activity log entries.

    Called from the signup endpoint. Does NOT auto-link anything — just
    creates awareness notifications for the owning recruiter.
    """
    from app.models.recruiter_notification import RecruiterNotification

    email_lower = new_user_email.lower().strip()
    role_label = new_user_role if new_user_role != "candidate" else "candidate"

    # --- 1) Check RecruiterClient contacts (JSONB) ---
    # PostgreSQL: contacts @> '[{"email": "x"}]'::jsonb
    import json

    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    pattern = json.dumps([{"email": email_lower}])
    client_matches = (
        session.execute(
            select(RecruiterClient).where(
                RecruiterClient.contacts.op("@>")(
                    sa.cast(pattern, PG_JSONB)
                )
            )
        )
        .scalars()
        .all()
    )

    # Also check legacy single-contact email field
    legacy_matches = (
        session.execute(
            select(RecruiterClient).where(
                func.lower(RecruiterClient.contact_email) == email_lower,
            )
        )
        .scalars()
        .all()
    )

    # Deduplicate by client id
    seen_client_ids: set[int] = set()
    all_client_matches: list[RecruiterClient] = []
    for c in list(client_matches) + list(legacy_matches):
        if c.id not in seen_client_ids:
            seen_client_ids.add(c.id)
            all_client_matches.append(c)

    for client in all_client_matches:
        # Find the contact entry to get their role
        contact_role = None
        contact_name = None
        if client.contacts:
            for ct in client.contacts:
                if (ct.get("email") or "").lower() == email_lower:
                    contact_role = ct.get("role")
                    first = ct.get("first_name", "")
                    last = ct.get("last_name", "")
                    contact_name = f"{first} {last}".strip()
                    break
        if not contact_name and client.contact_name:
            contact_name = client.contact_name

        # Get the recruiter's user_id for notification
        profile = session.get(RecruiterProfile, client.recruiter_profile_id)
        if not profile:
            continue

        role_desc = f" ({contact_role})" if contact_role else ""
        name_desc = contact_name or email_lower
        msg = (
            f"{name_desc}{role_desc} on {client.company_name} "
            f"has joined Winnow as a {role_label}."
        )

        # Log activity on the client
        activity = RecruiterActivity(
            recruiter_profile_id=profile.id,
            client_id=client.id,
            activity_type="contact_signup",
            subject=msg,
            activity_metadata={
                "new_user_id": new_user_id,
                "new_user_email": email_lower,
                "new_user_role": new_user_role,
                "contact_role": contact_role,
            },
        )
        session.add(activity)
        session.flush()

        # Create notification for the recruiter
        notif = RecruiterNotification(
            recipient_user_id=profile.user_id,
            sender_user_id=new_user_id,
            activity_id=activity.id,
            notification_type="contact_signup",
            message=msg,
        )
        session.add(notif)

    # --- 2) Check RecruiterPipelineCandidate external_email ---
    pipeline_matches = (
        session.execute(
            select(RecruiterPipelineCandidate).where(
                func.lower(
                    RecruiterPipelineCandidate.external_email
                ) == email_lower,
                RecruiterPipelineCandidate.candidate_profile_id.is_(None),
            )
        )
        .scalars()
        .all()
    )

    for pc in pipeline_matches:
        profile = session.get(
            RecruiterProfile, pc.recruiter_profile_id
        )
        if not profile:
            continue

        cand_name = pc.external_name or email_lower
        msg = (
            f"{cand_name}, a candidate in your pipeline, "
            f"has joined Winnow as a {role_label}."
        )

        activity = RecruiterActivity(
            recruiter_profile_id=profile.id,
            pipeline_candidate_id=pc.id,
            activity_type="candidate_signup",
            subject=msg,
            activity_metadata={
                "new_user_id": new_user_id,
                "new_user_email": email_lower,
                "new_user_role": new_user_role,
                "pipeline_candidate_id": pc.id,
            },
        )
        session.add(activity)
        session.flush()

        notif = RecruiterNotification(
            recipient_user_id=profile.user_id,
            sender_user_id=new_user_id,
            activity_id=activity.id,
            notification_type="candidate_signup",
            message=msg,
        )
        session.add(notif)
