from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select, text
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
    MatchesRefreshResponse,
    MatchResponse,
    ReferralUpdateRequest,
    ReferralUpdateResponse,
)
from app.services.auth import get_current_user, require_onboarded_user
from app.services.billing import (
    check_daily_limit,
    check_interview_prep_limit,
    get_plan_tier,
    get_tier_limit,
    increment_daily_counter,
    increment_interview_preps,
)
from app.services.job_pipeline import ingest_jobs_job, match_jobs_job
from app.services.matching import (
    _get_embedding_list,
    compute_cosine_similarity,
    generate_ips_coaching,
    recalculate_interview_probability,
)
from app.services.queue import get_queue
from app.services.trust_gate import require_allowed_trust

logger = logging.getLogger(__name__)

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
    basics = (
        profile.get("basics", {}) if isinstance(profile.get("basics", {}), dict) else {}
    )
    return basics.get("location") or ""


def _deduplicate_matches(
    rows: list[tuple],
) -> list[tuple]:
    """Keep only the highest-scored match per job_id."""
    best: dict[int, tuple] = {}
    for match, job in rows:
        existing = best.get(job.id)
        if existing is None or (match.match_score or 0) > (
            existing[0].match_score or 0
        ):
            best[job.id] = (match, job)
    return list(best.values())


def _refresh_skill_analysis(
    rows: list[tuple],
    profile_json: dict,
    jobs_by_id: dict,
) -> list[MatchResponse]:
    """Build MatchResponse list, refreshing skill analysis against current profile."""
    from app.services.matching import _tokenize, _top_keywords

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
                semantic_similarity=match.semantic_similarity,
                match_explanation=match.match_explanation,
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
            CandidateProfile.user_id == user.id,
            CandidateProfile.version == profile_version,
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    ingest_query = _build_ingest_query(profile.profile_json, candidate)
    queue = get_queue("critical")
    ingest_job = queue.enqueue(ingest_jobs_job, ingest_query)
    job = queue.enqueue(match_jobs_job, user.id, profile_version, depends_on=ingest_job)
    return MatchesRefreshResponse(status="queued", job_id=job.id)


