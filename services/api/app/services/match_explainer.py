"""Match Explanation Generator.

Generates human-readable, one-sentence explanations for why a job was matched
to a candidate. Uses Claude Haiku for cost-effective natural language generation.
"""

import logging
import os

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def generate_match_explanation(
    match: Match,
    job: Job,
    profile: CandidateProfile,
) -> str:
    """Generate a single-sentence explanation for why this job was matched."""
    reasons = match.reasons or {}
    matched_skills = reasons.get("matched_skills", [])

    profile_json = profile.profile_json or {}
    preferences = profile_json.get("preferences", {})
    target_roles = preferences.get("target_titles", [])
    work_mode = preferences.get("work_mode", "")
    if not work_mode:
        work_mode = "remote" if preferences.get("remote_ok") else ""

    context = {
        "job_title": job.title,
        "company": job.company,
        "location": job.location,
        "remote": job.remote_flag,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "matched_skills": matched_skills[:5],
        "match_score": match.match_score,
        "candidate_target_roles": target_roles[:3],
        "candidate_work_mode": work_mode,
    }

    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return _generate_fallback_explanation(context)

    skills_str = ", ".join(context["matched_skills"]) or "general experience"
    roles_str = ", ".join(context["candidate_target_roles"]) or "not specified"
    remote_tag = "(Remote)" if context["remote"] else ""
    sal_min = context["salary_min"] or "?"
    sal_max = context["salary_max"] or "?"
    wm = context["candidate_work_mode"] or "flexible"

    prompt = (
        "Generate a single, friendly sentence explaining "
        "why this job was matched to this candidate.\n\n"
        f"Job: {context['job_title']} at {context['company']}\n"
        f"Location: {context['location']} {remote_tag}\n"
        f"Salary: ${sal_min}k - ${sal_max}k\n\n"
        f"Candidate's matched skills: {skills_str}\n"
        f"Candidate's target roles: {roles_str}\n"
        f"Candidate's preferred work mode: {wm}\n"
        f"Match score: {context['match_score']}%\n\n"
        "Rules:\n"
        "1. Write ONE sentence only (max 25 words)\n"
        '2. Start with "Matched because..." or '
        '"Great fit because..."\n'
        "3. Highlight the TOP 1-2 reasons "
        "(skills, location, remote, salary, role alignment)\n"
        "4. Be specific and personal "
        "(use actual skill names, not generic phrases)\n"
        "5. Sound encouraging, not robotic\n"
        "6. Do NOT mention the score number\n\n"
        "Examples of good explanations:\n"
        '- "Matched because of your Python and AWS experience, '
        "plus this role offers the remote flexibility "
        'you prefer."\n'
        '- "Great fit because your project management background '
        "aligns with this PM role at a fintech company "
        "you'd enjoy.\"\n"
        '- "Matched because your React expertise and '
        "San Antonio location preference align perfectly "
        'with this opportunity."\n\n'
        "Now generate the explanation:"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        explanation = response.content[0].text.strip().strip('"').strip("'")

        if len(explanation) > 200:
            explanation = explanation[:197] + "..."

        return explanation

    except Exception:
        logger.exception("LLM explanation generation failed, using fallback")
        return _generate_fallback_explanation(context)


def _generate_fallback_explanation(context: dict) -> str:
    """Generate a simple fallback explanation without LLM."""
    parts = []

    if context["matched_skills"]:
        skills_str = ", ".join(context["matched_skills"][:2])
        parts.append(f"your {skills_str} experience")

    if context["remote"] and context["candidate_work_mode"] in ("remote", "hybrid"):
        parts.append("remote work option")

    if context["candidate_target_roles"]:
        for role in context["candidate_target_roles"]:
            if role.lower() in context["job_title"].lower():
                parts.append(f"alignment with your {role} goals")
                break

    if not parts:
        parts.append("your overall profile fit")

    return f"Matched because of {' and '.join(parts[:2])}."


def generate_explanations_batch(
    match_ids: list[int],
    db: Session,
) -> dict[int, str]:
    """Generate explanations for multiple matches efficiently.

    Uses fallback for low-score matches to save API costs.
    """
    results: dict[int, str] = {}

    matches = db.execute(select(Match).where(Match.id.in_(match_ids))).scalars().all()

    for match in matches:
        job = db.execute(select(Job).where(Job.id == match.job_id)).scalars().first()
        profile = (
            db.execute(
                select(CandidateProfile)
                .where(CandidateProfile.user_id == match.user_id)
                .order_by(CandidateProfile.version.desc())
            )
            .scalars()
            .first()
        )

        if not job or not profile:
            results[match.id] = "Matched based on your profile."
            continue

        if match.match_score < 40:
            reasons = match.reasons or {}
            context = {
                "job_title": job.title,
                "company": job.company,
                "location": job.location,
                "remote": job.remote_flag,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "matched_skills": reasons.get("matched_skills", []),
                "match_score": match.match_score,
                "candidate_target_roles": (
                    (profile.profile_json or {})
                    .get("preferences", {})
                    .get("target_titles", [])
                ),
                "candidate_work_mode": (
                    (profile.profile_json or {})
                    .get("preferences", {})
                    .get("work_mode", "")
                ),
            }
            results[match.id] = _generate_fallback_explanation(context)
        else:
            results[match.id] = generate_match_explanation(match, job, profile)

        match.match_explanation = results[match.id]

    db.commit()
    return results


def backfill_match_explanations_job(batch_size: int = 100) -> None:
    """Backfill explanations for existing matches that don't have them.

    Enqueue via: ``queue.enqueue(backfill_match_explanations_job, 100)``
    """
    from app.db.session import get_session_factory

    db = get_session_factory()()
    try:
        matches = (
            db.execute(
                select(Match)
                .where(
                    Match.match_explanation.is_(None),
                    Match.match_score >= 40,
                )
                .limit(batch_size)
            )
            .scalars()
            .all()
        )

        if not matches:
            logger.info("No matches to backfill.")
            return

        match_ids = [m.id for m in matches]
        generate_explanations_batch(match_ids, db)
        logger.info("Generated explanations for %d matches.", len(match_ids))
    finally:
        db.close()
