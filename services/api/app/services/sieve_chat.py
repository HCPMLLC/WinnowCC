"""Sieve chatbot service — context loading, system prompt, LLM calls,
rate limiting, fallback responses, and suggested actions."""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.user import User

from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting (in-memory, per-process)
# ---------------------------------------------------------------------------
_rate_limits: dict[int, list[float]] = defaultdict(list)
MAX_MESSAGES_PER_MINUTE = 10


def _check_rate_limit(user_id: int) -> bool:
    """Return True if the user is within rate limits."""
    now = time.time()
    _rate_limits[user_id] = [t for t in _rate_limits[user_id] if now - t < 60]
    if len(_rate_limits[user_id]) >= MAX_MESSAGES_PER_MINUTE:
        return False
    _rate_limits[user_id].append(now)
    return True


# ---------------------------------------------------------------------------
# Skill-based job recommendations (title-agnostic)
# ---------------------------------------------------------------------------

_JOB_FRESHNESS_DAYS = 15


def find_skill_matched_jobs(
    session: Session, user_id: int, limit: int = 8
) -> list[dict]:
    """Find jobs that best match the user's skills, ignoring title preferences.

    This is the fallback when standard matching yields 0 results.
    It bypasses title matching and threshold filtering to surface jobs
    where the candidate's skills genuinely overlap with job requirements.
    """
    from app.services.matching import _extract_all_skills, _extract_skills_from_text

    # Load latest profile
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not profile or not profile.profile_json:
        return []

    candidate_skills = {s.lower() for s in _extract_all_skills(profile.profile_json)}
    if not candidate_skills:
        return []

    # Load candidate for location/remote preferences
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()

    prefs = profile.profile_json.get("preferences", {})
    location_prefs = [loc.lower() for loc in prefs.get("locations", [])]
    if not location_prefs and candidate and candidate.desired_locations:
        location_prefs = [loc.lower() for loc in candidate.desired_locations]

    remote_pref = None
    if candidate and candidate.remote_preference:
        remote_pref = candidate.remote_preference.lower()
    elif prefs.get("remote_ok"):
        remote_pref = "remote"

    # Fetch active, recent jobs
    cutoff = datetime.now(UTC) - timedelta(days=_JOB_FRESHNESS_DAYS)
    jobs = (
        session.execute(
            select(Job).where(
                func.coalesce(Job.posted_at, Job.ingested_at) >= cutoff,
                Job.is_active.is_not(False),
            )
        )
        .scalars()
        .all()
    )

    import re

    # Score each job by: how strong a candidate this person would be
    # Key metric: coverage_ratio = matched_skills / total_job_skills
    # A candidate covering 4/5 job skills is a TOP candidate for that role
    scored: list[tuple[Job, list[str], int, float]] = []
    for job in jobs:
        job_skills = {
            s.lower() for s in _extract_skills_from_text(job.description_text or "")
        }
        if not job_skills:
            continue
        overlap = candidate_skills & job_skills
        if len(overlap) < 2:
            continue  # Need at least 2 matching skills

        # Coverage ratio: what % of the job's skills does this candidate have?
        # Higher = they'd be a stronger candidate relative to the job's needs
        coverage = len(overlap) / len(job_skills)

        # Composite score: prioritize jobs where candidate covers the most
        # requirements (best candidate for the job), with bonuses for
        # absolute overlap count, location fit, and remote fit
        score = coverage * 100  # 0-100 base from coverage ratio

        # Bonus for absolute overlap (rewards deep skill matches)
        score += min(len(overlap) * 2, 20)

        # Location alignment bonus
        if location_prefs and job.location:
            job_loc = job.location.lower()
            if any(lp in job_loc for lp in location_prefs):
                score += 10
        # Remote alignment bonus
        if remote_pref and job.remote_flag:
            score += 5

        scored.append((job, sorted(overlap), int(score), coverage))

    scored.sort(key=lambda x: -x[2])
    top = scored[:limit]

    results = []
    for job, matched_skills, score, coverage in top:
        # Clean up job titles: strip ID prefixes and trailing reference codes
        title = job.title or ""
        title = re.sub(r"^(Job\s+)?\d{4,}\s*", "", title).strip()
        title = re.sub(r"\s+[A-Z]?\d{6,}$", "", title).strip()
        if not title:
            title = job.title or "Untitled"

        results.append({
            "title": title,
            "company": job.company,
            "location": job.location or "Remote",
            "matched_skills": matched_skills[:8],
            "skill_overlap_count": len(matched_skills),
            "coverage_pct": int(coverage * 100),
        })

    return results


# ---------------------------------------------------------------------------
# Context loading
# ---------------------------------------------------------------------------