@router.get(
    "/search",
    response_model=list[MatchResponse],
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def search_matches(
    request: Request,
    q: str = Query(..., min_length=2, max_length=500),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MatchResponse]:
    """Semantic search over jobs using embedding similarity.

    Requires starter or pro tier (gated by semantic_searches_per_day limit).
    """
    from app.services.embedding import generate_embedding

    # Check billing tier
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    check_daily_limit(
        session,
        user.id,
        tier,
        "semantic_searches",
        "semantic_searches_per_day",
        request=request,
    )

    # Generate embedding for query
    query_embedding = generate_embedding(q)

    # Try pgvector cosine distance operator first, fall back to Python
    try:
        rows = session.execute(
            text(
                """
                SELECT j.id, j.embedding <=> cast(:emb as vector) AS distance
                FROM jobs j
                WHERE j.embedding IS NOT NULL
                  AND j.is_active IS NOT FALSE
                ORDER BY distance ASC
                LIMIT :lim
                """
            ),
            {"emb": str(query_embedding), "lim": limit},
        ).fetchall()
        job_ids_with_sim = [(row[0], 1.0 - row[1]) for row in rows]
    except Exception:
        logger.info("pgvector <=> not available, falling back to Python cosine sim")
        # Fall back: load all job embeddings and compute in Python
        jobs_with_emb = session.execute(
            select(Job.id, Job.embedding).where(
                Job.embedding.is_not(None),
                Job.is_active.is_not(False),
            )
        ).all()
        scored = []
        for job_id, job_emb in jobs_with_emb:
            emb_list = _get_embedding_list(job_emb)
            sim = compute_cosine_similarity(query_embedding, emb_list)
            if sim is not None:
                scored.append((job_id, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        job_ids_with_sim = scored[:limit]

    if not job_ids_with_sim:
        increment_daily_counter(session, user.id, "semantic_searches")
        return []

    # Load full job objects
    job_id_list = [jid for jid, _ in job_ids_with_sim]
    sim_by_id = {jid: sim for jid, sim in job_ids_with_sim}

    jobs = session.execute(select(Job).where(Job.id.in_(job_id_list))).scalars().all()
    jobs_by_id = {j.id: j for j in jobs}

    # Build response in similarity order
    response = []
    for job_id in job_id_list:
        job = jobs_by_id.get(job_id)
        if job is None:
            continue
        sim = sim_by_id[job_id]
        response.append(
            MatchResponse(
                id=0,
                job=JobResponse.model_validate(job),
                match_score=int(sim * 100),
                interview_readiness_score=0,
                offer_probability=0,
                reasons={},
                created_at=datetime.now(UTC),
                semantic_similarity=round(sim, 4),
            )
        )

    increment_daily_counter(session, user.id, "semantic_searches")
    return response


@router.get(
    "",
    response_model=list[MatchResponse],
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def list_matches(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[MatchResponse]:
    # Determine tier-based limits
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    allowed_sources = get_tier_limit(tier, "job_sources") or ["board"]
    matches_visible = get_tier_limit(tier, "matches_visible") or 5

    cutoff = datetime.now(UTC) - timedelta(days=14)
    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user.id,
            Job.posted_at.is_not(None),
            Job.posted_at >= cutoff,
            Job.is_active.is_not(False),
        )
        .order_by(Match.match_score.desc())
    )
    rows = session.execute(stmt).all()

    # Filter to allowed sources
    rows = [
        (m, j)
        for m, j in rows
        if j.source in allowed_sources
        or (j.source not in ("employer", "recruiter") and "board" in allowed_sources)
    ]

    rows = _deduplicate_matches(rows)[:matches_visible]
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
            semantic_similarity=match.semantic_similarity,
            match_explanation=match.match_explanation,
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
    """Return all matches for the current user (no recency cutoff).

    Active jobs always show. Inactive jobs only show if the user has
    saved/applied (application_status is set).
    """
    # Determine tier-based source limits
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    allowed_sources = get_tier_limit(tier, "job_sources") or ["board"]

    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user.id,
            or_(
                Job.is_active.is_not(False),
                Match.application_status.is_not(None),
            ),
        )
        .order_by(Match.match_score.desc())
    )
    rows = session.execute(stmt).all()

    # Filter to allowed sources
    rows = [
        (m, j)
        for m, j in rows
        if j.source in allowed_sources
        or (j.source not in ("employer", "recruiter") and "board" in allowed_sources)
    ]

    rows = _deduplicate_matches(rows)
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
            semantic_similarity=match.semantic_similarity,
            match_explanation=match.match_explanation,
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
    stmt = (
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.id == match_id,
            Match.user_id == user.id,
            or_(
                Job.is_active.is_not(False),
                Match.application_status.is_not(None),
            ),
        )
    )
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Match not found.")
    match, job = row

    # Pro-tier coaching tips
    coaching = None
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    ips_detail = get_tier_limit(tier, "ips_detail")
    if ips_detail == "full_coaching":
        reasons = dict(match.reasons or {})
        days_ago = None
        if job.posted_at:
            days_ago = (datetime.now(UTC) - job.posted_at).days
        coaching = generate_ips_coaching(
            resume_score=match.resume_score,
            cover_letter_score=match.cover_letter_score,
            application_logistics_score=match.application_logistics_score,
            matched_skills=reasons.get("matched_skills"),
            missing_skills=reasons.get("missing_skills"),
            job_posted_days_ago=days_ago,
        )

    # Gap recommendations status
    from app.models.gap_recommendation import GapRecommendation

    gap_rec = session.execute(
        select(GapRecommendation).where(GapRecommendation.match_id == match_id)
    ).scalar_one_or_none()
    gap_recs_status = gap_rec.status if gap_rec else None

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
        semantic_similarity=match.semantic_similarity,
        match_explanation=match.match_explanation,
        coaching_tips=coaching,
        gap_recs_status=gap_recs_status,
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
    When status changes to 'interviewing', triggers interview prep generation.
    """
    from app.models.interview_prep import InterviewPrep

    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    old_status = match.application_status
    match.application_status = body.status

    interview_prep_status = None

    # Trigger interview prep when transitioning to "interviewing"
    if body.status == "interviewing" and old_status != "interviewing":
        # Check if prep already exists for this match
        existing_prep = session.execute(
            select(InterviewPrep).where(InterviewPrep.match_id == match_id)
        ).scalar_one_or_none()

        if existing_prep is None:
            candidate = session.execute(
                select(Candidate).where(Candidate.user_id == user.id)
            ).scalar_one_or_none()

            # Check billing — raises 403/429 if not allowed
            check_interview_prep_limit(session, user, candidate)

            # Create prep row and enqueue
            prep = InterviewPrep(
                user_id=user.id,
                match_id=match_id,
                job_id=match.job_id,
                status="pending",
            )
            session.add(prep)
            session.flush()

            increment_interview_preps(session, user.id)

            from app.services.interview_prep import generate_interview_prep_job

            queue = get_queue("default")
            queue.enqueue(generate_interview_prep_job, prep.id)

            interview_prep_status = "pending"
        else:
            interview_prep_status = existing_prep.status

    session.commit()

    return ApplicationStatusUpdateResponse(
        id=match.id,
        application_status=match.application_status,
        interview_prep_status=interview_prep_status,
    )


# ---------------------------------------------------------------------------
# Gap Closure Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/{match_id}/gap-recs",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def get_gap_recommendations(
    match_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Get or trigger gap closure recommendations for a match.

    First call creates the recommendation (checks billing limit), subsequent
    calls return current status / completed results.
    """
    from app.models.gap_recommendation import GapRecommendation
    from app.services.gap_recommendations import filter_for_free_tier

    # Verify match ownership
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    # Check for existing recommendation
    gap_rec = session.execute(
        select(GapRecommendation).where(GapRecommendation.match_id == match_id)
    ).scalar_one_or_none()

    if gap_rec is None:
        # Check billing limit
        candidate = session.execute(
            select(Candidate).where(Candidate.user_id == user.id)
        ).scalar_one_or_none()
        tier = get_plan_tier(candidate)
        check_daily_limit(
            session,
            user.id,
            tier,
            "gap_recommendations",
            "gap_recommendations_per_day",
            request=request,
        )

        # Create and enqueue
        gap_rec = GapRecommendation(
            user_id=user.id,
            match_id=match_id,
            job_id=match.job_id,
            status="pending",
        )
        session.add(gap_rec)
        session.flush()

        increment_daily_counter(session, user.id, "gap_recommendations")

        from app.services.gap_recommendations import generate_gap_recommendations_job

        queue = get_queue("default")
        queue.enqueue(generate_gap_recommendations_job, gap_rec.id)
        session.commit()

        return {"status": "pending", "recommendations": None}

    if gap_rec.status in ("pending", "processing"):
        return {"status": "pending", "recommendations": None}

    if gap_rec.status == "failed":
        return {
            "status": "failed",
            "error_message": gap_rec.error_message,
            "recommendations": None,
        }

    # Completed — apply tier filtering
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user.id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)
    recs = gap_rec.recommendations or {}
    if tier == "free":
        recs = filter_for_free_tier(recs)

    return {"status": "completed", "recommendations": recs}


