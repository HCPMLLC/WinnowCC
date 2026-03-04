from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match

MIN_MATCH_SCORE = 45


@dataclass(frozen=True)
class MatchResult:
    match_score: int
    interview_readiness_score: int
    offer_probability: int
    reasons: dict
    resume_score: int
    application_logistics_score: int
    interview_probability: int
    semantic_similarity: float | None = None


def compute_cosine_similarity(
    vec_a: list[float] | None, vec_b: list[float] | None
) -> float | None:
    """Compute cosine similarity between two embedding vectors.

    Returns a value between 0.0 and 1.0, or None if either vector is missing.
    Uses pure Python math (no numpy dependency).
    """
    if vec_a is None or vec_b is None:
        return None
    if len(vec_a) != len(vec_b) or len(vec_a) == 0:
        return None

    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return None
    similarity = dot / (mag_a * mag_b)
    return max(0.0, min(1.0, similarity))


def compute_blended_match_score(deterministic: int, semantic: float | None) -> int:
    """Blend deterministic keyword score with semantic similarity.

    65% deterministic + 35% semantic. Falls back to deterministic-only
    when semantic similarity is not available.
    """
    if semantic is None:
        return deterministic
    semantic_score = int(semantic * 100)
    blended = int(deterministic * 0.65 + semantic_score * 0.35)
    return max(0, min(100, blended))


