"""Salary Negotiation Coach — analyzes job offers and provides negotiation strategies.

Chain: OpenAI (primary) → Anthropic Claude (fallback) → static analysis (final).
Premium feature for Pro tier candidates.
"""

from __future__ import annotations

import json
import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert salary negotiation coach. Analyze job offers and provide \
actionable negotiation guidance. Return ONLY valid JSON with no markdown \
formatting or code fences."""


def _build_user_prompt(
    offer_salary: int,
    offer_bonus: int | None,
    offer_equity: str | None,
    job_title: str,
    company: str,
    job_salary_min: int | None,
    job_salary_max: int | None,
    candidate_experience_years: int,
    candidate_current_salary: int | None,
    candidate_location: str,
    candidate_skills: list[str],
    matched_skills: list[str],
) -> str:
    bonus_str = f"${offer_bonus:,}" if offer_bonus else "Not specified"
    cur_sal = (
        f"${candidate_current_salary:,}"
        if candidate_current_salary
        else "Not disclosed"
    )
    return f"""Analyze this job offer and provide actionable negotiation guidance.

## Offer Details
- Job: {job_title} at {company}
- Offered Base Salary: ${offer_salary:,}
- Bonus: {bonus_str}
- Equity: {offer_equity or 'Not specified'}
- Posted Salary Range: ${job_salary_min or '?'}k - ${job_salary_max or '?'}k

## Candidate Profile
- Years of Experience: {candidate_experience_years}
- Current/Last Salary: {cur_sal}
- Location: {candidate_location}
- Key Skills: {', '.join(candidate_skills[:8])}
- Skills Matching This Role: {', '.join(matched_skills[:5])}

## Your Analysis

Return JSON:
{{
    "offer_assessment": {{
        "overall": "below_market|at_market|above_market",
        "salary_position": "Analysis of where this offer falls",
        "total_comp_analysis": "Full compensation picture"
    }},
    "negotiation_strategy": {{
        "approach": "standard_counter|strong_counter|accept_with_perks|accept",
        "reasoning": "Why this strategy",
        "risk_level": "low|medium|high"
    }},
    "counter_offer": {{
        "target_salary": number,
        "minimum_acceptable": number,
        "script": "Exact words to say/write",
        "justification_points": ["Point 1", "Point 2", "Point 3"]
    }},
    "alternative_asks": [
        {{
            "item": "What to ask for",
            "suggested_amount": "Specific amount",
            "script": "How to ask"
        }}
    ],
    "red_flags": ["Concern 1 if any"],
    "positive_signals": ["Good sign 1"],
    "timeline_advice": "How to handle timing"
}}

Rules:
1. Be realistic - don't suggest unreasonable counters
2. Consider the candidate's leverage (skills match, experience, market)
3. Counter target should be 10-20% above offer unless offer is already high
4. Always include alternative asks (bonus, PTO, remote, start date)
5. Scripts should be professional and confident, not aggressive
6. Include specific numbers, not ranges
7. If offer is already strong, say so - don't encourage unnecessary negotiation
8. Consider location-based salary adjustments

