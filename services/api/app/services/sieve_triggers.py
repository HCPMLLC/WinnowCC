"""Proactive Sieve trigger computation.

Evaluates user state and generates contextual nudges for the Sieve widget.
Each trigger has a numeric priority (1 = highest), action metadata, and
a unique ID for dismissal tracking.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.career_intelligence import CareerTrajectory
from app.models.match import Match
from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.schemas.sieve import SieveTrigger

logger = logging.getLogger(__name__)

# ── Profile completeness fields (11 checkable items) ─────────────────────────
_CANDIDATE_FIELDS = [
    "first_name",
    "last_name",
    "phone",
    "location_city",
    "years_experience",
    "desired_salary_min",
    "desired_salary_max",
    "remote_preference",
]
_LIST_FIELDS = ["desired_job_types", "desired_locations"]
_TOTAL_ITEMS = len(_CANDIDATE_FIELDS) + len(_LIST_FIELDS) + 1  # +1 for CandidateProfile


def _profile_pct(user: User, session: Session) -> int:
    """Compute profile completeness percentage (0-100)."""
    candidate = session.query(Candidate).filter(Candidate.user_id == user.id).first()

    filled = 0
    if candidate:
        for field in _CANDIDATE_FIELDS:
            val = getattr(candidate, field, None)
            if val is not None and val != "":
                filled += 1
        for field in _LIST_FIELDS:
            val = getattr(candidate, field, None)
            if val and len(val) > 0:
                filled += 1

    has_profile = (
        session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .first()
        is not None
    )
    if has_profile:
        filled += 1

    return int((filled / _TOTAL_ITEMS) * 100)


# ── Trigger functions ────────────────────────────────────────────────────────


def compute_profile_completeness_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger if profile is incomplete.

    Two tiers: critical (<50%) and moderate (<70%).
    """
    pct = _profile_pct(user, session)

    if pct < 50:
        return SieveTrigger(
            id="profile_incomplete_critical",
            message=(
                f"Your profile is only {pct}% complete. "
                "Filling in more details would significantly improve your matches."
            ),
            priority=1,
            action_label="Complete Profile",
            action_type="navigate",
            action_target="/profile",
        )

    if pct < 70:
        return SieveTrigger(
            id="profile_incomplete_moderate",
            message=(
                f"Your profile is {pct}% complete. "
                "Adding a few more details could unlock better matches."
            ),
            priority=3,
            action_label="Improve Profile",
            action_type="navigate",
            action_target="/profile",
        )

    return None


def compute_new_matches_trigger(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if new matches in last 24 hours. Differentiates batch (3+) vs few."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    count = (
        session.query(sa_func.count(Match.id))
        .filter(Match.user_id == user.id, Match.created_at >= cutoff)
        .scalar()
    )

    if not count or count == 0:
        return None

    if count >= 3:
        return SieveTrigger(
            id="new_matches_batch",
            message=f"{count} new jobs matched your profile since yesterday!",
            priority=2,
            action_label="View Matches",
            action_type="navigate",
            action_target="/matches",
        )

    noun = "match" if count == 1 else "matches"
    return SieveTrigger(
        id="new_matches_few",
        message=f"{count} new {noun} found since yesterday.",
        priority=4,
        action_label="View Matches",
        action_type="navigate",
        action_target="/matches",
    )


def compute_stale_application_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger if there are saved matches older than 5 days."""
    cutoff = datetime.now(UTC) - timedelta(days=5)

    count = (
        session.query(sa_func.count(Match.id))
        .filter(
            Match.user_id == user.id,
            Match.application_status == "saved",
            Match.created_at < cutoff,
        )
        .scalar()
    )

    if not count or count == 0:
        return None

    noun = "job" if count == 1 else "jobs"
    return SieveTrigger(
        id="stale_saved_jobs",
        message=(
            f"You saved {count} {noun} but haven't applied yet. Need help deciding?"
        ),
        priority=3,
        action_label="Review Saved Jobs",
        action_type="chat",
        action_target="Which of my saved jobs should I apply to?",
    )


def compute_high_match_unreviewed_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger if there are high-scoring matches (80%+) with no status."""
    count = (
        session.query(sa_func.count(Match.id))
        .filter(
            Match.user_id == user.id,
            Match.match_score >= 80,
            Match.application_status.is_(None),
        )
        .scalar()
    )

    if not count or count == 0:
        return None

    noun = "match" if count == 1 else "matches"
    return SieveTrigger(
        id="high_match_unreviewed",
        message=(f"You have {count} strong {noun} (80%+) you haven't looked at yet!"),
        priority=2,
        action_label="See Top Matches",
        action_type="navigate",
        action_target="/matches",
    )