def compute_matches(
    session: Session, user_id: int, profile_version: int
) -> list[Match]:
    from app.services.billing import get_plan_tier, get_tier_limit

    profile = _get_profile(session, user_id, profile_version)
    if profile is None:
        return []
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()

    profile_embedding = _get_embedding_list(profile.embedding)

    # Determine allowed job sources based on candidate tier
    tier = get_plan_tier(candidate)
    allowed_sources = get_tier_limit(tier, "job_sources") or ["board"]

    # Board jobs: 7-day cutoff; employer/recruiter: 30-day cutoff
    board_cutoff = datetime.now(UTC) - timedelta(days=7)
    extended_cutoff = datetime.now(UTC) - timedelta(days=30)

    source_filters = []
    if "board" in allowed_sources:
        source_filters.append(
            (Job.source.not_in(["employer", "recruiter"]))
            & (Job.posted_at >= board_cutoff)
        )
    if "employer" in allowed_sources:
        source_filters.append(
            (Job.source == "employer") & (Job.posted_at >= extended_cutoff)
        )
    if "recruiter" in allowed_sources:
        source_filters.append(
            (Job.source == "recruiter") & (Job.posted_at >= extended_cutoff)
        )

    jobs = (
        session.execute(
            select(Job).where(
                Job.posted_at.is_not(None),
                Job.is_active.is_not(False),
                or_(*source_filters),
            )
        )
        .scalars()
        .all()
    )
    scored: list[tuple[Job, MatchResult]] = []
    for job in jobs:
        result = _score_job(job, profile.profile_json, candidate)

        # Blend in semantic similarity when embeddings are available
        job_embedding = _get_embedding_list(job.embedding)
        semantic_sim = compute_cosine_similarity(profile_embedding, job_embedding)
        blended = compute_blended_match_score(result.match_score, semantic_sim)

        result = MatchResult(
            match_score=blended,
            interview_readiness_score=result.interview_readiness_score,
            offer_probability=result.offer_probability,
            reasons=result.reasons,
            resume_score=result.resume_score,
            application_logistics_score=result.application_logistics_score,
            interview_probability=result.interview_probability,
            semantic_similarity=semantic_sim,
        )
        scored.append((job, result))

    scored.sort(key=lambda item: item[1].match_score, reverse=True)
    top = scored[:50]

    from app.services.match_explainer import generate_match_explanation

    top_job_ids = [job.id for job, _ in top]

    # Delete stale matches: user's matches whose job is NOT in the new
    # top-50 list AND the user hasn't interacted with them.
    if top_job_ids:
        session.execute(
            delete(Match).where(
                Match.user_id == user_id,
                Match.job_id.not_in(top_job_ids),
                Match.application_status.is_(None),
            )
        )
    else:
        session.execute(
            delete(Match).where(
                Match.user_id == user_id,
                Match.application_status.is_(None),
            )
        )

    # Upsert matches: insert new ones, update scoring fields on conflict
    # while preserving user-interaction fields (application_status, referred).
    matches: list[tuple[Match, Job]] = []
    for job, result in top:
        matched_skills = result.reasons.get("matched_skills", [])
        if result.match_score >= 40:
            explanation = None  # Will be generated after flush
        else:
            explanation = (
                f"Partial match based on your "
                f"{', '.join(matched_skills[:2]) if matched_skills else 'experience'}."
            )

        values = {
            "user_id": user_id,
            "job_id": job.id,
            "profile_version": profile_version,
            "match_score": result.match_score,
            "interview_readiness_score": result.interview_readiness_score,
            "offer_probability": result.offer_probability,
            "reasons": result.reasons,
            "resume_score": result.resume_score,
            "application_logistics_score": result.application_logistics_score,
            "cover_letter_score": 50,
            "referred": False,
            "interview_probability": result.interview_probability,
            "semantic_similarity": result.semantic_similarity,
            "match_explanation": explanation,
        }

        stmt = pg_insert(Match).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_match_user_job",
            set_={
                "profile_version": stmt.excluded.profile_version,
                "match_score": stmt.excluded.match_score,
                "interview_readiness_score": stmt.excluded.interview_readiness_score,
                "offer_probability": stmt.excluded.offer_probability,
                "reasons": stmt.excluded.reasons,
                "resume_score": stmt.excluded.resume_score,
                "application_logistics_score": stmt.excluded.application_logistics_score,
                "cover_letter_score": stmt.excluded.cover_letter_score,
                "interview_probability": stmt.excluded.interview_probability,
                "semantic_similarity": stmt.excluded.semantic_similarity,
                "match_explanation": stmt.excluded.match_explanation,
            },
        )
        result_proxy = session.execute(stmt)

        # Fetch the match row so we can generate explanations
        match = session.execute(
            select(Match).where(
                Match.user_id == user_id, Match.job_id == job.id
            )
        ).scalar_one()
        matches.append((match, job))

    # Generate LLM explanations for qualifying matches
    for match, job in matches:
        if match.match_score >= 40:
            try:
                match.match_explanation = generate_match_explanation(
                    match, job, profile
                )
            except Exception:
                matched_skills = (match.reasons or {}).get("matched_skills", [])
                skills_text = (
                    ", ".join(matched_skills[:2]) if matched_skills else "experience"
                )
                match.match_explanation = f"Matched based on your {skills_text}."

    session.commit()
    return [m for m, _ in matches]


def _get_profile(
    session: Session, user_id: int, profile_version: int
) -> CandidateProfile | None:
    if profile_version > 0:
        stmt = select(CandidateProfile).where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.version == profile_version,
        )
    else:
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
    return session.execute(stmt).scalars().first()


