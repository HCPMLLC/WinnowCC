"""Talent pipeline — silver medalist CRM for employers."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)


def add_to_pipeline(
    employer_id: int,
    candidate_id: int,
    source_job_id: int | None,
    status: str,
    tags: list[str] | None,
    notes: str | None,
    session: Session,
) -> dict:
    """Add a candidate to the employer's talent pipeline."""
    from app.models.talent_pipeline import TalentPipeline

    # Check for existing entry
    stmt = select(TalentPipeline).where(
        TalentPipeline.employer_id == employer_id,
        TalentPipeline.candidate_profile_id == candidate_id,
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing:
        existing.pipeline_status = status
        if tags is not None:
            existing.tags = tags
        if notes is not None:
            existing.notes = notes
        existing.updated_at = datetime.now(UTC)
        session.flush()
        return {"id": existing.id, "status": "updated"}

    entry = TalentPipeline(
        employer_id=employer_id,
        candidate_profile_id=candidate_id,
        source_job_id=source_job_id,
        pipeline_status=status,
        tags=tags or [],
        notes=notes,
        consent_given=False,
    )
    session.add(entry)
    session.flush()
    return {"id": entry.id, "status": "created"}


def search_pipeline(
    employer_id: int,
    filters: dict,
    limit: int = 50,
    offset: int = 0,
    session: Session | None = None,
) -> list[dict]:
    """Search the talent pipeline with filters."""
    from app.models.talent_pipeline import TalentPipeline

    if not session:
        return []

    stmt = select(TalentPipeline).where(TalentPipeline.employer_id == employer_id)

    if filters.get("status"):
        stmt = stmt.where(TalentPipeline.pipeline_status == filters["status"])
    if filters.get("min_score"):
        stmt = stmt.where(TalentPipeline.match_score >= filters["min_score"])

    stmt = stmt.order_by(TalentPipeline.updated_at.desc()).offset(offset).limit(limit)

    entries = list(session.execute(stmt).scalars().all())
    return [_serialize(e, session) for e in entries]


def suggest_pipeline_candidates(
    employer_id: int,
    new_job_id: int,
    session: Session,
) -> list[dict]:
    """Find pipeline candidates that match a new job posting."""
    from app.models.talent_pipeline import TalentPipeline

    job = session.get(EmployerJob, new_job_id)
    if not job:
        return []

    # Get all pipeline candidates for this employer
    stmt = (
        select(TalentPipeline)
        .where(
            TalentPipeline.employer_id == employer_id,
            TalentPipeline.pipeline_status.in_(
                ["silver_medalist", "warm_lead", "nurturing"]
            ),
        )
        .order_by(TalentPipeline.match_score.desc().nullslast())
        .limit(20)
    )
    candidates = list(session.execute(stmt).scalars().all())

    results = []
    for entry in candidates:
        profile = session.get(CandidateProfile, entry.candidate_profile_id)
        if not profile:
            continue

        results.append(
            {
                "pipeline_id": entry.id,
                "candidate_profile_id": entry.candidate_profile_id,
                "pipeline_status": entry.pipeline_status,
                "original_match_score": entry.match_score,
                "tags": entry.tags or [],
                "notes": entry.notes,
                "last_contacted_at": (
                    entry.last_contacted_at.isoformat()
                    if entry.last_contacted_at
                    else None
                ),
            }
        )

    return results


def auto_add_silver_medalists(
    employer_id: int,
    job_id: int,
    session: Session,
) -> dict:
    """Auto-add interview-stage candidates as silver medalists.

    Called when a job is filled. Adds candidates who reached
    the interview stage but weren't hired.
    """
    from app.models.match import Match
    from app.models.talent_pipeline import TalentPipeline

    # Find candidates who were interviewing for this job
    # but didn't get hired
    match_stmt = select(Match).where(
        Match.job_id == job_id,
        Match.application_status.in_(["interviewing", "screening"]),
    )
    matches = list(session.execute(match_stmt).scalars().all())

    added = 0
    for match in matches:
        # Check if already in pipeline
        exists_stmt = select(TalentPipeline).where(
            TalentPipeline.employer_id == employer_id,
            TalentPipeline.candidate_profile_id == match.candidate_id,
        )
        if session.execute(exists_stmt).scalar_one_or_none():
            continue

        entry = TalentPipeline(
            employer_id=employer_id,
            candidate_profile_id=match.candidate_id,
            source_job_id=job_id,
            pipeline_status="silver_medalist",
            match_score=match.match_score,
            tags=["auto-added"],
            consent_given=False,
        )
        session.add(entry)
        added += 1

    if added:
        session.flush()

    return {"job_id": job_id, "silver_medalists_added": added}


def update_pipeline_entry(
    pipeline_id: int,
    employer_id: int,
    updates: dict,
    session: Session,
) -> dict | None:
    """Update a pipeline entry."""
    from app.models.talent_pipeline import TalentPipeline

    stmt = select(TalentPipeline).where(
        TalentPipeline.id == pipeline_id,
        TalentPipeline.employer_id == employer_id,
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if not entry:
        return None

    for field in [
        "pipeline_status",
        "tags",
        "notes",
        "last_contacted_at",
        "next_followup_at",
        "consent_given",
        "consent_date",
    ]:
        if field in updates:
            setattr(entry, field, updates[field])

    entry.updated_at = datetime.now(UTC)
    session.flush()
    return _serialize(entry, session)


def remove_from_pipeline(
    pipeline_id: int,
    employer_id: int,
    session: Session,
) -> bool:
    """Remove a candidate from the pipeline."""
    from app.models.talent_pipeline import TalentPipeline

    stmt = select(TalentPipeline).where(
        TalentPipeline.id == pipeline_id,
        TalentPipeline.employer_id == employer_id,
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if not entry:
        return False
    session.delete(entry)
    return True


def _serialize(entry, session: Session) -> dict:
    """Serialize a pipeline entry to dict."""
    return {
        "id": entry.id,
        "candidate_profile_id": entry.candidate_profile_id,
        "pipeline_status": entry.pipeline_status,
        "match_score": entry.match_score,
        "tags": entry.tags or [],
        "notes": entry.notes,
        "source_job_id": entry.source_job_id,
        "last_contacted_at": (
            entry.last_contacted_at.isoformat() if entry.last_contacted_at else None
        ),
        "next_followup_at": (
            entry.next_followup_at.isoformat() if entry.next_followup_at else None
        ),
        "consent_given": entry.consent_given,
        "created_at": (entry.created_at.isoformat() if entry.created_at else None),
    }