def compute_no_tailored_resumes_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger if user has matches but has never generated a tailored resume."""
    tailored_count = (
        session.query(sa_func.count(TailoredResume.id))
        .filter(TailoredResume.user_id == user.id)
        .scalar()
        or 0
    )

    total_matches = (
        session.query(sa_func.count(Match.id)).filter(Match.user_id == user.id).scalar()
        or 0
    )

    if tailored_count > 0 or total_matches == 0:
        return None

    return SieveTrigger(
        id="no_tailored_resumes",
        message=(
            "You haven't created any tailored resumes yet. "
            "A job-specific resume can 3x your callback rate."
        ),
        priority=4,
        action_label="Learn More",
        action_type="chat",
        action_target="How does tailored resume generation work?",
    )


def compute_usage_limit_trigger(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if free-plan user has hit their tailored resume limit."""
    try:
        from app.services.billing import (
            get_or_create_usage,
            get_plan_tier,
            get_tier_limit,
        )

        candidate = (
            session.query(Candidate).filter(Candidate.user_id == user.id).first()
        )
        tier = get_plan_tier(candidate)
        if tier != "free":
            return None

        usage = get_or_create_usage(session, user.id)
        limit = int(get_tier_limit(tier, "tailor_requests"))
        if usage.tailor_requests < limit:
            return None

        return SieveTrigger(
            id="usage_limit_reached",
            message=(
                "You've used all your free tailored resumes this month. "
                "Upgrade to Starter or Pro for more."
            ),
            priority=2,
            action_label="View Plans",
            action_type="navigate",
            action_target="/billing",
        )
    except Exception as exc:
        logger.warning("Trigger eval failed (usage_limit): %s", exc)
        return None


def compute_interview_coaching_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger if user has interviews in progress but no offers."""
    interviewing = (
        session.query(sa_func.count(Match.id))
        .filter(
            Match.user_id == user.id,
            Match.application_status == "interviewing",
        )
        .scalar()
        or 0
    )

    if interviewing == 0:
        return None

    offers = (
        session.query(sa_func.count(Match.id))
        .filter(
            Match.user_id == user.id,
            Match.application_status == "offer",
        )
        .scalar()
        or 0
    )

    if offers > 0:
        return None

    noun = "interview" if interviewing == 1 else "interviews"
    return SieveTrigger(
        id="interview_coaching",
        message=(f"You have {interviewing} {noun} in progress. Want some prep tips?"),
        priority=5,
        action_label="Interview Tips",
        action_type="chat",
        action_target="Give me interview preparation tips",
    )


# ── Location preference patterns that hurt matching ──────────────────────────

# Two-letter US state abbreviations
_US_STATE_ABBREVS = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
    "dc",
}

# Common city abbreviations that won't match full names
_CITY_ABBREVS = {
    "sf": "San Francisco",
    "nyc": "New York",
    "la": "Los Angeles",
    "dc": "Washington",
    "philly": "Philadelphia",
    "atl": "Atlanta",
    "chi": "Chicago",
    "dfw": "Dallas",
    "dmv": "Washington",
}

# Vague/wildcard values that don't match anything
_VAGUE_VALUES = {"any", "anywhere", "all", "nationwide", "n/a", "none", "usa", "us"}

_FULL_STATE_NAMES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
}


def _check_location_issues(locations: list[str]) -> list[str]:
    """Return a list of human-readable issues found in location values."""
    issues: list[str] = []
    for loc in locations:
        val = loc.strip().lower()
        if not val:
            continue
        if val in _VAGUE_VALUES:
            issues.append(
                f'"{loc}" doesn\'t match any job location. '
                "If you're open to any location, remove all location "
                "preferences and Winnow will match you with jobs everywhere."
            )
        elif val in _CITY_ABBREVS:
            issues.append(
                f'"{loc}" is an abbreviation \u2014 use the full city name '
                f'"{_CITY_ABBREVS[val]}" instead so it matches job listings.'
            )
        elif val in _US_STATE_ABBREVS and "," not in loc:
            issues.append(
                f'"{loc}" is a state abbreviation and will match too broadly '
                "(every city in that state). Use a city name like "
                '"Austin" or "Austin, TX" for precise matching.'
            )
        elif val in _FULL_STATE_NAMES:
            issues.append(
                f'"{loc}" is a state name. Job listings use city names '
                'or "City, ST" format \u2014 use a specific city like '
                f'"Austin" instead of "{loc}".'
            )
    return issues


def compute_no_matches_trigger(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if user has a profile but zero matches above threshold.

    Pulls the user's top skills from their profile and suggests broadening
    their search or highlighting transferable skills.
    """
    has_profile = (
        session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .first()
    )
    if not has_profile:
        return None

    match_count = (
        session.query(sa_func.count(Match.id)).filter(Match.user_id == user.id).scalar()
        or 0
    )
    if match_count > 0:
        return None

    # Find skill-matched jobs to determine if we can recommend specific roles
    try:
        from app.services.sieve_chat import find_skill_matched_jobs

        recs = find_skill_matched_jobs(session, user.id, limit=3)
    except Exception:
        recs = []

    if recs:
        # Lead with concrete recommendations — don't ask the user to lead
        titles = [r["title"] for r in recs[:3]]
        if len(titles) == 1:
            roles_text = f'"{titles[0]}"'
        elif len(titles) == 2:
            roles_text = f'"{titles[0]}" and "{titles[1]}"'
        else:
            roles_text = f'"{titles[0]}", "{titles[1]}", and "{titles[2]}"'

        message = (
            f"None of your target roles matched, but I found jobs where "
            f"your skills are a strong fit — like {roles_text}. "
            f"Want me to walk you through which ones give you the best "
            f"shot at an interview?"
        )
        action_target = (
            "Show me the jobs where my skills match "
            "and tell me which ones I should go after."
        )
    else:
        message = (
            "I ran your profile against all active jobs and none scored "
            "above the match threshold. I've identified some roles where "
            "your experience could transfer — let me show you."
        )
        action_target = (
            "What roles should I target to get "
            "interviews based on my skills "
            "and experience?"
        )

    return SieveTrigger(
        id="no_matches_after_profile",
        message=message,
        priority=1,
        action_label="Show Me",
        action_type="chat",
        action_target=action_target,
    )