def _score_job(
    job: Job, profile_json: dict, candidate: Candidate | None
) -> MatchResult:
    skills = [s.lower() for s in profile_json.get("skills", []) if isinstance(s, str)]
    preferences = (
        profile_json.get("preferences", {}) if isinstance(profile_json, dict) else {}
    )

    title = job.title.lower()
    title_tokens = _tokenize(title)
    target_titles = [t.lower() for t in preferences.get("target_titles", [])]
    title_score = 0
    if target_titles:
        max_overlap = max(
            (_overlap(title_tokens, _tokenize(t)) for t in target_titles), default=0
        )
        title_score = int(max_overlap * 20)

    job_tokens = _tokenize(job.description_text)
    matched_skills = [s for s in skills if s in job_tokens]
    missing_skills = [
        token for token in _top_keywords(job_tokens) if token not in skills
    ][:7]
    skill_score = min(40, int(len(matched_skills) * 4))

    location_score = _location_score(job, preferences)
    salary_score = _salary_score(job, preferences)
    years_score = _years_score(candidate, job)

    match_score = min(
        100, skill_score + title_score + location_score + salary_score + years_score
    )

    evidence_strength = _evidence_strength(profile_json, matched_skills)
    gaps_severity = min(20, len(missing_skills) * 2)
    readiness = int(
        (match_score * 0.6) + (evidence_strength * 0.2) + ((20 - gaps_severity) * 0.2)
    )
    readiness = max(0, min(100, readiness))

    offer_probability = int(
        (match_score * 0.5) + (readiness * 0.4) + (_years_fit_bonus(candidate) * 0.1)
    )
    offer_probability = max(0, min(100, offer_probability))

    reasons = {
        "matched_skills": matched_skills[:7],
        "missing_skills": missing_skills[:7],
        "title_alignment": title_score,
        "location_fit": location_score,
        "salary_fit": salary_score,
        "evidence_refs": _evidence_refs(profile_json, matched_skills),
    }

    # Compute new interview probability scores
    resume_score = _compute_resume_score(
        job, profile_json, candidate, matched_skills, missing_skills
    )
    application_logistics_score = _compute_application_logistics_score(job)
    cover_letter_score = 50  # Default until cover letter is generated
    interview_probability = _compute_interview_probability(
        resume_score=resume_score,
        cover_letter_score=cover_letter_score,
        application_logistics_score=application_logistics_score,
        referred=False,
    )

    return MatchResult(
        match_score=match_score,
        interview_readiness_score=readiness,
        offer_probability=offer_probability,
        reasons=reasons,
        resume_score=resume_score,
        application_logistics_score=application_logistics_score,
        interview_probability=interview_probability,
    )


def _score_posted_job(posted_job, profile_json: dict) -> MatchResult:
    """Score a candidate profile against a RecruiterJob or EmployerJob.

    These models use different field names than Job (e.g. ``description``
    instead of ``description_text``, ``remote_policy`` instead of
    ``remote_flag``).  We build a lightweight proxy that maps to the
    attributes ``_score_job`` expects.

    For sourced candidates whose preferences are empty, we synthesise
    preferences from resume data (job titles → target_titles, profile
    location → locations) so they score fairly.
    """

    class _JobProxy:
        pass

    proxy = _JobProxy()
    proxy.title = posted_job.title or ""
    proxy.description_text = (
        (posted_job.description or "")
        + "\n"
        + (getattr(posted_job, "requirements", None) or "")
    )
    proxy.remote_flag = (posted_job.remote_policy or "").lower() == "remote"
    proxy.location = posted_job.location or ""
    proxy.salary_min = posted_job.salary_min
    proxy.salary_max = posted_job.salary_max
    proxy.posted_at = posted_job.posted_at or getattr(posted_job, "created_at", None)
    proxy.source = "recruiter"

    # Enrich empty preferences from resume data so sourced candidates
    # don't lose points for missing preference fields.
    enriched = dict(profile_json) if profile_json else {}
    prefs = enriched.get("preferences") or {}
    prefs = dict(prefs)

    if not prefs.get("target_titles"):
        titles = []
        for exp in enriched.get("experience", []):
            t = exp.get("title", "").strip()
            if t and t not in titles:
                titles.append(t)
        if titles:
            prefs["target_titles"] = titles

    if not prefs.get("locations"):
        loc = enriched.get("location", "")
        if loc:
            prefs["locations"] = [loc]

    enriched["preferences"] = prefs

    # Expand multi-word skills into individual tokens so that
    # "Contract Management" matches when both "contract" and
    # "management" appear in the job description.
    raw_skills = enriched.get("skills", [])
    seen: set[str] = set()
    expanded: list[str] = []
    for s in raw_skills:
        name = s if isinstance(s, str) else s.get("name", "")
        if not name:
            continue
        low = name.lower()
        if low not in seen:
            seen.add(low)
            expanded.append(name)
        for tok in _tokenize(name):
            if tok not in seen:
                seen.add(tok)
                expanded.append(tok)
    enriched["skills"] = expanded

    # Build a lightweight Candidate stand-in for years scoring.
    candidate_proxy = None
    yrs = enriched.get("years_experience")
    if yrs is None:
        # Estimate from experience entries
        experience = enriched.get("experience", [])
        if experience:
            yrs = len(experience) * 2  # rough heuristic
    if yrs is not None:

        class _CandProxy:
            years_experience = None

        candidate_proxy = _CandProxy()
        candidate_proxy.years_experience = yrs

    return _score_job(proxy, enriched, candidate_proxy)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9+.#]+", text.lower())
        if len(token) >= 3
    }


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), 1)


