from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match


@dataclass(frozen=True)
class MatchResult:
    match_score: int
    interview_readiness_score: int
    offer_probability: int
    reasons: dict
    resume_score: int
    application_logistics_score: int
    interview_probability: int


def compute_matches(session: Session, user_id: int, profile_version: int) -> list[Match]:
    profile = _get_profile(session, user_id, profile_version)
    if profile is None:
        return []
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    jobs = (
        session.execute(
            select(Job).where(Job.posted_at.is_not(None), Job.posted_at >= cutoff)
        )
        .scalars()
        .all()
    )
    scored: list[tuple[Job, MatchResult]] = []
    for job in jobs:
        scored.append((job, _score_job(job, profile.profile_json, candidate)))

    scored.sort(key=lambda item: item[1].match_score, reverse=True)
    top = scored[:50]

    session.execute(
        delete(Match).where(
            Match.user_id == user_id, Match.profile_version == profile_version
        )
    )

    matches: list[Match] = []
    for job, result in top:
        match = Match(
            user_id=user_id,
            job_id=job.id,
            profile_version=profile_version,
            match_score=result.match_score,
            interview_readiness_score=result.interview_readiness_score,
            offer_probability=result.offer_probability,
            reasons=result.reasons,
            resume_score=result.resume_score,
            application_logistics_score=result.application_logistics_score,
            cover_letter_score=50,  # Default until cover letter is generated
            referred=False,
            interview_probability=result.interview_probability,
        )
        session.add(match)
        matches.append(match)
    session.commit()
    return matches


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


def _score_job(job: Job, profile_json: dict, candidate: Candidate | None) -> MatchResult:
    skills = [s.lower() for s in profile_json.get("skills", []) if isinstance(s, str)]
    preferences = profile_json.get("preferences", {}) if isinstance(profile_json, dict) else {}

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
    missing_skills = [token for token in _top_keywords(job_tokens) if token not in skills][:7]
    skill_score = min(40, int(len(matched_skills) * 4))

    location_score = _location_score(job, preferences)
    salary_score = _salary_score(job, preferences)
    years_score = _years_score(candidate, job)

    match_score = min(100, skill_score + title_score + location_score + salary_score + years_score)

    evidence_strength = _evidence_strength(profile_json, matched_skills)
    gaps_severity = min(20, len(missing_skills) * 2)
    readiness = int(
        (match_score * 0.6)
        + (evidence_strength * 0.2)
        + ((20 - gaps_severity) * 0.2)
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
    resume_score = _compute_resume_score(job, profile_json, candidate, matched_skills, missing_skills)
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


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9+.#]+", text.lower()) if len(token) >= 3}


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), 1)


def _top_keywords(tokens: set[str]) -> list[str]:
    return sorted(tokens)


def _location_score(job: Job, preferences: dict) -> int:
    remote_ok = preferences.get("remote_ok")
    locations = [loc.lower() for loc in preferences.get("locations", []) if isinstance(loc, str)]
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
    experience = profile_json.get("experience", []) if isinstance(profile_json, dict) else []
    bullets = []
    for item in experience:
        bullets.extend(item.get("bullets") or [])
    matched = 0
    for bullet in bullets:
        if any(skill in bullet.lower() for skill in matched_skills):
            matched += 1
    return min(100, matched * 10)


def _evidence_refs(profile_json: dict, matched_skills: list[str]) -> list[str]:
    experience = profile_json.get("experience", []) if isinstance(profile_json, dict) else []
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
    "greenhouse": 85,
    "lever": 82,
    "workday": 78,
    "linkedin": 75,
    "indeed": 70,
    "glassdoor": 72,
    "remotive": 80,
    "themuse": 75,
    "adzuna": 68,
    "arbeitnow": 70,
    "jobicy": 75,
    "default": 70,
}


def _compute_resume_score(
    job: Job, profile_json: dict, candidate: Candidate | None, matched_skills: list[str], missing_skills: list[str]
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
    skill_match_ratio = len(matched_skills) / min(job_skill_count, len(skills) if skills else 1)
    skill_component = min(100, int(skill_match_ratio * 100))

    # Title component (0-100): alignment with target titles
    preferences = profile_json.get("preferences", {}) if isinstance(profile_json, dict) else {}
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
        days_old = (datetime.now(timezone.utc) - job.posted_at).days
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


def recalculate_interview_probability(match: Match) -> int:
    """Recalculate P_i for an existing match (e.g., after referral toggle)."""
    return _compute_interview_probability(
        resume_score=match.resume_score or 50,
        cover_letter_score=match.cover_letter_score or 50,
        application_logistics_score=match.application_logistics_score or 70,
        referred=match.referred,
    )