def load_user_context(user_id: int, session: Session) -> dict:
    """Load the user's current state for Sieve's system prompt.

    Returns a dict with profile summary, match highlights,
    tracking stats, and tailored resume count.
    """
    context: dict = {}

    # ── User ──────────────────────────────────
    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        return context

    # ── Candidate record ──────────────────────
    candidate = session.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()

    name = user.email.split("@")[0]
    if candidate:
        full = " ".join(p for p in [candidate.first_name, candidate.last_name] if p)
        if full:
            name = full

    # ── Profile ───────────────────────────────
    profile = session.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    pj = (profile.profile_json if profile else None) or {}
    skills = pj.get("skills", [])
    experience = pj.get("experience", [])
    prefs = pj.get("preferences", {})

    # Compute completeness score (same algorithm as dashboard)
    from app.services.profile_scoring import compute_profile_completeness

    completeness = compute_profile_completeness(pj).score

    # Target titles from profile preferences or candidate record
    target_titles = prefs.get("target_titles", [])
    if not target_titles and candidate:
        target_titles = candidate.desired_job_types or []

    # Remote preference
    remote_pref = "not specified"
    if candidate and candidate.remote_preference:
        remote_pref = candidate.remote_preference
    elif prefs.get("remote_ok") is True:
        remote_pref = "remote"

    # Location preferences (merge profile + candidate)
    location_prefs: list[str] = prefs.get("locations", [])
    if not location_prefs and candidate and candidate.desired_locations:
        location_prefs = candidate.desired_locations

    # Detect location format issues
    from app.services.sieve_triggers import _check_location_issues

    location_issues = _check_location_issues(location_prefs) if location_prefs else []

    # Has resume
    from app.models.resume_document import ResumeDocument

    has_resume = (
        session.execute(
            select(func.count(ResumeDocument.id)).where(
                ResumeDocument.user_id == user_id
            )
        ).scalar_one()
        > 0
    )

    context["profile"] = {
        "name": name,
        "completeness_score": completeness,
        "skills_count": len(skills),
        "experience_count": len(experience),
        "target_titles": target_titles,
        "remote_preference": remote_pref,
        "location_preferences": location_prefs,
        "location_issues": location_issues,
        "has_resume": has_resume,
    }

    # ── Matches (filtered by winnowing threshold) ──
    from app.services.matching import MIN_MATCH_SCORE

    total_match_count = session.execute(
        select(func.count(Match.id)).where(
            Match.user_id == user_id,
            Match.match_score >= MIN_MATCH_SCORE,
        )
    ).scalar_one()

    # Top 5 qualified matches by score, joined with Job for title/company
    top_rows = session.execute(
        select(Match, Job)
        .join(Job, Match.job_id == Job.id)
        .where(
            Match.user_id == user_id,
            Match.match_score >= MIN_MATCH_SCORE,
        )
        .order_by(Match.match_score.desc())
        .limit(5)
    ).all()

    top_matches = []
    score_sum = 0
    for match, job in top_rows:
        reasons = match.reasons or {}
        top_matches.append(
            {
                "title": job.title,
                "company": job.company,
                "score": match.match_score,
                "matched_skills": (reasons.get("matched_skills") or [])[:3],
                "missing_skills": (reasons.get("missing_skills") or [])[:2],
            }
        )
        score_sum += match.match_score

    avg_score = round(score_sum / len(top_rows)) if top_rows else 0

    context["matches"] = {
        "total_count": total_match_count,
        "top_matches": top_matches,
        "avg_match_score": avg_score,
    }

    # ── Tracking stats ────────────────────────
    status_counts = session.execute(
        select(Match.application_status, func.count(Match.id))
        .where(
            Match.user_id == user_id,
            Match.application_status.is_not(None),
        )
        .group_by(Match.application_status)
    ).all()

    tracking: dict[str, int] = {
        "saved": 0,
        "applied": 0,
        "interviewing": 0,
        "rejected": 0,
        "offer": 0,
    }
    for status, count in status_counts:
        if status in tracking:
            tracking[status] = count

    context["tracking"] = tracking

    # ── Tailored resumes ──────────────────────
    from app.models.tailored_resume import TailoredResume

    tailored_count = session.execute(
        select(func.count(TailoredResume.id)).where(TailoredResume.user_id == user_id)
    ).scalar_one()

    context["tailored_resumes_count"] = tailored_count

    # ── Billing / subscription ─────────────────
    try:
        from app.services.billing import get_or_create_usage, get_plan_tier, get_tier_limit

        tier = get_plan_tier(candidate)
        usage = get_or_create_usage(session, user_id)
        tailor_limit = get_tier_limit(tier, "tailor_requests")
        context["billing"] = {
            "plan": tier,
            "tailored_resumes_used": usage.tailor_requests,
            "tailored_resumes_limit": (
                int(tailor_limit) if tier == "free" else "unlimited"
            ),
        }
    except Exception:
        context["billing"] = {"plan": "free"}

    # ── Career trajectory (Pro users only) ──────
    if context.get("billing", {}).get("plan") == "pro" and profile:
        try:
            from app.models.career_intelligence import CareerTrajectory

            now_utc = datetime.now(UTC)
            trajectory = session.execute(
                select(CareerTrajectory)
                .where(
                    CareerTrajectory.candidate_profile_id == profile.id,
                    (CareerTrajectory.expires_at.is_(None))
                    | (CareerTrajectory.expires_at > now_utc),
                )
                .order_by(CareerTrajectory.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if trajectory and trajectory.trajectory_json:
                tj = trajectory.trajectory_json
                context["career_trajectory"] = {
                    "current_level": tj.get("current_level"),
                    "career_velocity": tj.get("career_velocity"),
                    "trajectory_6mo": tj.get("trajectory_6mo"),
                    "trajectory_12mo": tj.get("trajectory_12mo"),
                    "key_growth_areas": tj.get("key_growth_areas"),
                    "recommended_skills": tj.get("recommended_skills"),
                    "strengths": tj.get("strengths"),
                    "potential_obstacles": tj.get("potential_obstacles"),
                }
        except Exception as exc:
            logger.warning("Failed to load career trajectory for Sieve: %s", exc)

    # ── Skill-matched recommendations (when user has few/no matches) ──
    if total_match_count <= 3:
        try:
            # Find jobs where user's skills match, ignoring title preferences
            skill_recs = find_skill_matched_jobs(session, user_id, limit=8)
            if skill_recs:
                context["skill_matched_jobs"] = skill_recs

            # Also include job inventory summary for broader context
            total_active = session.execute(
                select(func.count(Job.id)).where(Job.is_active.is_(True))
            ).scalar() or 0

            title_rows = session.execute(
                select(Job.title, func.count(Job.id).label("cnt"))
                .where(Job.is_active.is_(True))
                .group_by(Job.title)
                .order_by(func.count(Job.id).desc())
                .limit(20)
            ).all()

            context["job_inventory"] = {
                "total_active_jobs": total_active,
                "top_roles": [
                    {"title": title, "count": count}
                    for title, count in title_rows
                ],
            }
        except Exception as exc:
            logger.warning("Failed to load job recommendations for Sieve: %s", exc)

    return context


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _format_top_matches(top_matches: list) -> str:
    """Format top matches for the system prompt."""
    if not top_matches:
        return "  No matches yet."
    lines = []
    for i, m in enumerate(top_matches, 1):
        matched = ", ".join(m.get("matched_skills", []))
        missing = ", ".join(m.get("missing_skills", []))
        lines.append(
            f"  {i}. {m['title']} at {m['company']}"
            f" \u2014 Score: {m['score']}/100"
            f"\n     Matched: {matched}"
            f"\n     Missing: {missing}"
        )
    return "\n".join(lines)


def build_system_prompt(user_context: dict) -> str:
    """Build the Claude system prompt for Sieve with full user context."""
    profile = user_context.get("profile", {})
    matches = user_context.get("matches", {})
    tracking = user_context.get("tracking", {})
    tailored_count = user_context.get("tailored_resumes_count", 0)
    billing = user_context.get("billing", {})

    targets = ", ".join(profile.get("target_titles", [])) or "not specified"
    loc_prefs = profile.get("location_preferences", [])
    loc_display = ", ".join(loc_prefs) if loc_prefs else "none (matches all locations)"
    loc_issues = profile.get("location_issues", [])
    loc_issues_block = ""
    if loc_issues:
        bullets = "\n".join(f"  - {issue}" for issue in loc_issues)
        loc_issues_block = f"""
LOCATION PREFERENCE ISSUES DETECTED:
{bullets}
IMPORTANT: Proactively warn the user about these issues when they ask \
about matches, locations, or profile improvements. These problems \
silently hurt their match scores."""

    # Career trajectory coaching block (Pro users with trajectory data)
    career_traj = user_context.get("career_trajectory")
    career_traj_block = ""
    if career_traj:
        ct_lines = []
        if career_traj.get("current_level"):
            ct_lines.append(f"- Current level: {career_traj['current_level']}")
        if career_traj.get("career_velocity"):
            ct_lines.append(f"- Career velocity: {career_traj['career_velocity']}")
        t6 = career_traj.get("trajectory_6mo")
        if t6:
            salary_6 = ""
            if t6.get("salary_range_min") and t6.get("salary_range_max"):
                salary_6 = f" (${t6['salary_range_min']:,}–${t6['salary_range_max']:,})"
            ct_lines.append(
                f"- 6-month projection: {t6.get('role', 'N/A')}{salary_6}"
            )
        t12 = career_traj.get("trajectory_12mo")
        if t12:
            salary_12 = ""
            if t12.get("salary_range_min") and t12.get("salary_range_max"):
                lo = t12["salary_range_min"]
                hi = t12["salary_range_max"]
                salary_12 = f" (${lo:,}\u2013${hi:,})"
            ct_lines.append(
                f"- 12-month projection: {t12.get('role', 'N/A')}{salary_12}"
            )
        if career_traj.get("key_growth_areas"):
            ct_lines.append(
                f"- Growth areas: {', '.join(career_traj['key_growth_areas'][:5])}"
            )
        if career_traj.get("recommended_skills"):
            rec_sk = ", ".join(career_traj["recommended_skills"][:5])
            ct_lines.append(f"- Recommended skills: {rec_sk}")
        if career_traj.get("strengths"):
            ct_lines.append(
                f"- Strengths: {', '.join(career_traj['strengths'][:5])}"
            )
        if career_traj.get("potential_obstacles"):
            obs = ", ".join(career_traj["potential_obstacles"][:5])
            ct_lines.append(f"- Potential obstacles: {obs}")
        ct_data = "\n".join(ct_lines)
        career_traj_block = f"""
CAREER TRAJECTORY (AI-predicted, based on profile analysis):
{ct_data}

CAREER COACHING RULES:
1. Reference this real trajectory data when coaching — never fabricate \
projections or salary numbers.
2. Connect recommended skills to the user's current matches — show \
which skills would unlock higher-scoring jobs.
3. Coach based on career velocity: if accelerating, encourage \
ambitious moves; if plateauing, suggest skill investments.
4. Suggest concrete actions: courses, certifications, project types, \
or role changes that align with the trajectory.
5. Ground advice in the user's strengths — build on what's working.
6. Acknowledge potential obstacles honestly and suggest strategies \
to overcome them.
7. Never fabricate trajectory data, salary ranges, or predictions \
beyond what is provided above.
"""

    # Skill-matched job recommendations (only when user has few/no matches)
    skill_recs = user_context.get("skill_matched_jobs", [])
    job_inventory = user_context.get("job_inventory")
    job_recs_block = ""

    if skill_recs:
        recs_lines = []
        for i, rec in enumerate(skill_recs, 1):
            skills_str = ", ".join(rec["matched_skills"][:6])
            coverage = rec.get("coverage_pct", 0)
            recs_lines.append(
                f"  {i}. **{rec['title']}** at {rec['company']} ({rec['location']})"
                f"\n     Your matching skills: {skills_str}"
                f"\n     You cover {coverage}% of this job's requirements"
            )
        recs_text = "\n".join(recs_lines)
        job_recs_block = f"""
SKILL-MATCHED JOB RECOMMENDATIONS (title-agnostic, ranked by candidate strength):
These jobs were found by matching the user's SKILLS against job \
requirements, ignoring job title. They are ranked by COVERAGE RATIO — \
what percentage of the job's required skills this candidate covers. \
Higher coverage = this person would be one of the STRONGEST candidates \
for that role:
{recs_text}

CRITICAL INSTRUCTIONS — DUAL-SIDED VALUE:
Winnow serves BOTH sides: we find the best job for each candidate AND \
the best candidate for each job. Your recommendations should reflect this.

When the user has 0 standard matches:
1. LEAD with specific jobs from the list above where coverage is \
highest. These are roles where the candidate would STAND OUT — not \
just qualify, but be a top contender. Frame it that way: "You cover \
X% of what they're looking for — that puts you near the top of their \
applicant pool."
2. Explain WHY they'd be a strong candidate: name their matching \
skills, reference specific work experience that transfers, and \
highlight what makes them competitive for that role.
3. Coach them to OPTIMIZE their profile truthfully for highest IPS \
on these jobs: suggest adding relevant skills they may have omitted, \
highlighting transferable experience, and evidencing accomplishments \
with metrics. Never suggest fabrication — only surface what's real.
4. Help them understand the FULL scoring picture: profile completeness, \
skill overlap, location fit, experience alignment, and resume \
optimization ALL affect whether they clear the match threshold.
5. Suggest adding these roles to their target titles so Winnow's \
matching engine picks them up automatically in future refreshes.
6. Always end with a concrete next step toward an interview — never \
leave the user wondering what to do.
"""

    if job_inventory and not skill_recs:
        roles_lines = "\n".join(
            f"  - {r['title']} ({r['count']} posting{'s' if r['count'] != 1 else ''})"
            for r in job_inventory.get("top_roles", [])
        )
        job_recs_block = f"""
AVAILABLE JOB INVENTORY ({job_inventory.get("total_active_jobs", 0)} active postings):
The most common roles currently in Winnow's job pool:
{roles_lines}

When this user has 0 matches, suggest SPECIFIC roles from the \
inventory that align with their transferable skills. Be concrete: \
name 3-5 roles and explain WHY their skills transfer."""

    return f"""\
You are Sieve (she/her), the personal AI concierge for Winnow \u2014 a job matching platform.

IDENTITY:
Your name has a dual meaning. A sieve is a tool for sifting and filtering \
\u2014 separating the best from the noise. But your name is also a homonym for \
Siv, a Scandinavian feminine name derived from "sif," meaning "bride" or \
"connection by marriage," associated with the Norse goddess Sif, wife of \
Thor. Sif's golden hair represented fields of golden wheat \u2014 and when cut, \
became the catalyst for the creation of the treasures of the Gods, including \
Thor's hammer Mj\u00f6lnir. You are the perfect companion for Winnow, the \
platform that separates the wheat from the chaff. If a user asks about your \
name, share this story naturally and with warmth.

PERSONALITY:
- You are female and use she/her pronouns when referring to yourself.
- Warm, professional, and encouraging. Think: a supportive career \
coach who also has access to real data.
- Address the user by first name when you know it.
- Keep responses concise \u2014 2\u20134 sentences for simple questions, \
up to a short paragraph for complex ones.
- Use a confident but not pushy tone. You are here to help, not sell.
- When you don't know something specific, say so honestly. \
Never fabricate data.

CAPABILITIES \u2014 What you CAN help with:
- Explaining match scores and why jobs matched (or didn't)
- Suggesting which matched jobs to apply to first (prioritization)
- Advising on profile improvements to increase match scores
- Guiding users through tailored resume AND cover letter generation
- Explaining the interview probability score and how to improve it
- Helping track application progress and next steps
- General job search tips, resume advice, interview preparation
- Advising on AI Search best practices (use descriptive queries, not single keywords)
- Explaining document downloads (tailored resume + cover letter as DOCX)
- Guiding data export (Starter+ plans) and account management
- Advising on professional references to strengthen profiles
- Explaining trust/verification status and how to request review

LIMITATIONS \u2014 What you CANNOT do:
- You cannot apply to jobs on the user's behalf
- You cannot modify the user's profile directly (suggest they edit it)
- You cannot guarantee interview outcomes
- You cannot access external websites or job boards
- You do not have access to other users' data

CURRENT USER STATE:
- Name: {profile.get("name", "there")}
- Profile completeness: {profile.get("completeness_score", "unknown")}%
- Skills on profile: {profile.get("skills_count", 0)}
- Work experiences listed: {profile.get("experience_count", 0)}
- Target roles: {targets}
- Remote preference: {profile.get("remote_preference", "not specified")}
- Location preferences: {loc_display}
- Has uploaded resume: \
{"Yes" if profile.get("has_resume") else "No"}
- Total job matches: {matches.get("total_count", 0)}
- Average match score: {matches.get("avg_match_score", 0)}/100
- Tailored resumes generated: {tailored_count}

APPLICATION PIPELINE:
- Saved: {tracking.get("saved", 0)}
- Applied: {tracking.get("applied", 0)}
- Interviewing: {tracking.get("interviewing", 0)}
- Rejected: {tracking.get("rejected", 0)}
- Offers: {tracking.get("offer", 0)}

SUBSCRIPTION:
- Plan: {billing.get("plan", "free")}
- Tailored resumes used: \
{billing.get("tailored_resumes_used", 0)}/\
{billing.get("tailored_resumes_limit", "?")}
{career_traj_block}
TOP MATCHES (for reference when user asks about matches):
{_format_top_matches(matches.get("top_matches", []))}
{job_recs_block}
LOCATION PREFERENCES \u2014 How Winnow Matches Locations:
Winnow uses substring matching: the user's preference must appear \
inside the job's location string. Both sides are lowercased first.
- BEST FORMAT: City name only (e.g., "Austin", "San Francisco"). \
This is the most flexible since job boards vary in how they format states.
- ALSO WORKS: "City, ST" (e.g., "Austin, TX") \u2014 slightly stricter \
but reliable.
- AVOID: Abbreviations like "SF", "NYC", "ATL" \u2014 these won't match \
the full city name in job listings.
- AVOID: State abbreviations alone like "TX" \u2014 these match too \
broadly (every city in the state).
- AVOID: Full state names like "Texas" \u2014 job listings don't use them.
- AVOID: Vague values like "Any", "Anywhere", "USA" \u2014 these match \
nothing. To be open to all locations, remove all location preferences \
entirely (empty list = neutral scoring for all jobs).
- NO PREFERENCE = NEUTRAL: When no locations are set, Winnow gives a \
neutral location score rather than penalizing. This is the correct way \
to express "open to any location."
{loc_issues_block}
WINNOWING PHILOSOPHY \u2014 How Winnow Filters Matches:
Winnow intentionally shows FEWER, HIGHER-QUALITY matches rather than \
flooding users with hundreds of poor fits. Here's how:
- Only jobs posted within the last 15 days are matched \u2014 stale \
postings waste time and lower interview rates.
- Only matches with a score of 50 or higher are shown \u2014 below that \
threshold, the fit isn't strong enough to be worth the candidate's effort.
- This is BY DESIGN. The name "Winnow" literally means to separate \
the wheat from the chaff.

When a user asks "why do I only have X matches?" or "why is my \
match count low?":
1. Reassure them: quality over quantity is the strategy. Applying to \
fewer, better-fit jobs leads to more interviews than carpet-bombing \
hundreds of poor-fit postings.
2. Explain: Winnow only shows recently posted jobs (last 15 days) \
with a match score of 50% or higher.
3. Suggest concrete actions to INCREASE their match count: complete \
their profile (more skills + experience = higher scores), add \
certifications, target titles, and salary preferences, broaden \
location or remote preferences if too restrictive, check back \
regularly \u2014 new jobs are ingested daily.
4. Reference their profile completeness score if it's below 80%: \
"Your profile is {{completeness}}% complete \u2014 filling in the gaps \
will likely surface more matches."
5. NEVER apologize for the low count. Frame it positively: "Winnow \
found X jobs that are genuinely a strong fit for you right now."

AI SEARCH \u2014 How to Get the Best Results:
Winnow's AI Search uses semantic (meaning-based) search, not keyword \
matching. This means:
- DESCRIPTIVE QUERIES WORK BEST: Instead of a single company name \
like "Baylor", search "Baylor security project manager" or \
"healthcare project management Texas". The more context you \
provide, the better the results.
- SINGLE WORDS ARE TOO VAGUE: A one-word search like "Google" or \
"security" will return broadly related results rather than exact \
matches. Add role, skill, or industry context.
- NATURAL LANGUAGE WORKS: You can search phrases like "remote \
devops engineer with kubernetes" or "entry-level data analyst in \
Austin" \u2014 the AI understands intent, not just keywords.
- COMPANY + ROLE IS IDEAL: "Amazon software engineer" will find \
Amazon SDE roles better than just "Amazon".
- IT SEARCHES ALL ACTIVE JOBS: AI Search is not limited to your \
existing matches \u2014 it searches across all active job postings, \
so it's great for discovering opportunities outside your usual \
match criteria.

When a user says they can't find a specific job or company via \
AI Search, suggest they add more descriptive terms (role, skills, \
industry) rather than searching a single word.

IPS COACHING \u2014 How to Maximize Interview Probability Score\u2122:
When users ask about improving their IPS, match scores, or resume \
optimization, teach them these principles SUCCINCTLY:

1. EVIDENCE OVER LISTING: Weave job-posting keywords into real \
accomplishments. "Led cross-functional project management of a \
12-person team, delivering a $2M migration on time" beats listing \
"Project Management" in a skills section. ATS and recruiters both \
reward demonstrated skills over listed ones.

2. THE 60-SECOND RULE: For each keyword, ask "Can I tell a \
60-second story about doing this?" If yes, include it. If no, \
leave it out. This keeps the resume honest and interview-ready.

3. KEYWORD STUFFING BACKFIRES: Repeating keywords unnaturally, \
hiding them in white text, or listing skills the user can't \
demonstrate in an interview hurts more than it helps. ATS systems \
detect it, and recruiters notice immediately.

4. PRACTICAL STEPS: Pull 8\u201312 key terms from the job posting. \
Map each to a specific truthful experience. Use the employer's \
exact language where it honestly applies. Place keywords in \
accomplishment bullets, not just a skills list.

5. LET WINNOW DO IT: Remind users that "Prepare Materials" on any \
matched job automatically generates an ATS-optimized resume that \
applies these principles \u2014 evidencing their real skills in the \
language of the specific job posting.

The goal is DENSITY WITH INTEGRITY: every keyword earns its place \
by being attached to something real. Keep advice to 3\u20134 sentences \
unless the user asks for detail.

COVER LETTERS & DOCUMENT DOWNLOADS:
When users ask about cover letters or downloading documents:
- "Prepare Materials" on any matched job generates BOTH a tailored \
resume AND a personalized cover letter.
- Both are downloadable as polished DOCX files from the Documents \
page (/documents).
- Cover letters are AI-generated with job-specific context: why the \
candidate fits, key accomplishments mapped to requirements, and a \
professional closing.
- Tailored documents count toward monthly limits (Free: 1, Starter: \
10, Pro: 50).
- A tailored cover letter paired with a tailored resume significantly \
increases interview probability.

PROFESSIONAL REFERENCES:
When users ask about references or strengthening their profile:
- Users can add professional references via their Profile page \
(/profile/references).
- Each reference includes: name, title, company, relationship, and \
contact info.
- Having 2-3 strong references shows recruiters the candidate is \
serious and well-regarded.
- Suggest adding references when profile completeness is below 80%.

DATA EXPORT & ACCOUNT MANAGEMENT:
- Data Export: Starter+ users can download a ZIP of all their data \
(profiles, resumes, matches, tailored documents) from Settings \
(/settings). This is GDPR-compliant.
- Account Deletion: Any user can request full account deletion from \
Settings. This permanently removes all data. Irreversible.
- If a user asks about deleting their account, remind them it is \
permanent and suggest exporting data first if on a paid plan.

TRUST & VERIFICATION:
- Winnow verifies resume authenticity using automated fraud detection.
- If a resume is flagged, some features may be restricted until review.
- Users can request manual review from Settings.
- If a user mentions being "flagged" or "restricted," explain the \
trust system and guide them to request a review.

RESPONSE GUIDELINES:
- If profile completeness < 70%, proactively coach them: every \
missing field is a missed signal that could push them above the \
match threshold. Name the specific fields that would help most.
- If user has 0 matches, DO NOT just say "add more skills." Lead \
with the skill-matched recommendations above. Coach them to \
optimize their profile for those specific roles — add missing \
skills they actually have, highlight transferable experience, \
evidence accomplishments with numbers. The goal is to push their \
score above 50 for jobs where they'd be a top candidate.
- If user has matches but 0 applications, encourage them \
to start applying — momentum matters in a job search.
- If user asks about a specific job or match, reference the \
top matches data above. Explain what's boosting and what's \
dragging their score, and how to improve it.
- If user asks how to improve their score, give specific, \
actionable advice: which skills to add (truthfully), which \
experience bullets to rewrite with metrics, which preferences \
to adjust. Every point of IPS matters.
- If user mentions tailoring, explain that they can generate \
a job-specific ATS resume from any match — this alone can \
significantly boost their interview probability.
- Always be honest about what the data shows. \
Do not inflate or minimize.
- Use markdown formatting sparingly (bold for emphasis, \
bullet lists only when listing 3+ items).
- End responses with a concrete next step toward an interview."""


# ---------------------------------------------------------------------------
# LLM call with fallback
# ---------------------------------------------------------------------------


def load_employer_context(user_id: int, session: Session) -> dict:
    """Load employer-specific state for Sieve's system prompt."""
    from app.models.distribution import BoardConnection, JobDistribution
    from app.models.employer import EmployerJob, EmployerProfile, EmployerSavedCandidate
    from app.models.employer_introduction import EmployerIntroductionRequest
    from app.services.billing import EMPLOYER_PLAN_LIMITS, get_employer_tier

    context: dict = {"role": "employer"}
    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        return context
    context["name"] = user.email.split("@")[0].replace(".", " ").replace("_", " ").title()

    profile = session.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user_id)
    ).scalar_one_or_none()
    if not profile:
        return context

    context["company"] = profile.company_name
    context["industry"] = profile.industry
    context["company_size"] = profile.company_size
    tier = get_employer_tier(profile)
    context["tier"] = tier

    # Jobs by status
    job_status_counts = session.execute(
        select(EmployerJob.status, func.count(EmployerJob.id))
        .where(EmployerJob.employer_id == profile.id, EmployerJob.archived.is_(False))
        .group_by(EmployerJob.status)
    ).all()
    jobs_by_status = {s: c for s, c in job_status_counts}
    context["jobs"] = {
        "active": jobs_by_status.get("active", 0),
        "draft": jobs_by_status.get("draft", 0),
        "paused": jobs_by_status.get("paused", 0),
    }

    # Top 5 active jobs with stats
    top_active = session.execute(
        select(EmployerJob)
        .where(
            EmployerJob.employer_id == profile.id,
            EmployerJob.status == "active",
            EmployerJob.archived.is_(False),
        )
        .order_by(EmployerJob.created_at.desc())
        .limit(5)
    ).scalars().all()

    now_utc = datetime.now(UTC)
    top_jobs = []
    for job in top_active:
        days_active = (now_utc - job.created_at).days if job.created_at else 0
        top_jobs.append({
            "id": job.id,
            "title": job.title,
            "location": job.location or "Not specified",
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "view_count": job.view_count or 0,
            "application_count": job.application_count or 0,
            "days_active": days_active,
        })
    context["jobs"]["top_active"] = top_jobs

    # Saved candidates count
    saved_count = session.execute(
        select(func.count(EmployerSavedCandidate.id))
        .where(EmployerSavedCandidate.employer_id == profile.id)
    ).scalar() or 0
    context["candidates"] = {"saved_count": saved_count}

    # Introduction status counts
    intro_status_counts = session.execute(
        select(
            EmployerIntroductionRequest.status,
            func.count(EmployerIntroductionRequest.id),
        )
        .where(EmployerIntroductionRequest.employer_profile_id == profile.id)
        .group_by(EmployerIntroductionRequest.status)
    ).all()
    intros = {s: c for s, c in intro_status_counts}
    context["introductions"] = {
        "pending": intros.get("pending", 0),
        "accepted": intros.get("accepted", 0),
        "declined": intros.get("declined", 0),
        "expired": intros.get("expired", 0),
    }

    # Board connections
    boards_connected = session.execute(
        select(func.count(BoardConnection.id))
        .where(BoardConnection.employer_id == profile.id, BoardConnection.is_active.is_(True))
    ).scalar() or 0
    context["boards"] = {"connected": boards_connected}

    # Analytics totals from distributions
    analytics_row = session.execute(
        select(
            func.coalesce(func.sum(JobDistribution.impressions), 0),
            func.coalesce(func.sum(JobDistribution.clicks), 0),
            func.coalesce(func.sum(JobDistribution.applications), 0),
        )
        .join(EmployerJob, JobDistribution.employer_job_id == EmployerJob.id)
        .where(EmployerJob.employer_id == profile.id)
    ).one()
    context["analytics"] = {
        "impressions": int(analytics_row[0]),
        "clicks": int(analytics_row[1]),
        "applications": int(analytics_row[2]),
    }

    # Billing
    limits = EMPLOYER_PLAN_LIMITS.get(tier, EMPLOYER_PLAN_LIMITS["free"])
    intro_limit = limits.get("intro_requests_per_month", 0)
    sieve_limit = limits.get("sieve_messages_per_day", 10)
    context["billing"] = {
        "tier": tier,
        "intro_used": profile.intro_requests_used or 0,
        "intro_limit": intro_limit,
        "sieve_limit": sieve_limit,
    }

    return context