_STOP = {
    "the",
    "and",
    "for",
    "are",
    "you",
    "our",
    "with",
    "this",
    "that",
    "will",
    "have",
    "from",
    "your",
    "can",
    "all",
    "has",
    "not",
    "but",
    "they",
    "been",
    "their",
    "which",
    "about",
    "would",
    "make",
    "like",
    "just",
    "over",
    "such",
    "also",
    "into",
    "year",
    "some",
    "than",
    "them",
    "other",
    "new",
    "more",
    "experience",
    "work",
    "team",
    "role",
    "ability",
    "strong",
    "must",
    "required",
    "preferred",
    "years",
    "including",
    "working",
    "knowledge",
    "skills",
    "using",
}


def _top_keywords(tokens: set[str]) -> list[str]:
    return sorted(t for t in tokens if t not in _STOP)


def _extract_skills_from_text(text: str) -> list[str]:
    """Extract skill-like keywords from text using tokenization."""
    if not text or not text.strip():
        return []
    tokens = _tokenize(text)
    # Filter to tokens that look like meaningful skills (3+ chars, not stop words)
    return sorted(t for t in tokens if t not in _STOP)


def _location_score(job: Job, preferences: dict) -> int:
    remote_ok = preferences.get("remote_ok")
    locations = [
        loc.lower() for loc in preferences.get("locations", []) if isinstance(loc, str)
    ]
    if job.remote_flag and remote_ok:
        return 15
    if locations:
        if any(loc in job.location.lower() for loc in locations):
            return 15
        return 0
    return 5


def _salary_score(job: Job, preferences: dict) -> int:
    min_pref = preferences.get("salary_min")
    max_pref = preferences.get("salary_max")
    if job.salary_min is None or job.salary_max is None or min_pref is None:
        return 5
    if job.salary_max < min_pref:
        return 0
    if max_pref is not None and job.salary_min > max_pref:
        return 0
    return 10


def _years_score(candidate: Candidate | None, job: Job) -> int:
    if candidate is None or candidate.years_experience is None:
        return 5
    if candidate.years_experience >= 5:
        return 15
    if candidate.years_experience >= 2:
        return 10
    return 5


def _years_fit_bonus(candidate: Candidate | None) -> int:
    if candidate is None or candidate.years_experience is None:
        return 50
    return min(100, 30 + candidate.years_experience * 10)


def _evidence_strength(profile_json: dict, matched_skills: list[str]) -> int:
    experience = (
        profile_json.get("experience", []) if isinstance(profile_json, dict) else []
    )
    bullets = []
    for item in experience:
        bullets.extend(item.get("bullets") or [])
    matched = 0
    for bullet in bullets:
        if any(skill in bullet.lower() for skill in matched_skills):
            matched += 1
    return min(100, matched * 10)


def _evidence_refs(profile_json: dict, matched_skills: list[str]) -> list[str]:
    experience = (
        profile_json.get("experience", []) if isinstance(profile_json, dict) else []
    )
    refs = []
    for item in experience:
        for bullet in item.get("bullets") or []:
            if any(skill in bullet.lower() for skill in matched_skills):
                refs.append(bullet[:200])
            if len(refs) >= 5:
                return refs
    return refs