Return ONLY valid JSON."""


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv(
        "SALARY_COACH_OPENAI_MODEL",
        os.getenv("LLM_PARSER_MODEL", "gpt-4o-mini"),
    )
    timeout = int(os.getenv("SALARY_COACH_TIMEOUT", "30"))

    client = OpenAI(api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1500,
    )
    return (response.choices[0].message.content or "").strip()


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv(
        "SALARY_COACH_ANTHROPIC_MODEL",
        os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
    )
    timeout = int(os.getenv("SALARY_COACH_TIMEOUT", "30"))

    client = Anthropic(api_key=api_key, timeout=timeout, max_retries=3)
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.4,
    )
    return (response.content[0].text or "").strip()


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    last_exc: Exception | None = None

    if _has_openai_key():
        try:
            logger.info("Salary coach: trying OpenAI")
            return _call_openai(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Salary coach OpenAI failed: %s", exc)

    if _has_anthropic_key():
        try:
            logger.info("Salary coach: trying Anthropic Claude")
            return _call_anthropic(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Salary coach Anthropic failed: %s", exc)

    raise last_exc or RuntimeError("No LLM API keys configured for salary coach")


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------


def analyze_offer(
    offer_salary: int,
    offer_bonus: int | None,
    offer_equity: str | None,
    job_title: str,
    company: str,
    job_salary_min: int | None,
    job_salary_max: int | None,
    candidate_experience_years: int,
    candidate_current_salary: int | None,
    candidate_location: str,
    candidate_skills: list[str],
    matched_skills: list[str],
) -> dict:
    """Analyze a job offer and provide negotiation guidance.

    Returns dict with offer_assessment, negotiation_strategy, counter_offer,
    alternative_asks, red_flags, positive_signals, timeline_advice.
    """
    user_prompt = _build_user_prompt(
        offer_salary=offer_salary,
        offer_bonus=offer_bonus,
        offer_equity=offer_equity,
        job_title=job_title,
        company=company,
        job_salary_min=job_salary_min,
        job_salary_max=job_salary_max,
        candidate_experience_years=candidate_experience_years,
        candidate_current_salary=candidate_current_salary,
        candidate_location=candidate_location,
        candidate_skills=candidate_skills,
        matched_skills=matched_skills,
    )

    try:
        raw = _call_llm(_SYSTEM_PROMPT, user_prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].rstrip()

        return json.loads(cleaned)

    except Exception as exc:
        logger.error("Salary coach LLM failed: %s", exc)
        return _generate_fallback_analysis(
            offer_salary, job_salary_min, job_salary_max, candidate_experience_years
        )


def _generate_fallback_analysis(
    offer: int,
    job_min: int | None,
    job_max: int | None,
    experience: int,
) -> dict:
    """Fallback analysis without LLM."""

    if job_max and offer >= job_max * 0.9:
        overall = "at_market"
        approach = "accept_with_perks"
    elif job_min and offer <= job_min * 1.1:
        overall = "below_market"
        approach = "strong_counter"
    else:
        overall = "at_market"
        approach = "standard_counter"

    target = int(offer * 1.15)
    minimum = int(offer * 1.07)

    return {
        "offer_assessment": {
            "overall": overall,
            "salary_position": (
                "Based on the posted range, this offer "
                "appears reasonable."
            ),
            "total_comp_analysis": (
                "Consider the full package including benefits."
            ),
        },
        "negotiation_strategy": {
            "approach": approach,
            "reasoning": (
                "Standard negotiation is expected and "
                "won't jeopardize the offer."
            ),
            "risk_level": "low",
        },
        "counter_offer": {
            "target_salary": target,
            "minimum_acceptable": minimum,
            "script": (
                f"Thank you for the offer. I'm excited about the opportunity. "
                f"Based on my experience and the market, I was hoping for a base "
                f"salary closer to ${target:,}. Is there flexibility in the "
                f"compensation?"
            ),
            "justification_points": [
                f"My {experience} years of experience",
                "Strong skills match for the role requirements",
                "Market rates for similar positions",
            ],
        },
        "alternative_asks": [
            {
                "item": "Signing bonus",
                "suggested_amount": "$5,000-10,000",
                "script": (
                    "If base salary flexibility is limited, "
                    "would a signing bonus be possible?"
                ),
            },
            {
                "item": "Additional PTO",
                "suggested_amount": "5 extra days",
                "script": "I value work-life balance. Could we discuss additional PTO?",
            },
        ],
        "red_flags": [],
        "positive_signals": ["You received an offer - they want you!"],
        "timeline_advice": "Ask for 3-5 business days to review the full offer.",
    }


# ---------------------------------------------------------------------------
# High-level helper: generate coaching from a match row
# ---------------------------------------------------------------------------


def get_salary_coaching(
    match_id: int,
    offer_details: dict,
    user_id: int,
    db: Session,
) -> dict:
    """Get salary negotiation coaching for a specific offer.

    Requires Pro tier subscription.
    """
    from app.models.candidate import Candidate
    from app.models.candidate_profile import CandidateProfile
    from app.models.job import Job
    from app.models.match import Match
    from app.services.billing import check_feature_access, get_plan_tier

    candidate = db.execute(
        select(Candidate).where(Candidate.user_id == user_id)
    ).scalar_one_or_none()
    tier = get_plan_tier(candidate)

    if not check_feature_access(tier, "salary_negotiation"):
        return {
            "error": "upgrade_required",
            "message": (
                "Salary negotiation coaching is a Pro feature. "
                "Upgrade to unlock personalized negotiation strategies."
            ),
        }

    match = db.execute(
        select(Match).where(Match.id == match_id, Match.user_id == user_id)
    ).scalar_one_or_none()

    if not match:
        return {"error": "Match not found"}

    job = db.execute(select(Job).where(Job.id == match.job_id)).scalar_one_or_none()
    profile = (
        db.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.version.desc())
        )
        .scalars()
        .first()
    )

    if not job or not profile:
        return {"error": "Missing job or profile data"}

    profile_json = profile.profile_json or {}
    basics = profile_json.get("basics", {})
    experience = profile_json.get("experience", [])
    skills = profile_json.get("skills", [])
    preferences = profile_json.get("preferences", {})

    reasons = match.reasons or {}

    return analyze_offer(
        offer_salary=offer_details.get("salary", 0),
        offer_bonus=offer_details.get("bonus"),
        offer_equity=offer_details.get("equity"),
        job_title=job.title,
        company=job.company,
        job_salary_min=job.salary_min,
        job_salary_max=job.salary_max,
        candidate_experience_years=len(experience) * 2,
        candidate_current_salary=preferences.get("salary_current"),
        candidate_location=basics.get("location", ""),
        candidate_skills=skills[:15],
        matched_skills=reasons.get("matched_skills", []),
    )