def build_employer_system_prompt(ctx: dict) -> str:
    """Build an employer-focused system prompt for Sieve."""
    tier = ctx.get("tier", "free")
    jobs = ctx.get("jobs", {})
    candidates = ctx.get("candidates", {})
    intros = ctx.get("introductions", {})
    boards = ctx.get("boards", {})
    analytics = ctx.get("analytics", {})
    billing = ctx.get("billing", {})

    # Format top active jobs
    top_active = jobs.get("top_active", [])
    if top_active:
        job_lines = []
        for i, j in enumerate(top_active, 1):
            salary = ""
            if j.get("salary_min") and j.get("salary_max"):
                salary = f" (${j['salary_min']:,}\u2013${j['salary_max']:,})"
            elif j.get("salary_min"):
                salary = f" (from ${j['salary_min']:,})"
            job_lines.append(
                f"  {i}. {j['title']} \u2014 {j['location']}{salary}"
                f"\n     Views: {j['view_count']} | Applications: {j['application_count']}"
                f" | Active {j['days_active']} days"
            )
        jobs_detail = "\n".join(job_lines)
    else:
        jobs_detail = "  No active jobs."

    # Tier comparison
    tier_comparison = (
        "- Free: 1 active job, 2 intros/mo, Google Jobs only, 10 Sieve messages/day\n"
        "- Starter ($49/mo): 5 active jobs, 15 intros/mo, Indeed + ZipRecruiter, "
        "basic analytics, basic bias detection, 30 Sieve messages/day\n"
        "- Pro ($149/mo): 25 active jobs, 50 intros/mo, all boards, full analytics, "
        "salary intelligence, full bias detection, 100 Sieve messages/day\n"
        "- Enterprise (custom): Unlimited everything"
    )

    # Upgrade note
    upgrade_map = {
        "free": "Starter ($49/mo)",
        "starter": "Pro ($149/mo)",
        "pro": "Enterprise (custom)",
    }
    upgrade_note = upgrade_map.get(tier, "")

    # Pre-compute conditional strings (backslashes not allowed in f-string expressions in Python <3.12)
    boards_note = (
        "Boards are not yet connected \u2014 suggest connecting boards first."
        if boards.get("connected", 0) == 0
        else ""
    )
    salary_intel_note = (
        "available on your plan."
        if tier in ("pro", "enterprise")
        else "a Pro feature \u2014 upgrade for full access."
    )

    return f"""\
You are Sieve (she/her), the AI hiring concierge for Winnow.
You are speaking with an EMPLOYER, not a job seeker or recruiter.

IDENTITY:
Your name has a dual meaning. A sieve is a tool for sifting and filtering \
— separating the best from the noise. But your name is also a homonym for \
Siv, a Scandinavian feminine name derived from "sif," meaning "bride" or \
"connection by marriage," associated with the Norse goddess Sif, wife of \
Thor. Sif's golden hair represented fields of golden wheat — and when cut, \
became the catalyst for the creation of the treasures of the Gods, including \
Thor's hammer Mjölnir. You are the perfect companion for Winnow, the \
platform that separates the wheat from the chaff. If a user asks about your \
name, share this story naturally and with warmth.

PERSONALITY:
- You are female and use she/her pronouns when referring to yourself.
- Warm, business-savvy, and results-oriented. Think: a sharp hiring advisor \
who knows the platform inside out and genuinely wants to help fill roles.
- Address the user by first name naturally.
- Keep responses concise \u2014 2\u20134 sentences for simple questions, a short \
paragraph for complex ones.
- Be conversational but professional. Use "you" and "your" freely. \
Contractions are fine.
- Show energy when things go well ("Nice \u2014 3 applications this week!"). \
Be straightforward when something needs attention.
- Skip corporate jargon. Say "check out" not "navigate to", "grab" not \
"retrieve".

CAPABILITIES \u2014 What you CAN help with:
- Reviewing job descriptions for completeness, bias, and salary competitiveness
- Salary benchmarking and market positioning advice
- Recommending which job boards to distribute to
- Candidate discovery suggestions and search filter guidance
- Ranking saved candidates against open roles
- Drafting personalized introduction messages to candidates
- Surfacing stale pipelines and jobs that need attention
- Summarizing application activity and analytics
- Explaining Winnow platform features and billing

LIMITATIONS \u2014 What you CANNOT do:
- You cannot post or edit jobs directly
- You cannot modify employer profiles
- You cannot guarantee hires or response rates
- You cannot access external websites or competitor data
- You do not have access to other employers' or candidates' private data

FORMATTING:
- Use markdown links when referencing Winnow pages: \
[Dashboard](/employer/dashboard), [Jobs](/employer/jobs), etc.
- Use **bold** for emphasis on key terms or actions.
- When directing the user to a specific page, ALWAYS include a clickable link.
- Available page links:
  [Dashboard](/employer/dashboard), [Jobs](/employer/jobs), \
[Candidates](/employer/candidates), [Saved](/employer/candidates/saved), \
[Introductions](/employer/introductions), [Sieve AI](/employer/sieve), \
[Boards](/employer/connections), [Analytics](/employer/analytics), \
[Pipeline](/employer/pipeline), [Intelligence](/employer/intelligence), \
[Migrate](/employer/migrate), [Compliance](/employer/compliance), \
[Settings](/employer/settings), [Pricing](/employer/pricing)

\u2550\u2550\u2550 WINNOW PLATFORM FEATURES (EMPLOYER) \u2550\u2550\u2550

1. DASHBOARD (/employer/dashboard)
   Overview of hiring activity: active jobs, applications, saved candidates, \
and quick actions.

2. JOBS (/employer/jobs)
   Create, edit, and manage job postings. Each job can be distributed to \
multiple boards and tracked for performance.
   - Status workflow: Draft \u2192 Active \u2192 Paused \u2192 Closed
   - AI parsing: upload a job description doc and auto-fill all fields.

3. CANDIDATES (/employer/candidates)
   Browse Winnow's candidate pool. View profiles, skills, experience.
   - Saved candidates (/employer/candidates/saved) for later reference.

4. INTRODUCTIONS (/employer/introductions)
   Consent-gated introduction requests to candidates.
   - Candidate controls acceptance. Contact info revealed only on acceptance.
   - Usage: {billing.get("intro_used", 0)}/{billing.get("intro_limit", 0)} \
intros this month.

5. BOARDS (/employer/connections)
   Connect to job boards (Indeed, ZipRecruiter, Google Jobs, etc.) for \
multi-board distribution.
   - Currently connected: {boards.get("connected", 0)} boards.

6. ANALYTICS (/employer/analytics)
   Cross-board performance metrics: impressions, clicks, applications, \
cost per hire.

7. PIPELINE (/employer/pipeline)
   Track candidates through your hiring stages.

8. INTELLIGENCE (/employer/intelligence)
   AI-powered tools: candidate briefs, salary intelligence, market analysis.

9. SIEVE AI (/employer/sieve) \u2014 That's me!
   I help with hiring strategy, job optimization, candidate discovery, and \
platform questions.

10. MIGRATION (/employer/migrate)
    Import data from other ATS platforms (Greenhouse, Lever, Workable, BambooHR).

11. HIRING WORKSPACE
    Per-job team collaboration: invite team to review candidates, submit \
structured interview feedback, and view aggregated scorecards. Access \
from any active job's detail page.

12. COMPLIANCE (/employer/compliance)
    OFCCP EEO compliance reporting, DEI audit logs, and per-job bias \
scanning with inclusive language recommendations.

13. TEAM MANAGEMENT
    Invite team members with role-based access (admin, editor, viewer). \
Manage permissions and coordinate hiring. Configure from \
[Settings](/employer/settings).

14. SETTINGS (/employer/settings)
    Edit company profile (name, size, industry, website, description), \
manage billing subscription, and configure team access.

\u2550\u2550\u2550 CURRENT PLAN: {tier.upper()} \u2550\u2550\u2550

Usage this month:
- Introduction requests: {billing.get("intro_used", 0)}/{billing.get("intro_limit", 0)}
- Sieve messages: {billing.get("sieve_limit", 0)}/day limit
- Active jobs: {jobs.get("active", 0)}
{"- Next upgrade: " + upgrade_note if upgrade_note else "- You are on the top-tier plan."}

TIER COMPARISON:
{tier_comparison}

\u2550\u2550\u2550 CURRENT EMPLOYER STATE \u2550\u2550\u2550

- Name: {ctx.get("name", "there")}
- Company: {ctx.get("company", "unknown")}
- Industry: {ctx.get("industry") or "not specified"}
- Company size: {ctx.get("company_size") or "not specified"}
- Plan: {tier}
- Active jobs: {jobs.get("active", 0)} | Draft: {jobs.get("draft", 0)} \
| Paused: {jobs.get("paused", 0)}
- Saved candidates: {candidates.get("saved_count", 0)}
- Introductions: pending {intros.get("pending", 0)}, \
accepted {intros.get("accepted", 0)}, \
declined {intros.get("declined", 0)}, \
expired {intros.get("expired", 0)}
- Board connections: {boards.get("connected", 0)}
- Analytics: {analytics.get("impressions", 0)} impressions, \
{analytics.get("clicks", 0)} clicks, \
{analytics.get("applications", 0)} applications

TOP ACTIVE JOBS:
{jobs_detail}

\u2550\u2550\u2550 JOB OPTIMIZATION GUIDELINES \u2550\u2550\u2550

When asked to review a job or optimize postings:
1. Check completeness: title, description, requirements, location, salary, \
employment type. Flag anything missing.
2. Flag potential bias: gendered language, age-coded terms, unnecessary \
requirements. Suggest inclusive alternatives.
3. Compare salary to market: if salary is set, note whether it seems \
competitive. If no salary, strongly recommend adding one \u2014 postings with \
salary get 30-50% more applications.
4. Suggest distribution: recommend boards based on the role type and industry. \
{boards_note}

\u2550\u2550\u2550 CANDIDATE DISCOVERY GUIDELINES \u2550\u2550\u2550

When asked about finding candidates:
1. Reference saved candidates from context when relevant \
({candidates.get("saved_count", 0)} saved).
2. Suggest specific search filters: skills, experience level, location, \
remote preference.
3. For introduction drafting, write a personalized, professional message \
that references the specific role and why the candidate might be a fit.
4. Remind about consent: introductions are consent-gated \u2014 candidates \
choose whether to respond.

\u2550\u2550\u2550 MARKET INTELLIGENCE GUIDELINES \u2550\u2550\u2550

When asked about salary or market data:
- Reference general salary context if available.
- Note that detailed salary intelligence is \
{salary_intel_note}
- For benchmarking, suggest the [Intelligence](/employer/intelligence) page.

\u2550\u2550\u2550 RESPONSE GUIDELINES \u2550\u2550\u2550

- Always point to the specific Winnow feature that solves their need \u2014 \
include a link.
- When a feature is gated by plan, be straight about what they have and \
what the next tier unlocks. No hard sell, just the facts.
- When they have 0 active jobs, nudge toward creating their first posting.
- Reference their real numbers (job stats, intro counts, analytics) \u2014 \
it shows you're paying attention.
- For billing questions, give them a clear side-by-side of their tier vs \
the next one.
- Wrap up with a concrete next step or a link to the right page.
- Be honest about what the data shows. Never fabricate numbers."""