# Platform benchmark scores for application logistics
PLATFORM_SCORES = {
    "employer": 90,
    "recruiter": 85,
    "greenhouse": 85,
    "lever": 82,
    "workday": 78,
    "linkedin": 75,
    "indeed": 70,
    "glassdoor": 72,
    "remotive": 80,
    "themuse": 75,
    "adzuna": 68,
    "jobicy": 75,
    "default": 70,
}


def _compute_resume_score(
    job: Job,
    profile_json: dict,
    candidate: Candidate | None,
    matched_skills: list[str],
    missing_skills: list[str],
) -> int:
    """
    Compute Resume Score (R_s) using the formula:
    R_s = (skill_component * 0.40) + (title_component * 0.15) +
          (evidence_component * 0.25) + (gap_penalty_component * 0.20)
    """
    skills = [s.lower() for s in profile_json.get("skills", []) if isinstance(s, str)]
    job_tokens = _tokenize(job.description_text)

    # Skill component (0-100): ratio of matched skills to job requirements
    job_skill_count = max(len([t for t in job_tokens if len(t) >= 3]), 1)
    skill_match_ratio = len(matched_skills) / min(
        job_skill_count, len(skills) if skills else 1
    )
    skill_component = min(100, int(skill_match_ratio * 100))

    # Title component (0-100): alignment with target titles
    preferences = (
        profile_json.get("preferences", {}) if isinstance(profile_json, dict) else {}
    )
    target_titles = [t.lower() for t in preferences.get("target_titles", [])]
    title_tokens = _tokenize(job.title.lower())
    title_component = 50  # default
    if target_titles:
        max_overlap = max(
            (_overlap(title_tokens, _tokenize(t)) for t in target_titles), default=0
        )
        title_component = int(max_overlap * 100)

    # Evidence component (0-100): bullet points mentioning skills
    evidence_component = _evidence_strength(profile_json, matched_skills)

    # Gap penalty component (0-100): inverse of missing skills severity
    gap_severity = min(100, len(missing_skills) * 10)
    gap_penalty_component = 100 - gap_severity

    # Weighted sum
    r_s = int(
        (skill_component * 0.40)
        + (title_component * 0.15)
        + (evidence_component * 0.25)
        + (gap_penalty_component * 0.20)
    )
    return max(0, min(100, r_s))


def _compute_application_logistics_score(job: Job) -> int:
    """
    Compute Application Logistics Score (A_s) using the formula:
    A_s = (timing_score * 0.6) + (platform_score * 0.4)

    Timing: 100 if ≤10 days old, linear decay after
    Platform: Mapped benchmark scores based on job source
    """
    # Timing score
    timing_score = 100
    if job.posted_at:
        days_old = (datetime.now(UTC) - job.posted_at).days
        if days_old <= 10:
            timing_score = 100
        elif days_old <= 30:
            # Linear decay from 100 to 50 between day 10 and day 30
            timing_score = int(100 - ((days_old - 10) * 2.5))
        else:
            # Continue decay after 30 days
            timing_score = max(10, int(50 - (days_old - 30)))

    # Platform score based on job source
    source_lower = job.source.lower() if job.source else "default"
    platform_score = PLATFORM_SCORES.get(source_lower, PLATFORM_SCORES["default"])

    # Weighted sum
    a_s = int((timing_score * 0.6) + (platform_score * 0.4))
    return max(0, min(100, a_s))


