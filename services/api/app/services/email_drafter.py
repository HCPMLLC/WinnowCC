"""Application Email Drafter — generates professional intro emails for job applications.

Chain: OpenAI (primary) → Anthropic Claude (fallback) → static template (final).
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
You are a professional email writer. You draft concise, compelling job application \
emails. Return ONLY valid JSON with no markdown formatting or code fences."""


def _build_user_prompt(
    candidate_name: str,
    candidate_title: str,
    candidate_experience_years: int,
    top_skills: list[str],
    top_achievements: list[str],
    job_title: str,
    company: str,
    job_requirements: list[str],
    matched_skills: list[str],
) -> str:
    return f"""Write a professional job application email.

Candidate:
- Name: {candidate_name}
- Current/Recent Title: {candidate_title}
- Years of Experience: {candidate_experience_years}
- Top Skills: {", ".join(top_skills[:5])}
- Key Achievements: {"; ".join(top_achievements[:3])}

Job:
- Title: {job_title}
- Company: {company}
- Key Requirements: {", ".join(job_requirements[:5])}
- Candidate's Matching Skills: {", ".join(matched_skills[:5])}

Return JSON:
{{
    "subject": "Email subject line",
    "greeting": "Opening greeting",
    "body": "Email body - 2-3 short paragraphs",
    "closing": "Professional closing"
}}

Email Rules:
1. Subject: Include job title and imply experience (not just "Application")
2. Keep total length under 200 words
3. Paragraph 1: Express interest and 1 sentence on relevant background
4. Paragraph 2: 2-3 specific qualifications that match requirements
5. Paragraph 3: Call to action (interview request) and availability
6. Tone: Confident but not arrogant, professional but not stiff
7. DO NOT use cliches: "I am excited", "I believe I would be a great fit"
8. DO include specific numbers/achievements from their background
9. End with clear next step

Return ONLY valid JSON."""


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv(
        "EMAIL_DRAFTER_OPENAI_MODEL",
        os.getenv("LLM_PARSER_MODEL", "gpt-4o-mini"),
    )
    timeout = int(os.getenv("EMAIL_DRAFTER_TIMEOUT", "30"))

    client = OpenAI(api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=500,
    )
    return (response.choices[0].message.content or "").strip()


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv(
        "EMAIL_DRAFTER_ANTHROPIC_MODEL",
        os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
    )
    timeout = int(os.getenv("EMAIL_DRAFTER_TIMEOUT", "30"))

    client = Anthropic(api_key=api_key, timeout=timeout)
    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.4,
    )
    return (response.content[0].text or "").strip()


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    last_exc: Exception | None = None

    if _has_openai_key():
        try:
            logger.info("Email drafter: trying OpenAI")
            return _call_openai(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Email drafter OpenAI failed: %s", exc)

    if _has_anthropic_key():
        try:
            logger.info("Email drafter: trying Anthropic Claude")
            return _call_anthropic(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Email drafter Anthropic failed: %s", exc)

    raise last_exc or RuntimeError("No LLM API keys configured for email drafter")


# ---------------------------------------------------------------------------
# Core draft function
# ---------------------------------------------------------------------------


def draft_application_email(
    candidate_name: str,
    candidate_title: str,
    candidate_experience_years: int,
    top_skills: list[str],
    top_achievements: list[str],
    job_title: str,
    company: str,
    job_requirements: list[str],
    matched_skills: list[str],
) -> dict:
    """Draft a professional application email.

    Returns dict with subject, greeting, body, closing, full_email.
    """
    user_prompt = _build_user_prompt(
        candidate_name=candidate_name,
        candidate_title=candidate_title,
        candidate_experience_years=candidate_experience_years,
        top_skills=top_skills,
        top_achievements=top_achievements,
        job_title=job_title,
        company=company,
        job_requirements=job_requirements,
        matched_skills=matched_skills,
    )

    try:
        raw = _call_llm(_SYSTEM_PROMPT, user_prompt)
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].rstrip()

        result = json.loads(cleaned)

        result["full_email"] = (
            f"Subject: {result['subject']}\n\n"
            f"{result['greeting']}\n\n"
            f"{result['body']}\n\n"
            f"{result['closing']}\n"
            f"{candidate_name}"
        )
        return result

    except Exception as exc:
        logger.error("Email drafter LLM failed: %s", exc)
        return _generate_fallback_email(
            candidate_name, candidate_title, job_title, company, top_skills
        )


def _generate_fallback_email(
    name: str,
    title: str,
    job_title: str,
    company: str,
    skills: list[str],
) -> dict:
    """Fallback template-based email."""
    skills_str = ", ".join(skills[:3]) if skills else "relevant experience"

    subject = f"{job_title} Application - {name}"
    greeting = "Dear Hiring Manager,"
    body = (
        f"I am writing to apply for the {job_title} position at {company}.\n\n"
        f"With experience as a {title} and skills in {skills_str}, "
        "I am confident I can contribute to your team.\n\n"
        "I would welcome the opportunity to discuss how my background "
        "aligns with your needs. I am available for an interview at your convenience."
    )
    closing = "Best regards,"

    return {
        "subject": subject,
        "greeting": greeting,
        "body": body,
        "closing": closing,
        "full_email": (
            f"Subject: {subject}\n\n{greeting}\n\n{body}\n\n{closing}\n{name}"
        ),
    }


# ---------------------------------------------------------------------------
# High-level helper: generate from a match row
# ---------------------------------------------------------------------------


def generate_email_for_match(
    match_id: int,
    user_id: int,
    db: Session,
) -> dict:
    """Generate application email for a specific match."""
    from app.models.candidate_profile import CandidateProfile
    from app.models.job import Job
    from app.models.match import Match

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

    # Extract achievements from experience bullets (lines with numbers)
    achievements: list[str] = []
    for exp in experience[:3]:
        for bullet in exp.get("bullets", [])[:2]:
            if any(c.isdigit() for c in str(bullet)):
                achievements.append(str(bullet))

    # Rough experience years estimate
    exp_years = len(experience) * 2

    reasons = match.reasons or {}

    return draft_application_email(
        candidate_name=basics.get("name", ""),
        candidate_title=experience[0].get("title", "") if experience else "",
        candidate_experience_years=exp_years,
        top_skills=skills[:10],
        top_achievements=achievements[:3],
        job_title=job.title,
        company=job.company,
        job_requirements=reasons.get("job_requirements", [])[:5],
        matched_skills=reasons.get("matched_skills", []),
    )
