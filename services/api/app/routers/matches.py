from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.user import User
from app.schemas.jobs import JobResponse
from app.schemas.matches import MatchResponse, MatchesRefreshResponse
from app.services.auth import get_current_user, require_onboarded_user
from app.services.queue import get_queue
from app.services.job_pipeline import ingest_jobs_job, match_jobs_job
from app.services.trust_gate import require_allowed_trust

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _latest_profile_version(session: Session, user_id: int) -> int:
    stmt = (
        select(CandidateProfile.version)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    version = session.execute(stmt).scalar()
    return int(version or 0)


def _build_ingest_query(profile: dict, candidate: Candidate | None) -> dict:
    preferences = profile.get("preferences", {}) if isinstance(profile, dict) else {}
    search_terms = preferences.get("target_titles") or []
    search = search_terms[0] if search_terms else ""
    if not search:
        search = _first_experience_title(profile)

    locations = preferences.get("locations") or []
    location = locations[0] if locations else ""
    if not location:
        location = _basics_location(profile)
    if not location and candidate is not None:
        desired = candidate.desired_locations or []
        location = desired[0] if desired else ""

    return {"search": search, "location": location}


def _first_experience_title(profile: dict) -> str:
    if not isinstance(profile, dict):
        return ""
    experience = profile.get("experience", [])
    if not experience:
        return ""
    title = experience[0].get("title") if isinstance(experience[0], dict) else ""
    return title or ""


def _basics_location(profile: dict) -> str:
    if not isinstance(profile, dict):
        return ""
    basics = profile.get("basics", {}) if isinstance(profile.get("basics", {}), dict) else {}
    return basics.get("location") or ""


@router.post(
    "/refresh",
    response_model=MatchesRefreshResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def refresh_matches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MatchesRefreshResponse:
    profile_version = _latest_profile_version(session, user.id)
    profile = session.execute(
        select(CandidateProfile).where(
            CandidateProfile.user_id == user.id, CandidateProfile.version == profile_version
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    ingest_query = _build_ingest_query(profile.profile_json, candidate)
    queue = get_queue()
    queue.enqueue(ingest_jobs_job, ingest_query)
    job = queue.enqueue(match_jobs_job, user.id, profile_version)
    return MatchesRefreshResponse(status="queued", job_id=job.id)


@router.get(
    "",
    response_model=list[MatchResponse],
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def list_matches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MatchResponse]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user.id, Job.posted_at.is_not(None), Job.posted_at >= cutoff
        )
        .order_by(Match.match_score.desc())
        .limit(5)
    )
    rows = session.execute(stmt).all()
    return [
        MatchResponse(
            id=match.id,
            job=JobResponse.model_validate(job),
            match_score=match.match_score,
            interview_readiness_score=match.interview_readiness_score,
            offer_probability=match.offer_probability,
            reasons=match.reasons,
            created_at=match.created_at,
        )
        for match, job in rows
    ]


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def get_match(
    match_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MatchResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.id == match_id,
            Match.user_id == user.id,
            Job.posted_at.is_not(None),
            Job.posted_at >= cutoff,
        )
    )
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Match not found.")
    match, job = row
    return MatchResponse(
        id=match.id,
        job=JobResponse.model_validate(job),
        match_score=match.match_score,
        interview_readiness_score=match.interview_readiness_score,
        offer_probability=match.offer_probability,
        reasons=match.reasons,
        created_at=match.created_at,
    )
