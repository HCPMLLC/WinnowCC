"""Implicit preference learning from match status changes.

Accumulates behavioral signals (saved, applied, interviewing, offer, rejected)
and derives per-candidate weight multipliers for the 5 scoring components.
Starter/Pro only — free tier uses static scoring.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_preference_weights import CandidatePreferenceWeights
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.models.match import Match

logger = logging.getLogger(__name__)

# Signal strength per status
STATUS_STRENGTH: dict[str, float] = {
    "saved": 1.0,
    "applied": 2.0,
    "interviewing": 3.0,
    "offer": 4.0,
    "rejected": -0.5,
}

POSITIVE_STATUSES = {"saved", "applied", "interviewing", "offer"}
NEGATIVE_STATUSES = {"rejected"}

# Weight bounds
MIN_WEIGHT = 0.7
MAX_WEIGHT = 1.3

# Cold start: need this many events before adjusting weights
MIN_EVENTS_FOR_ADJUSTMENT = 3
# Full confidence at this many events
FULL_CONFIDENCE_EVENTS = 15


def _tokenize_title(title: str) -> list[str]:
    """Extract meaningful tokens from a job title."""
    tokens = re.findall(r"[a-zA-Z0-9+.#]+", title.lower())
    stop = {"senior", "junior", "lead", "staff", "principal", "the", "and", "for", "at"}
    return [t for t in tokens if len(t) >= 2 and t not in stop]


def extract_preference_signals(
    match: Match,
    job: Job,
    parsed_detail: JobParsedDetail | None,
    status: str,
) -> dict:
    """Extract preference signals from a match status change.

    Returns a dict of signal categories with their values.
    """
    strength = STATUS_STRENGTH.get(status, 0.0)
    if strength == 0.0:
        return {}

    signals: dict = {
        "strength": strength,
        "status": status,
    }

    # Skills from parsed detail or job description
    skills: list[str] = []
    if parsed_detail:
        if parsed_detail.required_skills and isinstance(
            parsed_detail.required_skills, list
        ):
            skills.extend(parsed_detail.required_skills)
        if parsed_detail.preferred_skills and isinstance(
            parsed_detail.preferred_skills, list
        ):
            skills.extend(parsed_detail.preferred_skills)
    if skills:
        signals["skills"] = [s.lower() for s in skills[:20]]

    # Title tokens
    if job.title:
        signals["title_tokens"] = _tokenize_title(job.title)

    # Salary range
    if job.salary_min is not None or job.salary_max is not None:
        signals["salary_min"] = job.salary_min
        signals["salary_max"] = job.salary_max

    # Remote preference
    signals["is_remote"] = bool(job.remote_flag)

    # Job source
    if job.source:
        signals["source"] = job.source

    return signals


def merge_signals(prefs: CandidatePreferenceWeights, signals: dict, status: str) -> None:
    """Merge new signal data into the accumulated learned_signals JSONB."""
    if not signals:
        return

    learned = dict(prefs.learned_signals or {})
    strength = signals.get("strength", 1.0)

    # Accumulate skill preferences
    if "skills" in signals:
        skill_counts = learned.get("skill_counts", {})
        for skill in signals["skills"]:
            skill_counts[skill] = skill_counts.get(skill, 0.0) + strength
        learned["skill_counts"] = skill_counts

    # Accumulate title token preferences
    if "title_tokens" in signals:
        title_counts = learned.get("title_counts", {})
        for token in signals["title_tokens"]:
            title_counts[token] = title_counts.get(token, 0.0) + strength
        learned["title_counts"] = title_counts

    # Accumulate salary signals
    if "salary_min" in signals or "salary_max" in signals:
        salary_signals = learned.get("salary_signals", [])
        salary_signals.append(
            {
                "min": signals.get("salary_min"),
                "max": signals.get("salary_max"),
                "strength": strength,
            }
        )
        # Keep last 20 salary signals
        learned["salary_signals"] = salary_signals[-20:]

    # Accumulate remote preference
    if "is_remote" in signals:
        remote_counts = learned.get("remote_counts", {"remote": 0.0, "onsite": 0.0})
        if signals["is_remote"]:
            remote_counts["remote"] = remote_counts.get("remote", 0.0) + strength
        else:
            remote_counts["onsite"] = remote_counts.get("onsite", 0.0) + strength
        learned["remote_counts"] = remote_counts

    # Update event counters
    if status in POSITIVE_STATUSES:
        prefs.positive_events = (prefs.positive_events or 0) + 1
    elif status in NEGATIVE_STATUSES:
        prefs.negative_events = (prefs.negative_events or 0) + 1

    prefs.learned_signals = learned


def recalculate_weights(prefs: CandidatePreferenceWeights) -> None:
    """Recalculate weight multipliers from accumulated signals.

    Requires MIN_EVENTS_FOR_ADJUSTMENT total events before adjusting.
    Confidence ramps linearly from 0 to 1 over events MIN_EVENTS..FULL_CONFIDENCE.
    All weights clamped to [MIN_WEIGHT, MAX_WEIGHT].
    """
    total_events = (prefs.positive_events or 0) + (prefs.negative_events or 0)
    if total_events < MIN_EVENTS_FOR_ADJUSTMENT:
        return

    # Confidence ramp: 0 at MIN_EVENTS, 1 at FULL_CONFIDENCE_EVENTS
    confidence = min(
        1.0,
        (total_events - MIN_EVENTS_FOR_ADJUSTMENT)
        / max(1, FULL_CONFIDENCE_EVENTS - MIN_EVENTS_FOR_ADJUSTMENT),
    )

    learned = prefs.learned_signals or {}

    # Skill weight: if many skills are consistently preferred, boost skill scoring
    skill_counts = learned.get("skill_counts", {})
    if skill_counts:
        total_skill_signal = sum(skill_counts.values())
        avg_skill_signal = total_skill_signal / max(1, len(skill_counts))
        # High average signal → user values skill match
        skill_boost = min(0.3, avg_skill_signal / (total_events * 2))
        prefs.skill_weight = _clamp(1.0 + skill_boost * confidence)
    else:
        prefs.skill_weight = 1.0

    # Title weight: strong title preference signals boost title scoring
    title_counts = learned.get("title_counts", {})
    if title_counts:
        total_title_signal = sum(title_counts.values())
        # If user consistently interacts with jobs of certain titles
        title_concentration = max(title_counts.values()) / max(1.0, total_title_signal)
        title_boost = min(0.3, title_concentration * 0.3)
        prefs.title_weight = _clamp(1.0 + title_boost * confidence)
    else:
        prefs.title_weight = 1.0

    # Location weight: remote preference signal
    remote_counts = learned.get("remote_counts", {})
    remote_signal = remote_counts.get("remote", 0.0)
    onsite_signal = remote_counts.get("onsite", 0.0)
    total_loc = remote_signal + onsite_signal
    if total_loc > 0:
        # Strong preference either way → location matters more
        dominance = abs(remote_signal - onsite_signal) / total_loc
        loc_boost = min(0.3, dominance * 0.3)
        prefs.location_weight = _clamp(1.0 + loc_boost * confidence)
    else:
        prefs.location_weight = 1.0

    # Salary weight: if user consistently interacts with jobs that have salary data
    salary_signals = learned.get("salary_signals", [])
    if salary_signals:
        has_salary = sum(
            1 for s in salary_signals if s.get("min") is not None or s.get("max") is not None
        )
        salary_data_ratio = has_salary / max(1, len(salary_signals))
        salary_boost = min(0.3, salary_data_ratio * 0.2)
        prefs.salary_weight = _clamp(1.0 + salary_boost * confidence)
    else:
        prefs.salary_weight = 1.0

    # Years weight: stays at 1.0 — insufficient signal from status changes
    prefs.years_weight = 1.0

    prefs.last_recalculated_at = datetime.now(UTC)


def _clamp(value: float) -> float:
    """Clamp a weight to [MIN_WEIGHT, MAX_WEIGHT]."""
    return max(MIN_WEIGHT, min(MAX_WEIGHT, value))


def update_preference_weights_job(
    user_id: int, match_id: int, new_status: str
) -> None:
    """RQ worker entry point: update preference weights after a status change."""
    from app.db.session import get_session_factory
    from app.services.billing import check_feature_access, get_plan_tier

    session = None
    try:
        session = get_session_factory()()
        # Load candidate and check tier
        candidate = session.execute(
            select(Candidate).where(Candidate.user_id == user_id)
        ).scalar_one_or_none()

        tier = get_plan_tier(candidate)
        if not check_feature_access(tier, "preference_learning"):
            return

        # Load match + job
        match = session.execute(
            select(Match).where(Match.id == match_id, Match.user_id == user_id)
        ).scalar_one_or_none()
        if match is None:
            logger.warning("Match %d not found for user %d", match_id, user_id)
            return

        job = session.get(Job, match.job_id)
        if job is None:
            logger.warning("Job %d not found for match %d", match.job_id, match_id)
            return

        # Load parsed detail (optional)
        parsed_detail = session.execute(
            select(JobParsedDetail).where(JobParsedDetail.job_id == job.id)
        ).scalar_one_or_none()

        # Extract signals
        signals = extract_preference_signals(match, job, parsed_detail, new_status)
        if not signals:
            return

        # Get or create preference weights row
        prefs = session.execute(
            select(CandidatePreferenceWeights).where(
                CandidatePreferenceWeights.user_id == user_id
            )
        ).scalar_one_or_none()

        if prefs is None:
            prefs = CandidatePreferenceWeights(user_id=user_id)
            session.add(prefs)
            session.flush()

        # Merge signals and recalculate
        merge_signals(prefs, signals, new_status)
        recalculate_weights(prefs)

        session.commit()
        logger.info(
            "Updated preference weights for user %d: skill=%.2f title=%.2f "
            "loc=%.2f salary=%.2f years=%.2f (events: +%d/-%d)",
            user_id,
            prefs.skill_weight,
            prefs.title_weight,
            prefs.location_weight,
            prefs.salary_weight,
            prefs.years_weight,
            prefs.positive_events,
            prefs.negative_events,
        )
    except Exception:
        if session:
            session.rollback()
        logger.exception(
            "Failed to update preference weights for user %d, match %d",
            user_id,
            match_id,
        )
        raise
    finally:
        if session:
            session.close()


def rebuild_preferences_from_history(session: Session, user_id: int) -> None:
    """Rebuild preference weights from all historical match statuses.

    Useful for backfill or repair.
    """
    from app.services.billing import check_feature_access, get_plan_tier

    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()

    tier = get_plan_tier(candidate)
    if not check_feature_access(tier, "preference_learning"):
        return

    # Get or create preference weights row
    prefs = session.execute(
        select(CandidatePreferenceWeights).where(
            CandidatePreferenceWeights.user_id == user_id
        )
    ).scalar_one_or_none()

    if prefs is None:
        prefs = CandidatePreferenceWeights(user_id=user_id)
        session.add(prefs)
        session.flush()

    # Reset accumulated data
    prefs.learned_signals = {}
    prefs.positive_events = 0
    prefs.negative_events = 0
    prefs.skill_weight = 1.0
    prefs.title_weight = 1.0
    prefs.location_weight = 1.0
    prefs.salary_weight = 1.0
    prefs.years_weight = 1.0

    # Load all matches with a status
    matches = (
        session.execute(
            select(Match).where(
                Match.user_id == user_id,
                Match.application_status.is_not(None),
            )
        )
        .scalars()
        .all()
    )

    for match in matches:
        job = session.get(Job, match.job_id)
        if job is None:
            continue
        parsed_detail = session.execute(
            select(JobParsedDetail).where(JobParsedDetail.job_id == job.id)
        ).scalar_one_or_none()

        signals = extract_preference_signals(
            match, job, parsed_detail, match.application_status
        )
        if signals:
            merge_signals(prefs, signals, match.application_status)

    recalculate_weights(prefs)
    session.flush()