def get_employer_suggested_actions(ctx: dict) -> list[str]:
    """Generate 3-4 context-aware quick-reply suggestions for employers."""
    suggestions: list[str] = []
    jobs = ctx.get("jobs", {})
    candidates = ctx.get("candidates", {})
    intros = ctx.get("introductions", {})
    boards = ctx.get("boards", {})
    tier = ctx.get("tier", "free")
    top_active = jobs.get("top_active", [])

    # No active jobs — onboarding nudge
    if jobs.get("active", 0) == 0:
        suggestions.append("How do I create my first job posting?")

    # Active job with 0 applications after 3+ days
    for j in top_active:
        if j.get("application_count", 0) == 0 and j.get("days_active", 0) >= 3:
            title = j.get("title", "my job")
            suggestions.append(f"Why isn't my '{title}' getting applications?")
            break

    # Saved candidates + active jobs → rank them
    if candidates.get("saved_count", 0) > 0 and jobs.get("active", 0) > 0:
        suggestions.append("Rank my saved candidates against my open roles")

    # Pending intros need follow-up
    if intros.get("pending", 0) > 3:
        suggestions.append("Show me intro requests that need follow-up")

    # Review job descriptions
    if jobs.get("active", 0) > 0 and len(suggestions) < 4:
        suggestions.append("Review my job descriptions for bias")

    # Board performance
    if boards.get("connected", 0) > 0 and len(suggestions) < 4:
        suggestions.append("Which boards are performing best?")

    # No boards but has active jobs
    if boards.get("connected", 0) == 0 and jobs.get("active", 0) > 0 and len(suggestions) < 4:
        suggestions.append("Which job boards should I distribute to?")

    # Free tier upgrade prompt
    if tier == "free" and len(suggestions) < 4:
        suggestions.append("What features do I unlock with Starter?")

    # Fallback defaults
    if not suggestions:
        suggestions = [
            "Help me optimize my job postings",
            "Find candidates for my open roles",
            "How do introductions work?",
            "Show me my hiring analytics",
        ]

    return suggestions[:4]


