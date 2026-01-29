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

    return MatchResult(
        match_score=match_score,
        interview_readiness_score=readiness,
        offer_probability=offer_probability,
        reasons=reasons,
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