def compute_location_format_trigger(
    user: User,
    session: Session,
) -> SieveTrigger | None:
    """Trigger if location preferences contain values that hurt matching."""
    candidate = session.query(Candidate).filter(Candidate.user_id == user.id).first()

    locations: list[str] = []

    # Check candidate.desired_locations
    if candidate and candidate.desired_locations:
        locations.extend(candidate.desired_locations)

    # Also check profile preferences
    profile = (
        session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .first()
    )
    if profile and profile.profile_json:
        prefs = profile.profile_json.get("preferences", {})
        profile_locs = prefs.get("locations", [])
        if profile_locs:
            locations.extend(loc for loc in profile_locs if isinstance(loc, str))

    if not locations:
        return None

    issues = _check_location_issues(locations)
    if not issues:
        return None

    # Pick the first issue for the notification message
    return SieveTrigger(
        id="location_format_issue",
        message=issues[0],
        priority=2,
        action_label="Fix Locations",
        action_type="chat",
        action_target="How should I format my location preferences?",
    )


def compute_career_trajectory_trigger(
    user: User, session: Session
) -> SieveTrigger | None:
    """Trigger for Pro users with cached career trajectory data.

    Nudges the user to explore career coaching based on their
    AI-predicted trajectory (recommended skills or growth areas).
    Does NOT call Claude — only reads cached predictions from DB.
    """
    try:
        from app.services.billing import get_plan_tier

        candidate = (
            session.query(Candidate).filter(Candidate.user_id == user.id).first()
        )
        tier = get_plan_tier(candidate)
        if tier != "pro":
            return None
    except Exception as exc:
        logger.warning("Trigger eval failed (career_trajectory tier check): %s", exc)
        return None

    # Get latest profile to join with trajectory
    profile = (
        session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user.id)
        .order_by(CandidateProfile.version.desc())
        .first()
    )
    if not profile:
        return None

    # Query latest non-expired trajectory for this profile
    now = datetime.now(UTC)
    trajectory = (
        session.query(CareerTrajectory)
        .filter(
            CareerTrajectory.candidate_profile_id == profile.id,
            (CareerTrajectory.expires_at.is_(None))
            | (CareerTrajectory.expires_at > now),
        )
        .order_by(CareerTrajectory.created_at.desc())
        .first()
    )
    if not trajectory or not trajectory.trajectory_json:
        return None

    tj = trajectory.trajectory_json

    # Build message from recommended_skills or key_growth_areas
    recommended_skills = tj.get("recommended_skills") or []
    key_growth_areas = tj.get("key_growth_areas") or []

    if recommended_skills:
        top = recommended_skills[:3]
        skills_text = ", ".join(top)
        message = (
            f"Based on your career trajectory, focusing on "
            f"{skills_text} could accelerate your growth. "
            f"Want coaching on how to build these skills?"
        )
    elif key_growth_areas:
        top = key_growth_areas[:3]
        areas_text = ", ".join(top)
        message = (
            f"Your trajectory analysis identified growth opportunities in "
            f"{areas_text}. Let's talk about your next move."
        )
    else:
        return None

    return SieveTrigger(
        id="career_trajectory_coaching",
        message=message,
        priority=4,
        action_label="Career Coaching",
        action_type="chat",
        action_target=(
            "Based on my career trajectory, what skills should I focus on and how?"
        ),
    )