@router.get(
    "/{match_id}/status-prediction",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def get_status_prediction(
    match_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Get AI-predicted status for an application.

    Only available for matches with application_status = 'applied'.
    """
    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    if match.application_status != "applied":
        raise HTTPException(
            status_code=400,
            detail="Status prediction only available for submitted applications",
        )

    from app.services.status_predictor import predict_application_status

    return predict_application_status(match_id, session)


@router.post(
    "/{match_id}/gap-recs/retry",
    dependencies=[Depends(require_onboarded_user), Depends(require_allowed_trust)],
)
def retry_gap_recommendations(
    match_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Retry a failed gap recommendation generation (no billing re-check)."""
    from app.models.gap_recommendation import GapRecommendation

    match = session.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user.id)
    ).scalar_one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found.")

    gap_rec = session.execute(
        select(GapRecommendation).where(GapRecommendation.match_id == match_id)
    ).scalar_one_or_none()
    if gap_rec is None:
        raise HTTPException(status_code=404, detail="No gap recommendations found.")
    if gap_rec.status != "failed":
        raise HTTPException(
            status_code=400, detail="Only failed recommendations can be retried."
        )

    gap_rec.status = "pending"
    gap_rec.error_message = None
    session.flush()

    from app.services.gap_recommendations import generate_gap_recommendations_job

    queue = get_queue("default")
    queue.enqueue(generate_gap_recommendations_job, gap_rec.id)
    session.commit()

    return {"status": "pending", "recommendations": None}
