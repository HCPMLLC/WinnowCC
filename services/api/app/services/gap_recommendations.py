"""Gap Closure Recommendations — generates personalized learning plans for missing skills."""

import json
import logging
import os
import re
from datetime import UTC, datetime

import anthropic
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.gap_recommendation import GapRecommendation
from app.models.job import Job
from app.models.match import Match

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=3)
    return _client


def _extract_json(text: str) -> str:
    """Extract JSON from LLM responses."""
    text = text.strip()
    text = re.sub(r"<[\w-]+>.*?</[\w-]+>", "", text, flags=re.DOTALL).strip()
    m = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


_SYSTEM_PROMPT = """\
You are an expert career development advisor. Given a candidate's profile and a job \
posting with identified skill gaps, generate actionable learning recommendations to \
close each gap.

Return valid JSON with these exact keys:

{
  "gaps": [
    {
      "skill": "The missing skill name",
      "priority": "critical|high|medium|low",
      "time_estimate": "Estimated time to reach competency (e.g. '2-4 weeks')",
      "resources": [
        {
          "type": "course|certification|tutorial|book|project",
          "name": "Resource name",
          "provider": "Platform or provider name",
          "url_hint": "Search term to find this resource",
          "estimated_hours": 10,
          "cost": "free|$XX|varies"
        }
      ],
      "quick_win": "One specific thing the candidate can do THIS WEEK to start closing this gap",
      "portfolio_project": "A concrete project idea that demonstrates this skill"
    }
  ],
  "overall_plan": {
    "recommended_order": ["skill1", "skill2"],
    "total_time_estimate": "Overall time estimate",
    "strategy": "Brief paragraph on the recommended learning approach"
  }
}

Rules:
- Prioritize gaps based on how critical they are for the target role
- Resources should be real, well-known platforms (Coursera, Udemy, LinkedIn Learning, \
freeCodeCamp, official docs, etc.)
- Quick wins should be achievable in under a week
- Portfolio projects should be impressive enough to discuss in an interview
- Time estimates should be realistic for someone learning alongside a full-time job
- Consider the candidate's existing skills when recommending resources (skip basics if \
they have related experience)
- Provide 3 resources per gap
- Keep all text concise and actionable
"""


def generate_gap_recommendations_job(gap_rec_id: int) -> None:
    """RQ worker job: generate gap closure recommendations for a GapRecommendation row."""
    session = get_session_factory()()
    try:
        gap_rec = session.get(GapRecommendation, gap_rec_id)
        if gap_rec is None:
            logger.error("GapRecommendation %d not found", gap_rec_id)
            return

        gap_rec.status = "processing"
        session.flush()

        match = session.get(Match, gap_rec.match_id)
        if match is None:
            gap_rec.status = "failed"
            gap_rec.error_message = "Match not found"
            session.commit()
            return

        job = session.get(Job, gap_rec.job_id)
        if job is None:
            gap_rec.status = "failed"
            gap_rec.error_message = "Job not found"
            session.commit()
            return

        profile = session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == gap_rec.user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        ).scalar_one_or_none()

        profile_data = profile.profile_json if profile else {}
        match_reasons = match.reasons or {}

        missing_skills = match_reasons.get("missing_skills", [])
        matched_skills = match_reasons.get("matched_skills", [])

        if not missing_skills:
            gap_rec.recommendations = {"gaps": [], "overall_plan": None}
            gap_rec.status = "completed"
            gap_rec.completed_at = datetime.now(UTC)
            session.commit()
            return

        user_msg = (
            f"## Candidate Profile\n{json.dumps(profile_data, default=str)}\n\n"
            f"## Job Details\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location or 'Not specified'}\n"
            f"Description: {(job.description_text or '')[:3000]}\n\n"
            f"## Skill Analysis\n"
            f"Matched Skills: {json.dumps(matched_skills)}\n"
            f"Missing Skills (GAPS TO ADDRESS): {json.dumps(missing_skills)}\n"
        )

        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw_text = _extract_json(response.content[0].text)
        try:
            rec_json = json.loads(raw_text)
        except json.JSONDecodeError:
            salvaged = raw_text.rstrip()
            open_braces = salvaged.count("{") - salvaged.count("}")
            open_brackets = salvaged.count("[") - salvaged.count("]")
            salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                rec_json = json.loads(salvaged)
            except json.JSONDecodeError:
                gap_rec.status = "failed"
                gap_rec.error_message = "Failed to parse LLM response"
                session.commit()
                return

        gap_rec.recommendations = rec_json
        gap_rec.status = "completed"
        gap_rec.completed_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "Gap recommendations %d completed for match %d", gap_rec.id, gap_rec.match_id
        )

    except Exception:
        logger.exception(
            "Gap recommendations generation failed for id=%d", gap_rec_id
        )
        try:
            gap_rec = session.get(GapRecommendation, gap_rec_id)
            if gap_rec:
                gap_rec.status = "failed"
                gap_rec.error_message = "Internal error during generation"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


def filter_for_free_tier(recommendations: dict) -> dict:
    """Strip content for free-tier users: max 2 resources per gap, no overall_plan."""
    filtered = dict(recommendations)
    gaps = filtered.get("gaps", [])
    for gap in gaps:
        if "resources" in gap:
            gap["resources"] = gap["resources"][:2]
        gap.pop("portfolio_project", None)
    filtered["overall_plan"] = None
    # Remove priority ordering
    for gap in gaps:
        gap.pop("priority", None)
    filtered["gaps"] = gaps
    return filtered