# ── Employer trigger functions ──────────────────────────────────────────────


def _employer_no_active_jobs(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if employer has 0 active jobs."""
    from app.models.employer import EmployerJob, EmployerProfile

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    active = (
        session.query(sa_func.count(EmployerJob.id))
        .filter(
            EmployerJob.employer_id == profile.id,
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
        )
        .scalar()
        or 0
    )
    if active > 0:
        return None

    return SieveTrigger(
        id="employer_no_active_jobs",
        message=(
            "You don't have any active job postings "
            "yet. Let's get your first role live!"
        ),
        priority=1,
        action_label="Create Job",
        action_type="navigate",
        action_target="/employer/jobs/new",
    )


def _employer_low_application(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if an active job has 0 applications after 5+ days."""
    from app.models.employer import EmployerJob, EmployerProfile

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    cutoff = datetime.now(UTC) - timedelta(days=5)
    stale_job = (
        session.query(EmployerJob)
        .filter(
            EmployerJob.employer_id == profile.id,
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
            EmployerJob.created_at < cutoff,
            sa_func.coalesce(EmployerJob.application_count, 0) == 0,
        )
        .order_by(EmployerJob.created_at.asc())
        .first()
    )
    if not stale_job:
        return None

    return SieveTrigger(
        id="employer_low_application",
        message=(
            f'Your "{stale_job.title}" posting has been active for '
            f"{(datetime.now(UTC) - stale_job.created_at).days} days with "
            f"no applications. Let's figure out why."
        ),
        priority=2,
        action_label="Get Help",
        action_type="chat",
        action_target=f"Why isn't my '{stale_job.title}' getting applications?",
    )


def _employer_stale_intros(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if 3+ introduction requests are pending for 5+ days."""
    from app.models.employer import EmployerProfile
    from app.models.employer_introduction import EmployerIntroductionRequest

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    cutoff = datetime.now(UTC) - timedelta(days=5)
    stale_count = (
        session.query(sa_func.count(EmployerIntroductionRequest.id))
        .filter(
            EmployerIntroductionRequest.employer_profile_id == profile.id,
            EmployerIntroductionRequest.status == "pending",
            EmployerIntroductionRequest.created_at < cutoff,
        )
        .scalar()
        or 0
    )
    if stale_count < 3:
        return None

    return SieveTrigger(
        id="employer_stale_intros",
        message=(
            f"You have {stale_count} introduction requests pending for over 5 days. "
            f"Check in on them or consider reaching out to new candidates."
        ),
        priority=2,
        action_label="View Intros",
        action_type="navigate",
        action_target="/employer/introductions",
    )


def _employer_no_boards(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if employer has active jobs but 0 board connections."""
    from app.models.distribution import BoardConnection
    from app.models.employer import EmployerJob, EmployerProfile

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    active_jobs = (
        session.query(sa_func.count(EmployerJob.id))
        .filter(
            EmployerJob.employer_id == profile.id,
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
        )
        .scalar()
        or 0
    )
    if active_jobs == 0:
        return None

    boards = (
        session.query(sa_func.count(BoardConnection.id))
        .filter(
            BoardConnection.employer_id == profile.id,
            BoardConnection.is_active.is_(True),
        )
        .scalar()
        or 0
    )
    if boards > 0:
        return None

    return SieveTrigger(
        id="employer_no_boards",
        message=(
            "You have active jobs but no job boards connected. "
            "Distributing to boards can dramatically increase your reach."
        ),
        priority=3,
        action_label="Connect Boards",
        action_type="navigate",
        action_target="/employer/connections",
    )


def _employer_salary_missing(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if an active job has no salary range set."""
    from app.models.employer import EmployerJob, EmployerProfile

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    job = (
        session.query(EmployerJob)
        .filter(
            EmployerJob.employer_id == profile.id,
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
            EmployerJob.salary_min.is_(None),
            EmployerJob.salary_max.is_(None),
        )
        .first()
    )
    if not job:
        return None

    return SieveTrigger(
        id="employer_salary_missing",
        message=(
            f'Your "{job.title}" posting has no salary range. '
            f"Jobs with salary info get 30-50% more applications."
        ),
        priority=3,
        action_label="Add Salary",
        action_type="navigate",
        action_target=f"/employer/jobs/{job.id}/edit",
    )


def _employer_usage_limit(user: User, session: Session) -> SieveTrigger | None:
    """Trigger if employer is at 80%+ of their intro request limit."""
    from app.models.employer import EmployerProfile
    from app.services.billing import EMPLOYER_PLAN_LIMITS, get_employer_tier

    profile = (
        session.query(EmployerProfile)
        .filter(EmployerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        return None

    tier = get_employer_tier(profile)
    limits = EMPLOYER_PLAN_LIMITS.get(tier, EMPLOYER_PLAN_LIMITS["free"])
    intro_limit = limits.get("intro_requests_per_month", 0)
    if isinstance(intro_limit, int) and intro_limit >= 999:
        return None

    used = profile.intro_requests_used or 0
    if intro_limit == 0 or used < int(intro_limit * 0.8):
        return None

    return SieveTrigger(
        id="employer_usage_limit",
        message=(
            f"You've used {used}/{intro_limit} introduction requests this month. "
            f"Upgrade for more."
        ),
        priority=4,
        action_label="View Plans",
        action_type="navigate",
        action_target="/employer/pricing",
    )


_EMPLOYER_TRIGGER_FNS = [
    _employer_no_active_jobs,
    _employer_low_application,
    _employer_stale_intros,
    _employer_no_boards,
    _employer_salary_missing,
    _employer_usage_limit,
]


def compute_employer_triggers(
    user: User,
    session: Session,
    dismissed_ids: list[str] | None = None,
) -> list[SieveTrigger]:
    """Run employer trigger checks and return top 3 sorted by priority."""
    dismissed = set(dismissed_ids or [])
    results: list[SieveTrigger] = []

    for fn in _EMPLOYER_TRIGGER_FNS:
        try:
            trigger = fn(user, session)
            if trigger is not None and trigger.id not in dismissed:
                results.append(trigger)
        except Exception as exc:
            logger.warning("Employer trigger eval failed (%s): %s", fn.__name__, exc)

    results.sort(key=lambda t: t.priority)
    return results[:3]


# ── Main evaluation function ────────────────────────────────────────────────

_ALL_TRIGGER_FNS = [
    compute_profile_completeness_trigger,
    compute_new_matches_trigger,
    compute_no_matches_trigger,
    compute_stale_application_trigger,
    compute_high_match_unreviewed_trigger,
    compute_no_tailored_resumes_trigger,
    compute_usage_limit_trigger,
    compute_interview_coaching_trigger,
    compute_career_trajectory_trigger,
    compute_location_format_trigger,
]


def compute_all_triggers(
    user: User,
    session: Session,
    dismissed_ids: list[str] | None = None,
) -> list[SieveTrigger]:
    """Run all trigger checks and return top 3 sorted by priority (1 = highest).

    Filters out any triggers whose ID is in ``dismissed_ids``.
    """
    dismissed = set(dismissed_ids or [])
    results: list[SieveTrigger] = []

    for fn in _ALL_TRIGGER_FNS:
        try:
            trigger = fn(user, session)
            if trigger is not None and trigger.id not in dismissed:
                results.append(trigger)
        except Exception as exc:
            logger.warning("Trigger eval failed (%s): %s", fn.__name__, exc)

    results.sort(key=lambda t: t.priority)
    return results[:3]