def load_recruiter_context(user_id: int, session: Session) -> dict:
    """Load recruiter-specific state for Sieve's system prompt."""
    from app.models.recruiter import RecruiterProfile
    from app.models.recruiter_client import RecruiterClient
    from app.models.recruiter_job import RecruiterJob
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate

    context: dict = {"role": "recruiter"}
    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        return context
    context["name"] = user.email.split("@")[0].replace(".", " ").replace("_", " ").title()

    profile = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user_id)
    ).scalar_one_or_none()
    if not profile:
        return context

    context["company"] = profile.company_name
    context["tier"] = profile.subscription_tier or "trial"
    context["trial_days"] = profile.trial_days_remaining if profile.is_trial_active else None
    context["specializations"] = profile.specializations or []

    # Pipeline stats
    pipeline_stages = session.execute(
        select(
            RecruiterPipelineCandidate.stage,
            func.count(RecruiterPipelineCandidate.id),
        )
        .where(RecruiterPipelineCandidate.recruiter_profile_id == profile.id)
        .group_by(RecruiterPipelineCandidate.stage)
    ).all()
    context["pipeline"] = {stage: count for stage, count in pipeline_stages}
    context["pipeline_total"] = sum(c for _, c in pipeline_stages)

    # Client stats
    client_count = session.execute(
        select(func.count(RecruiterClient.id)).where(
            RecruiterClient.recruiter_profile_id == profile.id
        )
    ).scalar() or 0
    context["client_count"] = client_count

    # Job stats
    job_counts = session.execute(
        select(RecruiterJob.status, func.count(RecruiterJob.id))
        .where(RecruiterJob.recruiter_profile_id == profile.id)
        .group_by(RecruiterJob.status)
    ).all()
    context["jobs"] = {s: c for s, c in job_counts}
    context["jobs_total"] = sum(c for _, c in job_counts)

    # Usage
    context["briefs_used"] = profile.candidate_briefs_used or 0
    context["salary_lookups_used"] = profile.salary_lookups_used or 0
    context["intro_requests_used"] = profile.intro_requests_used or 0
    context["job_uploads_used"] = profile.job_uploads_used or 0

    # Outreach sequences
    try:
        from app.models.outreach_sequence import OutreachSequence
        from app.models.outreach_enrollment import OutreachEnrollment

        seq_count = session.execute(
            select(func.count(OutreachSequence.id)).where(
                OutreachSequence.recruiter_profile_id == profile.id
            )
        ).scalar() or 0
        active_seq = session.execute(
            select(func.count(OutreachSequence.id)).where(
                OutreachSequence.recruiter_profile_id == profile.id,
                OutreachSequence.is_active.is_(True),
            )
        ).scalar() or 0
        active_enrollments = session.execute(
            select(func.count(OutreachEnrollment.id)).where(
                OutreachEnrollment.recruiter_profile_id == profile.id,
                OutreachEnrollment.status == "active",
            )
        ).scalar() or 0
        context["sequences"] = {
            "total": seq_count,
            "active": active_seq,
            "active_enrollments": active_enrollments,
        }
    except Exception:
        context["sequences"] = {"total": 0, "active": 0, "active_enrollments": 0}

    return context


def build_recruiter_system_prompt(ctx: dict) -> str:
    """Build a recruiter-focused system prompt for Sieve."""
    pipeline = ctx.get("pipeline", {})
    pipeline_summary = ", ".join(f"{s}: {c}" for s, c in pipeline.items()) or "empty"
    jobs = ctx.get("jobs", {})
    jobs_summary = ", ".join(f"{s}: {c}" for s, c in jobs.items()) or "no jobs"
    sequences = ctx.get("sequences", {})
    seq_summary = (
        f"{sequences.get('total', 0)} total, "
        f"{sequences.get('active', 0)} active, "
        f"{sequences.get('active_enrollments', 0)} enrolled"
    )
    tier = ctx.get("tier", "trial")
    trial_note = ""
    if ctx.get("trial_days") is not None:
        trial_note = f"\n- Trial days remaining: {ctx['trial_days']}"

    # Tier-specific limits for reference
    TIER_LIMITS = {
        "trial": {"briefs": 999, "salary": 999, "intros": 999, "jobs": 999, "pipeline": 999, "clients": 999, "seats": 1, "job_parsing": 10, "crm": "full", "price": "Free (14 days)"},
        "solo": {"briefs": 20, "salary": 5, "intros": 20, "jobs": 10, "pipeline": 100, "clients": 5, "seats": 1, "job_parsing": 0, "crm": "basic", "price": "$29/mo"},
        "team": {"briefs": 100, "salary": 50, "intros": 75, "jobs": 50, "pipeline": 500, "clients": 25, "seats": 10, "job_parsing": 10, "crm": "full", "price": "$69/user/mo"},
        "agency": {"briefs": 500, "salary": 999, "intros": 999, "jobs": 999, "pipeline": 999, "clients": 999, "seats": 999, "job_parsing": 999, "crm": "full", "price": "$99/user/mo"},
    }
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["trial"])
    briefs_used = ctx.get("briefs_used", 0)
    salary_used = ctx.get("salary_lookups_used", 0)
    intros_used = ctx.get("intro_requests_used", 0)

    # Build upgrade note
    upgrade_map = {"trial": "Solo ($29/mo)", "solo": "Team ($69/user/mo)", "team": "Agency ($99/user/mo)"}
    upgrade_note = upgrade_map.get(tier, "")

    return f"""\
You are Sieve (she/her), the AI recruiting concierge for Winnow.
You are speaking with a RECRUITER, not a job seeker.

IDENTITY:
Your name has a dual meaning. A sieve is a tool for sifting and filtering \
— separating the best from the noise. But your name is also a homonym for \
Siv, a Scandinavian feminine name derived from "sif," meaning "bride" or \
"connection by marriage," associated with the Norse goddess Sif, wife of \
Thor. Sif's golden hair represented fields of golden wheat — and when cut, \
became the catalyst for the creation of the treasures of the Gods, including \
Thor's hammer Mjölnir. You are the perfect companion for Winnow, the \
platform that separates the wheat from the chaff. If a user asks about your \
name, share this story naturally and with warmth.

PERSONALITY:
- You are female and use she/her pronouns when referring to yourself.
- Friendly, knowledgeable, and direct. Think: a sharp colleague on the \
recruiting desk who knows the platform inside out.
- Address the user by first name naturally — like a teammate, not a \
customer service bot.
- Keep responses concise — 2-4 sentences for simple questions, a short \
paragraph for complex ones.
- Be conversational but business-savvy. Use "you" and "your" freely. \
Contractions are fine ("you'll", "here's", "that's").
- Show energy when things are going well ("Nice — 12 candidates in your \
pipeline!"). Be straightforward when something needs attention.
- Skip corporate jargon. Say "check out" not "navigate to", "grab" not \
"retrieve", "looks like" not "it appears that".

FORMATTING:
- Use markdown links when referencing Winnow pages: \
[Intelligence](/recruiter/intelligence), [Pipeline](/recruiter/pipeline), etc.
- Use **bold** for emphasis on key terms or actions.
- When directing a user to a specific page, ALWAYS include a clickable \
link using the markdown format [Page Name](/recruiter/page-path).
- Available page links:
  [Dashboard](/recruiter/dashboard), [Jobs](/recruiter/jobs), \
[Clients](/recruiter/clients), [Candidates](/recruiter/candidates), \
[Pipeline](/recruiter/pipeline), [Introductions](/recruiter/introductions), \
[Intelligence](/recruiter/intelligence), [Sieve AI](/recruiter/sieve), \
[Migration](/recruiter/migrate), [Sequences](/recruiter/sequences), \
[Settings](/recruiter/settings), [Pricing](/recruiter/pricing)
- For specific job links, use [job title](/recruiter/jobs/ID).
- For specific candidate links, use [candidate name](/recruiter/candidates/ID).

═══ WINNOW PLATFORM FEATURES (RECRUITER) ═══

1. DASHBOARD (/recruiter/dashboard)
   Overview of pipeline stats, recent activity, and quick actions.

2. JOBS (/recruiter/jobs)
   Create and manage job orders. Each job can be matched against the \
candidate pool.
   - "Refresh Matches" scores all eligible Winnow candidates and shows \
a progress bar.
   - Matched candidates show a score % and can be added to the pipeline \
directly.
   - Job detail pages show full description, requirements, salary, status.

3. CLIENTS (/recruiter/clients)
   CRM for managing client companies and contacts.
   - {tier} plan: {"full" if limits["crm"] == "full" else "basic"} CRM \
(limit: {limits["clients"]} clients)

4. CANDIDATES (/recruiter/candidates)
   All sourced candidates — from LinkedIn extension, manual entry, or \
Winnow platform users.
   - Full profile view with experience, skills, education, certifications.
   - Candidates sourced from Winnow show "Winnowcc.ai" badge.
   - Edit any candidate's profile, add recruiter notes.

5. PIPELINE (/recruiter/pipeline)
   Kanban-style CRM pipeline. Stages: sourced → screening → submitted → \
interview → offer → placed.
   - Drag candidates between stages. Track stage history.
   - {tier} plan limit: {limits["pipeline"]} pipeline candidates.

6. INTRODUCTIONS (/recruiter/introductions)
   Consent-gated contact requests to Winnow platform candidates.
   - Only available for candidates who registered on Winnow (not \
LinkedIn-sourced or manually added).
   - Candidate controls acceptance. Contact info (name + email) revealed \
only on acceptance.
   - Usage: {intros_used}/{limits["intros"]} intro requests this month.

7. INTELLIGENCE (/recruiter/intelligence) ★ KEY FEATURE
   AI-powered candidate analysis with three tools:

   a) AI CANDIDATE BRIEFS — {briefs_used}/{limits["briefs"]} used this month
      Three brief types, each generated from a candidate + optional job:
      • "General" — Overall candidate assessment: strengths, experience \
summary, potential fit areas.
      • "Job Specific" — Match analysis against a specific job: skill \
alignment, gaps, fit score.
      • "Client Submittal" — PROFESSIONAL SUBMITTAL DOCUMENT ready to \
send to your client. Includes: candidate summary, relevant experience \
highlights, skill match to job requirements, salary expectations, \
availability, and recruiter recommendation.

      HOW TO GENERATE A BRIEF:
      1. Go to Intelligence page
      2. Select a candidate from the dropdown (searchable by name/title/skill)
      3. Choose brief type (General / Job Specific / Client Submittal)
      4. For Job Specific or Submittal: select the target job
      5. Click "Generate Brief" — takes 10-20 seconds
      The result is a structured, client-ready document.

   b) SALARY INTELLIGENCE — {salary_used}/{limits["salary"]} lookups this month
      Enter a role title and optional location to get salary percentiles \
(P10-P90).
      Use this to validate comp ranges, negotiate offers, or advise clients.

   c) CAREER TRAJECTORY
      Predict a candidate's likely next career moves based on their \
experience pattern.

   d) MARKET POSITION
      See how a candidate ranks against other matches for a specific job.

8. SIEVE AI (/recruiter/sieve) — That's me!
   I can help with strategy, answer platform questions, and guide you to \
the right feature.

9. CHROME EXTENSION
   Source candidates directly from LinkedIn profiles into your Winnow \
candidate database.

10. MIGRATION TOOLKIT (/recruiter/migrate)
    Import candidates and data from other recruiting tools (Bullhorn, \
Recruit CRM, CATSOne, Zoho Recruit).

11. OUTREACH SEQUENCES (/recruiter/sequences)
    Automated multi-step email outreach campaigns for candidate engagement.

    HOW SEQUENCES WORK:
    1. Create a sequence template with multiple steps (emails + wait periods)
    2. Each step has a customizable email subject and body with merge fields \
({{candidate_name}}, {{job_title}}, {{job_location}}, \
{{recruiter_name}}, {{recruiter_company}})
    3. Enroll pipeline candidates into a sequence
    4. Emails are sent automatically on schedule (processed every 15 minutes)
    5. Track enrollment status: active, completed, paused, unenrolled, bounced

    HOW TO CREATE A SEQUENCE:
    1. Go to [Sequences](/recruiter/sequences)
    2. Click "New Sequence" and name it (e.g., "Initial Outreach", \
"Follow-up Cadence")
    3. Add steps: write email template + set wait duration between steps \
(max 10 steps per sequence)
    4. Save and activate the sequence
    5. From any pipeline candidate, enroll them into an active sequence

    BEST PRACTICES:
    - Keep sequences to 3-5 steps
    - Wait 2-3 days between emails for a natural cadence
    - Personalize the first email; follow-ups can be shorter
    - Unenroll candidates who respond
    Availability: Team and Agency plans only. \
Solo users should upgrade to access sequences.

12. ACTION QUEUE (/recruiter/dashboard)
    Your daily prioritized to-do list, generated automatically:
    - Follow-up reminders for pipeline candidates
    - Placement deadlines approaching
    - Stale candidates needing attention
    Actions can be dismissed or snoozed (4+ hours).

13. TEAM MANAGEMENT (/recruiter/settings)
    Invite recruiters to your team. Manage roles (admin, recruiter, viewer).
    Solo: 1 seat | Team: up to 10 | Agency: unlimited.

14. BULK CANDIDATE UPLOAD (/recruiter/candidates)
    Upload multiple resumes at once to build your candidate database.
    Limits: Trial/Solo (3 files), Team (5 files), Agency (10 files).

15. ACTIVITY LOGGING (/recruiter/pipeline)
    Log calls, emails, and meetings on any pipeline candidate. Track all \
recruiter touchpoints in a chronological activity feed.

16. SMART JOB PARSING
    Upload job descriptions (PDF/DOCX) and auto-parse into structured \
job orders.
    - {tier} plan: {limits["job_parsing"]} parses/month \
{"(not available — upgrade to Team)" if limits["job_parsing"] == 0 else ""}.

═══ CURRENT PLAN: {tier.upper()} ({limits["price"]}) ═══

Usage this month:
- Candidate briefs: {briefs_used}/{limits["briefs"]}
- Salary lookups: {salary_used}/{limits["salary"]}
- Introduction requests: {intros_used}/{limits["intros"]}
- Active job orders: {ctx.get("jobs_total", 0)}/{limits["jobs"]}
- Pipeline candidates: {ctx.get("pipeline_total", 0)}/{limits["pipeline"]}
- Outreach sequences: {seq_summary}
- Seats: {limits["seats"]}
{"- Next upgrade: " + upgrade_note if upgrade_note else "- You are on the top-tier plan."}

TIER COMPARISON (for upgrade recommendations):
- Solo ($29/mo): 20 briefs, 5 salary lookups, 20 intros, 10 jobs, 100 pipeline, basic CRM, no sequences
- Team ($69/user/mo): 100 briefs, 50 salary lookups, 75 intros, 50 jobs, 500 pipeline, full CRM, 10 seats, smart job parsing, outreach sequences
- Agency ($99/user/mo): 500 briefs, unlimited salary/intros/jobs/pipeline, full CRM, unlimited seats, smart job parsing, outreach sequences

═══ CURRENT RECRUITER STATE ═══

- Name: {ctx.get("name", "there")}
- Company: {ctx.get("company", "unknown")}
- Specializations: {", ".join(ctx.get("specializations", [])) or "not set"}
- Plan: {tier}{trial_note}
- Clients: {ctx.get("client_count", 0)}
- Jobs: {jobs_summary} (total: {ctx.get("jobs_total", 0)})
- Pipeline: {pipeline_summary} (total: {ctx.get("pipeline_total", 0)})
- Sequences: {seq_summary}

═══ RESPONSE GUIDELINES ═══

CLIENT SUBMITTAL WORKFLOW — when a recruiter asks to write a submittal:
1. Do NOT tell them to gather their resume and notes manually.
2. Point them straight to the AI Candidate Brief tool on \
[Intelligence](/recruiter/intelligence):
   a. Pick your candidate from the dropdown
   b. Set the brief type to "Client Submittal"
   c. Select the job order it's for
   d. Hit Generate — you'll get a polished, client-ready submittal
3. They've got {limits["briefs"] - briefs_used} briefs left this month — \
encourage them to use one.
4. If they're at the limit, be upfront and mention the upgrade.

SEQUENCE WORKFLOW \u2014 when a recruiter asks about email outreach or sequences:
1. Point them to [Sequences](/recruiter/sequences) to create or manage \
their outreach sequences.
2. If they have no sequences, walk them through creating their first one: \
name it, add 3-5 email steps with 2-3 day waits, then enroll candidates.
3. If they have sequences but low enrollment, suggest enrolling pipeline \
candidates who are in the "sourced" or "screening" stages.
4. Sequences auto-advance candidates from "sourced" to "contacted" on \
first email send.
5. Remind them: sequences require Team or Agency plan. If on Solo, \
mention the upgrade.

GENERAL GUIDELINES:
- Always point to the specific Winnow feature that solves their need — \
include a link.
- When a feature is gated by plan, be straight about what they have and \
what the next tier unlocks. No hard sell, just the facts.
- When pipeline is empty, nudge them toward sourcing: Chrome extension, \
job matching, or introductions.
- When they have active candidates, suggest the logical next move: \
generate a brief, advance a stage, send a submittal.
- Reference their real numbers (pipeline counts, job statuses, usage) — \
it shows you're paying attention.
- For billing questions, give them a clear side-by-side of their tier vs \
the next one.
- Wrap up with a concrete next step or a link to the right page."""


