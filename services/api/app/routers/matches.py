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
from app.schemas.matches import (
    ApplicationStatusUpdateRequest,
    ApplicationStatusUpdateResponse,
    MatchResponse,
    MatchesRefreshResponse,
    ReferralUpdateRequest,
    ReferralUpdateResponse,
)
from app.services.auth import get_current_user, require_onboarded_user
from app.services.queue import get_queue
from app.services.job_pipeline import ingest_jobs_job, match_jobs_job
from app.services.trust_gate import require_allowed_trust
from app.services.matching import recalculate_interview_probability

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


def _deduplicate_matches(
    rows: list[tuple],
) -> list[tuple]:
    """Keep only the highest-scored match per job_id."""
    best: dict[int, tuple] = {}
    for match, job in rows:
        existing = best.get(job.id)
        if existing is None or (match.match_score or 0) > (existing[0].match_score or 0):
            best[job.id] = (match, job)
    return list(best.values())


def _refresh_skill_analysis(
    rows: list[tuple],
    profile_json: dict,
    jobs_by_id: dict,
) -> list[MatchResponse]:
    """Build MatchResponse list, refreshing skill analysis against current profile."""
    import re as _re
    from app.services.matching import _top_keywords, _tokenize

    profile_skills = [
        s.lower() for s in profile_json.get("skills", []) if isinstance(s, str)
    ]

    results = []
    for match, job in rows:
        reasons = dict(match.reasons or {})

        job_tokens = _tokenize(job.description_text)
        matched = [s for s in profile_skills if s in job_tokens]
        missing = [t for t in _top_keywords(job_tokens) if t not in profile_skills][:7]

        reasons["matched_skills"] = matched[:7]
        reasons["missing_skills"] = missing[:7]

        results.append(
            MatchResponse(
                id=match.id,
                job=JobResponse.model_validate(job),
                match_score=match.match_score,
                interview_readiness_score=match.interview_readiness_score,
                offer_probability=match.offer_probability,
                reasons=reasons,
                created_at=match.created_at,
                resume_score=match.resume_score,
                cover_letter_score=match.cover_letter_score,
                application_logistics_score=match.application_logistics_score,
                referred=match.referred,
                interview_probability=match.interview_probability,
                application_status=match.application_status,
            )
        )
    return results


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
            resume_score=match.resume_score,
            cover_letter_score=match.cover_letter_score,
            application_logistics_score=match.application_logistics_score,
            referred=match.referred,
            interview_probability=match.interview_probability,
            application_status=match.application_status,
        )
        for match, job in rows
    ]


@router.get(
    "/all",
    response_model=list[MatchResponse],
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def list_all_matches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MatchResponse]:
    """Return all matches for the current user (no recency cutoff)."""
    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(Match.user_id == user.id)
        .order_by(Match.match_score.desc())
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
            resume_score=match.resume_score,
            cover_letter_score=match.cover_letter_score,
            application_logistics_score=match.application_logistics_score,
            referred=match.referred,
            interview_probability=match.interview_probability,
            application_status=match.application_status,
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
        resume_score=match.resume_score,
        cover_letter_score=match.cover_letter_score,
        application_logistics_score=match.application_logistics_score,
        referred=match.referred,
        interview_probability=match.interview_probability,
        application_status=match.application_status,
    )


@router.patch(
    "/{match_id}/referred",
    response_model=ReferralUpdateResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def update_referral(
    match_id: int,
    body: ReferralUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReferralUpdateResponse:
    """Toggle referral status for a match and recalculate interview probability."""
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    match.referred = body.referred
    match.interview_probability = recalculate_interview_probability(match)
    session.commit()

    return ReferralUpdateResponse(
        id=match.id,
        referred=match.referred,
        interview_probability=match.interview_probability,
    )


@router.patch(
    "/{match_id}/status",
    response_model=ApplicationStatusUpdateResponse,
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def update_application_status(
    match_id: int,
    body: ApplicationStatusUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationStatusUpdateResponse:
    """Update application tracking status for a match.

    Valid statuses: saved, applied, interviewing, rejected, offer
    """
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    match.application_status = body.status
    session.commit()

    return ApplicationStatusUpdateResponse(
        id=match.id,
        application_status=match.application_status,
    )