def _compute_interview_probability(
    resume_score: int,
    cover_letter_score: int,
    application_logistics_score: int,
    referred: bool = False,
) -> int:
    """
    Compute Interview Probability (P_i) using the formula:
    P_i = [(W_r × R_s) + (W_c × C_s) + (W_a × A_s)] × M_net

    Where:
    - W_r = 0.70 (Resume weight), R_s = Resume Score
    - W_c = 0.20 (Cover Letter weight), C_s = Cover Letter Score
    - W_a = 0.10 (Application Logistics weight), A_s = Application Logistics Score
    - M_net = 8.0 if referred, else 1.0
    """
    m_net = 8.0 if referred else 1.0

    raw_score = (
        (0.70 * resume_score)
        + (0.20 * cover_letter_score)
        + (0.10 * application_logistics_score)
    )

    p_i = int(raw_score * m_net)
    # Cap at 100 for display
    return max(0, min(100, p_i))


def _get_embedding_list(value) -> list[float] | None:
    """Normalize an embedding value to a plain list of floats.

    pgvector returns numpy arrays, JSON columns return lists, and None stays None.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return value
    # pgvector / numpy array
    try:
        return list(value)
    except TypeError:
        return None


def recalculate_interview_probability(match: Match) -> int:
    """Recalculate P_i for an existing match (e.g., after referral toggle)."""
    return _compute_interview_probability(
        resume_score=match.resume_score or 50,
        cover_letter_score=match.cover_letter_score or 50,
        application_logistics_score=match.application_logistics_score or 70,
        referred=match.referred,
    )


def generate_ips_coaching(
    resume_score: int | None,
    cover_letter_score: int | None,
    application_logistics_score: int | None,
    matched_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
    job_posted_days_ago: int | None = None,
) -> dict:
    """Generate actionable coaching tips for each IPS component.

    Rule-based (no LLM) — fast and cheap.  Returns structured tips dict.
    """
    tips: dict[str, list[str]] = {
        "resume": [],
        "cover_letter": [],
        "logistics": [],
        "overall": [],
    }
    r_s = resume_score or 50
    c_s = cover_letter_score or 50
    a_s = application_logistics_score or 70
    matched = matched_skills or []
    missing = missing_skills or []

    # --- Resume tips ---
    if missing:
        kw = ", ".join(missing[:5])
        tips["resume"].append(f"Add these keywords to your resume: {kw}")
    if r_s < 50:
        tips["resume"].append(
            "Your resume has significant gaps for this role. "
            "Highlight transferable skills from past experience."
        )
    elif r_s < 70:
        tips["resume"].append(
            "Strengthen evidence for your matched skills by adding "
            "quantified achievements (numbers, percentages, outcomes)."
        )
    if len(matched) < 3:
        tips["resume"].append(
            "You match few required skills. Consider whether this "
            "role aligns with your experience."
        )

    # --- Cover letter tips ---
    if c_s < 40:
        tips["cover_letter"].append(
            "A strong cover letter could significantly boost your "
            "score. Address the hiring manager by name if possible."
        )
        tips["cover_letter"].append(
            "Reference specific company values or recent news to show genuine interest."
        )
    elif c_s < 60:
        tips["cover_letter"].append(
            "Tailor your cover letter to mention the specific skills this job requires."
        )
    elif c_s < 80:
        tips["cover_letter"].append(
            "Your cover letter is solid. Include a brief example of "
            "a relevant accomplishment to push it further."
        )

    # --- Logistics tips ---
    if job_posted_days_ago is not None:
        if job_posted_days_ago > 20:
            tips["logistics"].append(
                f"This job was posted {job_posted_days_ago} days ago. "
                "Apply soon — older postings may be closing."
            )
        elif job_posted_days_ago <= 5:
            tips["logistics"].append(
                "Great timing! This job was just posted. Early "
                "applicants often get more attention."
            )
    if a_s < 60:
        tips["logistics"].append(
            "Apply directly on the company website for a potential "
            "boost to your application logistics score."
        )

    # --- Overall tips ---
    overall = (r_s * 0.70) + (c_s * 0.20) + (a_s * 0.10)
    if overall >= 75:
        tips["overall"].append("You're a strong candidate! Focus on interview prep.")
    elif overall >= 50:
        tips["overall"].append(
            "You have a reasonable shot. Addressing the tips above "
            "could meaningfully improve your chances."
        )
    else:
        tips["overall"].append(
            "This is a stretch role. Consider building skills in "
            "the missing areas or look for closer matches."
        )

    return tips


# ---------------------------------------------------------------------------
# Recruiter & Employer job → candidate matching
# ---------------------------------------------------------------------------


def _latest_platform_profiles(session: Session) -> list:
    """Return latest-version CandidateProfiles for opted-in platform users."""
    latest_sub = (
        select(
            CandidateProfile.user_id,
            func.max(CandidateProfile.version).label("mv"),
        )
        .where(CandidateProfile.user_id.is_not(None))
        .group_by(CandidateProfile.user_id)
    ).subquery()

    return (
        session.execute(
            select(CandidateProfile)
            .join(
                latest_sub,
                (CandidateProfile.user_id == latest_sub.c.user_id)
                & (CandidateProfile.version == latest_sub.c.mv),
            )
            .where(
                CandidateProfile.open_to_opportunities == True,  # noqa: E712
                CandidateProfile.profile_visibility.in_(["public", "anonymous"]),
            )
        )
        .scalars()
        .all()
    )


def find_top_candidates_for_recruiter_job(
    session: Session,
    recruiter_job,
    recruiter_user_id: int,
    limit: int = 100,
) -> list[dict]:
    """Find top candidates for a recruiter job.

    Searches two pools:
      A) Platform candidates — opted-in, latest version per user.
      B) Recruiter's own sourced candidates (user_id IS NULL,
         profile_json.sourced_by_user_id == recruiter_user_id).
    """
    # Pool A: platform candidates
    platform_profiles = _latest_platform_profiles(session)

    # Pool B: recruiter-sourced candidates
    sourced_profiles = (
        session.execute(
            select(CandidateProfile).where(
                CandidateProfile.user_id.is_(None),
                cast(CandidateProfile.profile_json["sourced_by_user_id"], String)
                == str(recruiter_user_id),
            )
        )
        .scalars()
        .all()
    )

    all_profiles = platform_profiles + sourced_profiles

    # Get job embedding for semantic blending (same approach as candidate
    # matching in compute_matches).
    job_embedding = _get_embedding_list(getattr(recruiter_job, "embedding", None))

    scored: list[dict] = []
    for cp in all_profiles:
        pj = cp.profile_json or {}
        result = _score_posted_job(recruiter_job, pj)
        if result.match_score > 0:
            # Blend deterministic score with semantic similarity
            profile_embedding = _get_embedding_list(cp.embedding)
            semantic_sim = compute_cosine_similarity(profile_embedding, job_embedding)
            blended = compute_blended_match_score(result.match_score, semantic_sim)
            scored.append(
                {
                    "id": cp.id,
                    "match_score": blended,
                    "matched_skills": result.reasons.get("matched_skills", []),
                }
            )

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]


def find_top_candidates_for_employer_job(
    session: Session,
    employer_job,
    limit: int = 100,
) -> list[dict]:
    """Find top candidates for an employer job (platform candidates only).

    Returns dicts compatible with ``TopCandidateResult`` schema.
    """
    platform_profiles = _latest_platform_profiles(session)

    scored: list[dict] = []
    for cp in platform_profiles:
        pj = cp.profile_json or {}
        result = _score_posted_job(employer_job, pj)
        if result.match_score > 0:
            skills = [
                s if isinstance(s, str) else s.get("name", "")
                for s in pj.get("skills", [])
            ]
            scored.append(
                {
                    "id": cp.id,
                    "name": pj.get("name", "Unknown"),
                    "headline": pj.get("headline"),
                    "location": pj.get("location"),
                    "years_experience": pj.get("years_experience"),
                    "top_skills": skills[:5],
                    "matched_skills": result.reasons.get("matched_skills", []),
                    "match_score": result.match_score,
                    "profile_visibility": cp.profile_visibility or "private",
                }
            )

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