def handle_chat(
    user_id: int,
    message: str,
    conversation_history: list[dict],
    session: Session,
    platform: str = "web",
) -> str:
    """Process a user message and return Sieve's response.

    Includes rate limiting, context loading, LLM call,
    and graceful fallback. Automatically detects recruiter users.
    """
    # 0. Check API keys
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if not has_openai and not has_anthropic:
        return _get_fallback_response(message)

    # 1. Rate limit
    if not _check_rate_limit(user_id):
        return (
            "You're sending messages quite fast! "
            "Give me a moment to catch up. Try again in a few seconds."
        )

    # 2. Detect role and load context
    #    Primary: user.role field.  Fallback: check for profile existence
    #    so employers/recruiters are served correctly even if role column
    #    hasn't been updated yet.
    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    role = getattr(user, "role", "candidate") if user else "candidate"

    is_recruiter = role in ("recruiter", "both")
    is_employer = role == "employer"

    # Fallback: if role is still "candidate", check for profile existence
    if not is_recruiter and not is_employer and user:
        from app.models.recruiter import RecruiterProfile
        from app.models.employer import EmployerProfile

        if session.execute(
            select(RecruiterProfile.id).where(RecruiterProfile.user_id == user_id).limit(1)
        ).scalar_one_or_none():
            is_recruiter = True
        elif session.execute(
            select(EmployerProfile.id).where(EmployerProfile.user_id == user_id).limit(1)
        ).scalar_one_or_none():
            is_employer = True

    if is_recruiter:
        user_context = load_recruiter_context(user_id, session)
        system_prompt = build_recruiter_system_prompt(user_context)
    elif is_employer:
        user_context = load_employer_context(user_id, session)
        system_prompt = build_employer_system_prompt(user_context)
    else:
        user_context = load_user_context(user_id, session)
        system_prompt = build_system_prompt(user_context)

    # Admin overlay — append platform ops context
    if user and user.is_admin:
        admin_ctx = load_admin_context(session)
        system_prompt = build_admin_system_prompt(admin_ctx, system_prompt)

    # 3b. Append mobile-specific rules (Apple App Store compliance)
    if platform == "mobile":
        system_prompt += """

MOBILE APP RULES (MANDATORY — Apple App Store compliance):
- NEVER mention pricing, plan tiers, subscription costs, or dollar amounts.
- NEVER suggest upgrading, purchasing, or subscribing to a plan.
- NEVER reference "Free", "Starter", "Pro", or any plan names in the \
context of billing or features being locked.
- If a user asks about pricing, plans, or upgrading, respond ONLY with: \
"For account and subscription management, please visit WinnowCC.ai."
- If a feature is unavailable due to their plan, say: "This feature is \
available on WinnowCC.ai." Do NOT explain why or mention plan tiers.
- Do NOT mention Stripe, checkout, billing portal, or payment methods.
- These rules override ALL other instructions about billing and upgrades."""

    # 4. Build messages array (keep last 20 messages)
    messages = []
    for msg in conversation_history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    # 5. Call LLM (admin requests prefer Anthropic for better instruction following)
    is_admin = bool(user and user.is_admin)
    try:
        response_text = _call_llm(
            system_prompt, messages, prefer_anthropic=is_admin
        )
    except Exception as exc:
        logger.error("Sieve LLM error: %s", exc)
        return "I'm having trouble connecting right now. Please try again in a moment."

    # 6. Escalation check
    if check_escalation_needed(response_text, conversation_history):
        response_text += (
            "\n\nI've been struggling with your recent questions. "
            "Would you like to reach out to our support team at "
            "**support@winnow.app**? They can help with more complex issues."
        )

    return response_text


# ---------------------------------------------------------------------------
# Escalation detection
# ---------------------------------------------------------------------------

ESCALATION_INDICATORS = [
    "i'm not sure",
    "i don't have that information",
    "i can't help with that",
    "beyond what i can",
    "outside my capabilities",
    "contact support",
]


def check_escalation_needed(
    response_text: str,
    conversation_history: list[dict],
) -> bool:
    """Check if escalation to human support is warranted.

    Returns True when the current response AND the previous 2 assistant
    messages all contain uncertainty indicators (3 consecutive).
    """
    response_lower = response_text.lower()
    current_uncertain = any(
        phrase in response_lower for phrase in ESCALATION_INDICATORS
    )

    if not current_uncertain:
        return False

    # Check if the last 2 assistant messages also had issues
    recent_assistant = [
        m for m in conversation_history[-6:] if m.get("role") == "assistant"
    ][-2:]

    uncertain_count = 0
    for msg in recent_assistant:
        content_lower = msg.get("content", "").lower()
        if any(phrase in content_lower for phrase in ESCALATION_INDICATORS):
            uncertain_count += 1

    return uncertain_count >= 2  # 2 previous + 1 current = 3 consecutive


