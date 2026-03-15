"""Profile Enhancement Suggestions — LLM-powered career-coach analysis.

After resume parsing, generates specific, actionable suggestions to strengthen
the candidate profile for better match scores.  Results are stored in the
``enhancement_suggestions`` key of the profile's ``profile_json`` JSONB column.

Cost: ~$0.02-0.04 per analysis (Sonnet).  One-time per profile version.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile

logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=3)
    return _client


def _extract_json(text: str) -> str:
    """Extract JSON from LLM responses (code fences, XML tags, preamble)."""
    text = text.strip()
    text = re.sub(r"<[\w-]+>.*?</[\w-]+>", "", text, flags=re.DOTALL).strip()
    m = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# Core worker job
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior career coach who reviews candidate profiles and gives \
specific, actionable improvement suggestions.  Your goal is to help \
candidates strengthen their profile so it scores higher in automated \
job-matching systems.

Rules:
- Be specific — reference exact sections and content from the profile.
- Give concrete "before → after" examples where possible.
- Focus on quantifiable impact, keywords, and clarity.
- Limit to the 5-8 most impactful suggestions.
- Assign each suggestion a priority: high, medium, or low.
- Categories: experience, skills, education, summary, preferences, formatting.

Respond ONLY with valid JSON matching this schema (no other text):
{
  "suggestions": [
    {
      "category": "experience|skills|education|summary|preferences|formatting",
      "section_ref": "which part of the profile this applies to",
      "priority": "high|medium|low",
      "current_issue": "what's weak or missing right now",
      "suggestion": "what to do about it",
      "example": "concrete before→after or addition example",
      "impact": "why this matters for match scores"
    }
  ],
  "overall_assessment": {
    "strengths": ["strength1", "strength2"],
    "biggest_opportunity": "the single highest-ROI change",
    "estimated_improvement": "rough percentage improvement in match quality"
  }
}
"""


def _build_user_prompt(profile_json: dict) -> str:
    """Build the user message from profile data."""
    sections = []

    basics = profile_json.get("basics") or {}
    if basics:
        sections.append(f"## Basic Info\n{json.dumps(basics, indent=2)}")

    experience = profile_json.get("experience") or []
    if experience:
        exp_json = json.dumps(experience, indent=2)
        n = len(experience)
        sections.append(f"## Experience ({n} entries)\n{exp_json}")

    education = profile_json.get("education") or []
    if education:
        edu_json = json.dumps(education, indent=2)
        n = len(education)
        sections.append(f"## Education ({n} entries)\n{edu_json}")

    skills = profile_json.get("skills") or []
    if skills:
        sections.append(f"## Skills\n{json.dumps(skills)}")

    preferences = profile_json.get("preferences") or {}
    if preferences:
        sections.append(f"## Preferences\n{json.dumps(preferences, indent=2)}")

    summary = basics.get("summary") or ""
    if summary:
        sections.append(f"## Summary\n{summary}")

    if not sections:
        return ""

    return (
        "Analyze this candidate profile and provide enhancement suggestions:\n\n"
        + "\n\n".join(sections)
    )


def _is_profile_empty(profile_json: dict) -> bool:
    """Return True if the profile has no meaningful content to analyze."""
    experience = profile_json.get("experience") or []
    skills = profile_json.get("skills") or []
    basics = profile_json.get("basics") or {}
    summary = basics.get("summary") or ""
    return not experience and not skills and not summary


def _set_enhancement_status(
    session: Session, user_id: int, version: int, data: dict
) -> None:
    """Write enhancement_suggestions into the profile_json of the given version."""
    stmt = (
        select(CandidateProfile)
        .where(
            CandidateProfile.user_id == user_id,
            CandidateProfile.version == version,
        )
        .limit(1)
    )
    profile = session.execute(stmt).scalar_one_or_none()
    if profile is None:
        logger.warning(
            "Enhancement: profile v%s not found for user %s", version, user_id
        )
        return

    pj = dict(profile.profile_json)
    pj["enhancement_suggestions"] = data
    profile.profile_json = pj
    session.commit()


def generate_enhancement_suggestions(user_id: int, version: int) -> None:
    """RQ worker job: generate LLM-powered enhancement suggestions.

    Writes results into ``profile_json.enhancement_suggestions`` on the
    specified profile version row.
    """
    session = None
    try:
        session = get_session_factory()()
        # Mark generating
        _set_enhancement_status(session, user_id, version, {
            "status": "generating",
            "suggestions": [],
            "overall_assessment": None,
            "generated_at": None,
        })

        # Load profile
        stmt = (
            select(CandidateProfile)
            .where(
                CandidateProfile.user_id == user_id,
                CandidateProfile.version == version,
            )
            .limit(1)
        )
        profile = session.execute(stmt).scalar_one_or_none()
        if profile is None:
            logger.warning(
                "Enhancement: profile not found user=%s v=%s",
                user_id,
                version,
            )
            return

        profile_json = profile.profile_json or {}

        # Skip LLM for empty profiles
        if _is_profile_empty(profile_json):
            _set_enhancement_status(session, user_id, version, {
                "status": "completed",
                "suggestions": [],
                "overall_assessment": {
                    "strengths": [],
                    "biggest_opportunity": (
                        "Add work experience, skills, and a "
                        "summary to get personalized suggestions."
                    ),
                    "estimated_improvement": "N/A",
                },
                "generated_at": datetime.now(UTC).isoformat(),
            })
            return

        user_msg = _build_user_prompt(profile_json)

        # Call LLM
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            temperature=0.3,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = _extract_json(response.content[0].text)
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try salvaging truncated JSON
            salvaged = raw_text.rstrip()
            open_braces = salvaged.count("{") - salvaged.count("}")
            open_brackets = salvaged.count("[") - salvaged.count("]")
            salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                result = json.loads(salvaged)
            except json.JSONDecodeError:
                logger.error(
                    "Enhancement: failed to parse LLM JSON user=%s",
                    user_id,
                )
                _set_enhancement_status(session, user_id, version, {
                    "status": "failed",
                    "suggestions": [],
                    "overall_assessment": None,
                    "generated_at": datetime.now(UTC).isoformat(),
                })
                return

        _set_enhancement_status(session, user_id, version, {
            "status": "completed",
            "suggestions": result.get("suggestions", []),
            "overall_assessment": result.get("overall_assessment"),
            "generated_at": datetime.now(UTC).isoformat(),
        })
        logger.info("Enhancement: completed for user=%s v=%s", user_id, version)

    except Exception:
        logger.exception("Enhancement: error for user=%s v=%s", user_id, version)
        if session:
            try:
                _set_enhancement_status(session, user_id, version, {
                    "status": "failed",
                    "suggestions": [],
                    "overall_assessment": None,
                    "generated_at": datetime.now(UTC).isoformat(),
                })
            except Exception:
                session.rollback()
    finally:
        if session:
            session.close()