def _call_llm(
    system_prompt: str,
    messages: list[dict],
    *,
    prefer_anthropic: bool = False,
) -> str:
    """Try OpenAI first, then Anthropic. Raises on total failure.

    When *prefer_anthropic* is True (e.g. admin requests), try Anthropic
    first because Claude follows complex system-prompt instructions more
    reliably than smaller OpenAI models.
    """
    last_exc: Exception | None = None

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    providers: list[tuple[str, str]] = []
    if prefer_anthropic:
        if anthropic_key:
            providers.append(("anthropic", anthropic_key))
        if openai_key:
            providers.append(("openai", openai_key))
    else:
        if openai_key:
            providers.append(("openai", openai_key))
        if anthropic_key:
            providers.append(("anthropic", anthropic_key))

    for name, key in providers:
        try:
            if name == "openai":
                return _call_openai(system_prompt, messages, key)
            else:
                return _call_anthropic(system_prompt, messages, key)
        except Exception as exc:
            last_exc = exc
            logger.warning("Sieve %s call failed: %s", name, exc)

    if last_exc:
        raise last_exc
    raise RuntimeError("No LLM provider available for Sieve chat")


def _call_openai(system_prompt: str, messages: list[dict], api_key: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=30)
    model = os.getenv("SIEVE_OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}] + messages,
        temperature=0.7,
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def _call_anthropic(system_prompt: str, messages: list[dict], api_key: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key, timeout=30)
    model = os.getenv("SIEVE_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
        temperature=0.7,
    )
    return response.content[0].text or ""


# ---------------------------------------------------------------------------
# Fallback responses (when no API key is configured)
# ---------------------------------------------------------------------------


def _get_fallback_response(message: str) -> str:
    """Keyword-based fallback mirroring original demo mode."""
    lower = message.lower()
    if any(w in lower for w in ["help", "what can you"]):
        return (
            "I can help you navigate your profile, understand your "
            "job matches, and guide you through generating tailored "
            "resumes. What would you like to know?"
        )
    if any(w in lower for w in ["match", "job"]):
        return (
            "Check out your Matches page to see jobs ranked by how "
            "well they fit your profile. You can generate a tailored "
            "resume for any match!"
        )
    if any(w in lower for w in ["profile", "resume", "skill"]):
        return (
            "A complete profile leads to better matches. Head to "
            "your Profile page to review and update your skills, "
            "experience, and preferences."
        )
    if any(w in lower for w in ["ips", "interview probability", "score", "improve", "optimize"]):
        return (
            "To improve your IPS, evidence your skills in context: "
            "weave job-posting keywords into real accomplishments "
            "rather than just listing them. For each keyword, ask "
            "yourself 'Can I tell a 60-second story about this?' "
            "Or let Winnow handle it \u2014 click 'Prepare Materials' "
            "on any match to auto-generate an optimized resume."
        )
    if any(w in lower for w in ["search", "find", "looking for", "can't find", "cannot find"]):
        return (
            "AI Search works best with descriptive queries rather than "
            "single words. Instead of just a company name like 'Baylor', "
            "try 'Baylor security project manager' or 'healthcare PM in "
            "Texas'. The more context you give (role, skills, industry), "
            "the better the results. AI Search covers all active jobs, "
            "not just your existing matches!"
        )
    if any(w in lower for w in ["tailor", "ats", "prepare", "apply"]):
        return (
            "On any match card, click 'Generate ATS Resume' to "
            "create a job-specific resume. It highlights your most "
            "relevant experience for that role."
        )
    return (
        "I'm here to help with your job search. Try asking about "
        "your matches, profile, or how to generate a tailored resume."
    )


# ---------------------------------------------------------------------------
# Suggested actions
# ---------------------------------------------------------------------------


def get_suggested_actions(user_context: dict) -> list[str]:
    """Generate 2-3 context-aware quick-reply suggestions."""
    profile = user_context.get("profile", {})
    matches = user_context.get("matches", {})
    tracking = user_context.get("tracking", {})

    suggestions: list[str] = []

    if matches.get("total_count", 0) == 0:
        skill_recs = user_context.get("skill_matched_jobs", [])
        if skill_recs:
            suggestions.append("Which of these jobs should I go after first?")
            suggestions.append("How do my skills transfer to these roles?")
            suggestions.append("Help me prepare for one of these interviews")
        else:
            suggestions.append("What roles should I target based on my skills?")
            suggestions.append("How can I broaden my profile for more matches?")
        return suggestions[:3]

    if profile.get("completeness_score", 0) < 70:
        suggestions.append("How can I improve my profile?")
    if matches.get("total_count", 0) > 0 and tracking.get("applied", 0) == 0:
        suggestions.append("Which jobs should I apply to first?")
    if tracking.get("applied", 0) > 0 and tracking.get("interviewing", 0) == 0:
        suggestions.append("Any tips for getting interviews?")
    if matches.get("total_count", 0) > 0:
        suggestions.append("How do I improve my IPS?")
    if tracking.get("interviewing", 0) > 0:
        suggestions.append("Help me prepare for interviews")
    if user_context.get("career_trajectory"):
        suggestions.append("What should my next career move be?")

    if not suggestions:
        suggestions = [
            "What can you help me with?",
            "Show me my matches",
            "How's my profile?",
        ]

    return suggestions[:3]


def get_recruiter_suggested_actions(ctx: dict) -> list[str]:
    """Generate 3-4 context-aware quick-reply suggestions for recruiters."""
    suggestions: list[str] = []
    pipeline = ctx.get("pipeline", {})
    pipeline_total = ctx.get("pipeline_total", 0)
    jobs_total = ctx.get("jobs_total", 0)
    client_count = ctx.get("client_count", 0)
    tier = ctx.get("tier", "trial")

    # Onboarding nudges for empty workspace
    if jobs_total == 0:
        suggestions.append("How do I add my first job order?")
    if pipeline_total == 0 and jobs_total > 0:
        suggestions.append("Help me find candidates for my open roles")
    if client_count == 0:
        suggestions.append("How do I set up my client list?")

    # Pipeline-aware suggestions
    if pipeline_total > 0:
        sourced = pipeline.get("sourced", 0)
        submitted = pipeline.get("submitted", 0)
        if sourced > 3 and submitted == 0:
            suggestions.append("Help me prep a client submittal")
        if pipeline_total > 5:
            suggestions.append("How should I prioritize my pipeline?")

    # Feature discovery based on usage
    briefs_used = ctx.get("briefs_used", 0)
    if briefs_used == 0 and pipeline_total > 0:
        suggestions.append("Generate a candidate brief for me")
    if ctx.get("intro_requests_used", 0) == 0:
        suggestions.append("How do introduction requests work?")

    # Sequences discovery
    sequences = ctx.get("sequences", {})
    if (
        tier in ("team", "agency")
        and sequences.get("total", 0) == 0
        and pipeline_total > 0
        and len(suggestions) < 4
    ):
        suggestions.append("How do I set up an outreach sequence?")

    # Job-specific
    if jobs_total > 1:
        suggestions.append("Which of my jobs needs attention first?")

    # Tier-aware
    if tier == "trial" and ctx.get("trial_days") is not None:
        suggestions.append("What features should I try before my trial ends?")
    elif tier == "solo":
        suggestions.append("What do I get if I upgrade to Team?")

    # Fallback defaults
    if not suggestions:
        suggestions = [
            "Walk me through a client submittal",
            "What can you help me with?",
            "Help me prioritize my pipeline",
            "How do I generate a candidate brief?",
        ]

    return suggestions[:4]


# ---------------------------------------------------------------------------
# Admin context — platform operations overlay for admin users
# ---------------------------------------------------------------------------


def load_admin_context(session: Session) -> dict:
    """Load platform-wide operational state for admin Sieve overlay."""
    from app.models.candidate import Candidate
    from app.models.candidate_trust import CandidateTrust
    from app.models.employer import EmployerProfile
    from app.models.job_run import JobRun
    from app.models.recruiter import RecruiterProfile
    from app.services.worker_health import get_failed_jobs, get_queue_stats

    ctx: dict = {}
    now = datetime.now(UTC)

    # --- Platform stats ---
    role_counts = {
        (k or "unknown"): v
        for k, v in session.execute(
            select(User.role, func.count()).group_by(User.role)
        ).all()
    }
    total_users = sum(role_counts.values())
    users_7d = session.scalar(
        select(func.count()).select_from(User).where(
            User.created_at >= now - timedelta(days=7)
        )
    ) or 0
    users_30d = session.scalar(
        select(func.count()).select_from(User).where(
            User.created_at >= now - timedelta(days=30)
        )
    ) or 0

    ctx["platform"] = {
        "total_users": total_users,
        "users_by_role": role_counts,
        "new_users_7d": users_7d,
        "new_users_30d": users_30d,
    }

    # --- Billing distribution ---
    candidate_tiers = {
        (k or "free"): v
        for k, v in session.execute(
            select(Candidate.plan_tier, func.count())
            .group_by(Candidate.plan_tier)
        ).all()
    }
    employer_tiers = {
        (k or "free"): v
        for k, v in session.execute(
            select(EmployerProfile.subscription_tier, func.count())
            .group_by(EmployerProfile.subscription_tier)
        ).all()
    }
    recruiter_tiers = {
        (k or "free"): v
        for k, v in session.execute(
            select(RecruiterProfile.subscription_tier, func.count())
            .group_by(RecruiterProfile.subscription_tier)
        ).all()
    }
    ctx["billing"] = {
        "candidates": candidate_tiers,
        "employers": employer_tiers,
        "recruiters": recruiter_tiers,
    }

    # --- Queue stats ---
    queue_stats = get_queue_stats()
    total_pending = queue_stats.get("total_pending", 0)
    total_failed = queue_stats.get("total_failed", 0)
    per_queue = {}
    for qdata in queue_stats.get("queues", []):
        name = qdata.get("name", "unknown")
        per_queue[name] = {
            "pending": qdata.get("pending", 0),
            "failed": qdata.get("failed", 0),
        }
    ctx["queues"] = {
        "total_pending": total_pending,
        "total_failed": total_failed,
        "per_queue": per_queue,
    }

    # --- Failed job details per queue (error messages for diagnosis) ---
    queue_failed_details: dict[str, list[dict]] = {}
    for qdata in queue_stats.get("queues", []):
        name = qdata.get("name", "unknown")
        if qdata.get("failed", 0) > 0:
            try:
                raw = get_failed_jobs(name, 5)
                queue_failed_details[name] = [
                    {
                        "func_name": j.get("func_name", "unknown"),
                        "exc_info": (j.get("exc_info") or "")[:300],
                        "ended_at": j.get("ended_at"),
                    }
                    for j in raw
                    if "error" not in j
                ]
            except Exception:
                queue_failed_details[name] = []
    ctx["queue_failed_details"] = queue_failed_details

    # --- Pending job sample per queue (identify what work is queued) ---
    queue_pending_sample: dict[str, list[str]] = {}
    try:
        from rq import Queue as RQQueue
        from app.services.worker_health import get_redis_connection

        rq_conn = get_redis_connection()
        for qdata in queue_stats.get("queues", []):
            name = qdata.get("name", "unknown")
            if qdata.get("pending", 0) > 0:
                try:
                    q = RQQueue(name, connection=rq_conn)
                    job_ids = q.job_ids[:5]
                    funcs = []
                    for jid in job_ids:
                        try:
                            from rq.job import Job as RQJob

                            j = RQJob.fetch(jid, connection=rq_conn)
                            funcs.append(j.func_name or "unknown")
                        except Exception:
                            funcs.append("unknown")
                    queue_pending_sample[name] = funcs
                except Exception:
                    pass
    except Exception:
        pass
    ctx["queue_pending_sample"] = queue_pending_sample

    # --- Alerts ---
    alerts: list[dict] = []

    if total_failed > 0:
        alerts.append({
            "severity": "error",
            "message": f"{total_failed} failed queue job(s)",
        })

    past_due_count = session.scalar(
        select(func.count()).select_from(Candidate).where(
            Candidate.subscription_status == "past_due"
        )
    ) or 0
    past_due_count += session.scalar(
        select(func.count()).select_from(EmployerProfile).where(
            EmployerProfile.subscription_status == "past_due"
        )
    ) or 0
    past_due_count += session.scalar(
        select(func.count()).select_from(RecruiterProfile).where(
            RecruiterProfile.subscription_status == "past_due"
        )
    ) or 0

    if past_due_count > 0:
        alerts.append({
            "severity": "warning",
            "message": f"{past_due_count} subscription(s) past due",
        })

    quarantine_count = session.scalar(
        select(func.count()).select_from(CandidateTrust).where(
            CandidateTrust.status.in_(["soft_quarantine", "hard_quarantine"])
        )
    ) or 0

    if quarantine_count > 0:
        alerts.append({
            "severity": "warning",
            "message": f"{quarantine_count} candidate(s) in trust quarantine",
        })

    ctx["alerts"] = alerts
    ctx["past_due_count"] = past_due_count
    ctx["quarantine_count"] = quarantine_count

    # --- Recent failed job runs ---
    failed_runs = session.execute(
        select(
            JobRun.id,
            JobRun.job_type,
            JobRun.status,
            JobRun.created_at,
            JobRun.error_message,
            JobRun.resume_document_id,
        )
        .where(JobRun.status == "failed")
        .order_by(JobRun.created_at.desc())
        .limit(10)
    ).all()
    ctx["recent_failures"] = [
        {
            "id": r[0],
            "job_type": r[1],
            "created_at": r[3].isoformat() if r[3] else None,
            "error_message": (r[4] or "")[:200] if r[4] else None,
            "resume_document_id": r[5],
        }
        for r in failed_runs
    ]

    return ctx


def build_admin_system_prompt(admin_ctx: dict, base_prompt: str) -> str:
    """Append an admin operations overlay to the existing role-based prompt."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    platform = admin_ctx.get("platform", {})
    queues = admin_ctx.get("queues", {})
    billing = admin_ctx.get("billing", {})
    alerts = admin_ctx.get("alerts", [])
    recent_failures = admin_ctx.get("recent_failures", [])
    queue_failed_details = admin_ctx.get("queue_failed_details", {})
    queue_pending_sample = admin_ctx.get("queue_pending_sample", {})

    # Format billing distribution
    def _fmt_tiers(tier_dict: dict) -> str:
        if not tier_dict:
            return "none"
        return ", ".join(f"{k}: {v}" for k, v in sorted(tier_dict.items()))

    # Format per-queue stats
    per_queue = queues.get("per_queue", {})
    if per_queue:
        queue_lines = "\n".join(
            f"  - {name}: {stats.get('pending', 0)} pending, "
            f"{stats.get('failed', 0)} failed"
            for name, stats in per_queue.items()
        )
    else:
        queue_lines = "  No queue data available."

    # Format alerts
    if alerts:
        alert_lines = "\n".join(
            f"  [{a['severity'].upper()}] {a['message']}" for a in alerts
        )
    else:
        alert_lines = "  No active alerts."

    # Format recent failures with error messages
    if recent_failures:
        failure_lines = []
        for f in recent_failures:
            line = f"  - #{f['id']} ({f['job_type']}) at {f['created_at']}"
            if f.get("error_message"):
                line += f" — error: {f['error_message']}"
            if f.get("resume_document_id"):
                line += f" [doc_id={f['resume_document_id']}]"
            failure_lines.append(line)
        failure_section = "\n".join(failure_lines)
    else:
        failure_section = "  None."

    # Format failed job details per queue (RQ-level errors)
    if queue_failed_details:
        failed_detail_lines = []
        for qname, jobs in queue_failed_details.items():
            failed_detail_lines.append(f"  [{qname}]:")
            if not jobs:
                failed_detail_lines.append("    (details unavailable)")
                continue
            for j in jobs:
                exc = j.get("exc_info", "")
                fn = j.get("func_name", "unknown")
                ended = j.get("ended_at", "?")
                failed_detail_lines.append(
                    f"    - {fn} (ended {ended}): {exc}"
                )
        failed_details_section = "\n".join(failed_detail_lines)
    else:
        failed_details_section = "  No failed job details."

    # Format pending job samples
    if queue_pending_sample:
        pending_sample_lines = []
        for qname, funcs in queue_pending_sample.items():
            pending_sample_lines.append(
                f"  [{qname}]: {', '.join(funcs)}"
            )
        pending_sample_section = "\n".join(pending_sample_lines)
    else:
        pending_sample_section = "  No pending job samples available."

    total_users = platform.get("total_users", 0)
    roles_str = _fmt_tiers(platform.get("users_by_role", {}))
    new_7d = platform.get("new_users_7d", 0)
    new_30d = platform.get("new_users_30d", 0)
    pending = queues.get("total_pending", 0)
    failed = queues.get("total_failed", 0)
    cand_tiers = _fmt_tiers(billing.get("candidates", {}))
    emp_tiers = _fmt_tiers(billing.get("employers", {}))
    rec_tiers = _fmt_tiers(billing.get("recruiters", {}))

    admin_block = f"""

---
ADMIN OPERATIONS CONTEXT — PRIMARY IDENTITY
IMPORTANT: This user is a PLATFORM ADMIN. When they ask about platform \
operations, queues, billing issues, user management, or "what needs attention", \
you MUST respond as the platform operations advisor using the admin page links \
and API actions below — NOT role-specific links. Only fall back to role-specific \
context (provided later) if the admin explicitly asks about their own personal \
recruiter/employer/candidate workflow.

You have access to live system data below and MUST give deeply \
actionable, specific advice — never vague suggestions.

ADMIN PAGE DIRECTORY (always link to these with markdown):
- [Queue Monitor]({frontend_url}/admin/support/queues) — view/retry failed jobs, monitor pending
- [Billing Diagnostics]({frontend_url}/admin/support/billing) — subscription status, past-due, overrides
- [User Lookup]({frontend_url}/admin/support/lookup) — search users, view profiles, usage
- [Trust Quarantine]({frontend_url}/admin/trust) — review quarantined candidates
- [Candidates]({frontend_url}/admin/candidates) — candidate management
- [Employers]({frontend_url}/admin/employers) — employer management
- [Recruiters]({frontend_url}/admin/recruiters) — recruiter management
- [Jobs]({frontend_url}/admin/jobs) — job listing management
- [Job Quality]({frontend_url}/admin/job-quality) — fraud scores, quality review

ADMIN API ACTION CATALOG (reference these when recommending fixes):
- POST /admin/retry-queue/{{queue_name}} — retry all failed jobs in a queue (use for transient errors)
- POST /admin/reparse/{{user_id}} — re-run resume parsing for a user (use when parse jobs failed)
- POST /admin/clear-daily-counters/{{user_id}} — reset daily rate limits (use when user hit limits incorrectly)
- POST /admin/tier-override — override a user's billing tier (use for billing mismatches)
- PUT /admin/trust/{{trust_id}}/set — resolve trust quarantine status
- POST /admin/jobs/{{job_id}}/reparse — reparse a specific job
- POST /admin/jobs/reparse-all — reparse all jobs
- POST /admin/jobs/{{job_id}}/fraud-override — override fraud score for a job
- POST /admin/embeddings/backfill — backfill missing embeddings

PLATFORM SNAPSHOT:
- Total users: {total_users}
- Users by role: {roles_str}
- New users (7d): {new_7d} | (30d): {new_30d}

QUEUE HEALTH:
- Total pending: {pending} | Total failed: {failed}
{queue_lines}

PENDING JOB SAMPLES (first 5 jobs per queue — shows what work is queued):
{pending_sample_section}

FAILED JOB ERROR DETAILS (from RQ — actual error messages):
{failed_details_section}

BILLING DISTRIBUTION:
- Candidates: {cand_tiers}
- Employers: {emp_tiers}
- Recruiters: {rec_tiers}

ACTIVE ALERTS:
{alert_lines}

RECENT FAILED JOB RUNS (from database — with error messages):
{failure_section}

MANDATORY RESPONSE RULES:
1. ALWAYS include markdown hyperlinks to the relevant admin page(s) from the directory above.
2. For queue issues: identify WHICH queue, examine the error messages above for root cause, \
categorize as transient (retry will fix), persistent (code/config bug), or data-related \
(bad input), and recommend the specific API action.
3. For billing issues: state exact counts from the data above, link to \
[Billing Diagnostics]({frontend_url}/admin/support/billing), and recommend specific \
override actions with the API endpoint.
4. ALWAYS propose a numbered multi-step remediation plan.
5. Reference exact counts, queue names, func_names, and error patterns from the data above.
6. NEVER give vague advice like "check your dashboard" or "look into it" — always \
be specific about what to do, where to do it, and why.
7. When asked "what needs attention", produce a severity-ranked list \
(errors > warnings > info) with impact assessment and linked action for each item.

PRIORITY FRAMEWORK:
- Sort issues by severity: errors > warnings > info
- Weigh by user impact: billing affects revenue, queue failures block user workflows, \
trust issues affect platform integrity
---"""

    admin_reminder = (
        "\n\n---\nREMINDER: You are responding as the PLATFORM ADMIN "
        "operations advisor. Use admin page links from the ADMIN PAGE "
        "DIRECTORY above (e.g. [Queue Monitor], [Billing Diagnostics]). "
        "Do NOT use role-specific links like /recruiter/ or /employer/.\n---"
    )
    return admin_block + "\n\n" + base_prompt + admin_reminder


def get_admin_suggested_actions(admin_ctx: dict) -> list[str]:
    """Generate 3-4 admin-focused quick-reply suggestions based on current state."""
    suggestions: list[str] = []

    past_due = admin_ctx.get("past_due_count", 0)
    quarantine = admin_ctx.get("quarantine_count", 0)
    queues = admin_ctx.get("queues", {})
    total_failed = queues.get("total_failed", 0)
    total_pending = queues.get("total_pending", 0)
    per_queue = queues.get("per_queue", {})

    # Failed jobs — name the worst queue
    if total_failed > 0:
        worst_queue = max(
            (
                (name, stats.get("failed", 0))
                for name, stats in per_queue.items()
                if stats.get("failed", 0) > 0
            ),
            key=lambda x: x[1],
            default=None,
        )
        if worst_queue:
            suggestions.append(
                f"Diagnose {worst_queue[1]} failed job(s) in the {worst_queue[0]} queue"
            )
        else:
            suggestions.append(f"Diagnose {total_failed} failed queue job(s)")

    # High pending count
    if total_pending > 50:
        suggestions.append(
            f"Why are {total_pending} jobs pending? Is the worker healthy?"
        )

    # Past-due subscriptions
    if past_due > 0:
        suggestions.append(
            f"Show me the {past_due} past-due subscription(s) and what to do"
        )

    # Trust quarantine
    if quarantine > 0:
        suggestions.append(
            f"Review {quarantine} quarantined candidate(s) — should I clear any?"
        )

    # Always include a general triage option
    if not suggestions:
        suggestions.append("What needs my attention right now?")

    # Fill remaining slots with general admin suggestions
    fallbacks = [
        "What needs my attention right now?",
        "How's platform usage today?",
        "Summarize new user growth",
        "Show me billing distribution",
    ]
    for fb in fallbacks:
        if len(suggestions) >= 4:
            break
        if fb not in suggestions:
            suggestions.append(fb)

    return suggestions[:4]


# ---------------------------------------------------------------------------
# Backward compatibility aliases
# ---------------------------------------------------------------------------


def gather_user_context(user: User, session: Session) -> dict:
    """Legacy alias — delegates to load_user_context."""
    return load_user_context(user.id, session)


def generate_response(
    message: str,
    history: list[dict],
    context: dict,
) -> str:
    """Legacy alias used by existing router."""
    system_prompt = build_system_prompt(context)
    llm_messages = []
    for item in history[-10:]:
        llm_messages.append({"role": item["role"], "content": item["content"]})
    llm_messages.append({"role": "user", "content": message})
    return _call_llm(system_prompt, llm_messages)


def generate_conversation_id() -> str:
    return str(uuid.uuid4())
