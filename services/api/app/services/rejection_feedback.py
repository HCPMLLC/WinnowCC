"""Rejection Feedback Interpreter — AI-powered analysis of job rejections."""

import json
import logging
import os
import re
from datetime import UTC, datetime

import anthropic
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.rejection_feedback import RejectionFeedback

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
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
You are a compassionate and insightful career coach. A candidate has been rejected \
from a job application. Analyze the situation and provide constructive, actionable \
feedback that helps them grow and stay motivated.

If a rejection email is provided, interpret what it really means (read between the \
lines). If no rejection email is provided, give general analysis based on the \
candidate's profile vs the job requirements.

Return valid JSON with these exact keys:

{
  "interpretation": "A 2-3 sentence interpretation of what this rejection likely means",
  "feedback_type": "generic|skills_gap|experience|culture_fit|competition",
  "strengths": ["3-5 things the candidate likely did well or has going for them"],
  "likely_causes": [
    {
      "factor": "Brief description of the likely cause",
      "severity": "high|medium|low",
      "fixable": true,
      "how_to_fix": "Specific actionable advice to address this"
    }
  ],
  "next_steps": [
    {
      "action": "Specific action the candidate should take",
      "priority": "high|medium|low",
      "timeframe": "immediate|this_week|this_month"
    }
  ],
  "encouragement": "A warm, genuine 2-3 sentence resilience message",
  "similar_roles_to_consider": ["3-5 job titles that might be a better fit"]
}

Rules:
- Be honest but kind — no toxic positivity, but always constructive
- Likely causes should be specific to this candidate/job pairing, not generic
- Next steps should be concrete and actionable (not "keep trying")
- Strengths should be genuine observations from their profile
- Similar roles should be realistic given the candidate's background
- Keep encouragement genuine and personalized, not generic platitudes
- Provide 2-4 likely causes and 3-5 next steps
- If there's a rejection email, reference specific language from it
"""


def generate_rejection_feedback_job(feedback_id: int) -> None:
    """RQ worker job: generate rejection feedback analysis."""
    session = get_session_factory()()
    try:
        feedback = session.get(RejectionFeedback, feedback_id)
        if feedback is None:
            logger.error("RejectionFeedback %d not found", feedback_id)
            return

        feedback.status = "processing"
        session.flush()

        match = session.get(Match, feedback.match_id)
        if match is None:
            feedback.status = "failed"
            feedback.error_message = "Match not found"
            session.commit()
            return

        job = session.get(Job, feedback.job_id)
        if job is None:
            feedback.status = "failed"
            feedback.error_message = "Job not found"
            session.commit()
            return

        profile = session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == feedback.user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        ).scalar_one_or_none()

        profile_data = profile.profile_json if profile else {}
        match_reasons = match.reasons or {}

        missing_skills = match_reasons.get("missing_skills", [])
        matched_skills = match_reasons.get("matched_skills", [])

        user_msg = (
            f"## Candidate Profile\n{json.dumps(profile_data, default=str)}\n\n"
            f"## Job Details\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location or 'Not specified'}\n"
            f"Description: {(job.description_text or '')[:3000]}\n\n"
            f"## Match Analysis\n"
            f"Match Score: {match.score}\n"
            f"Matched Skills: {json.dumps(matched_skills)}\n"
            f"Missing Skills: {json.dumps(missing_skills)}\n"
        )

        if feedback.rejection_email:
            user_msg += (
                f"\n## Rejection Email Received\n"
                f"{feedback.rejection_email[:2000]}\n"
            )
        else:
            user_msg += (
                "\n## Note\nNo rejection email was provided. "
                "Provide general analysis based on profile vs job fit.\n"
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
            analysis_json = json.loads(raw_text)
        except json.JSONDecodeError:
            salvaged = raw_text.rstrip()
            open_braces = salvaged.count("{") - salvaged.count("}")
            open_brackets = salvaged.count("[") - salvaged.count("]")
            salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                analysis_json = json.loads(salvaged)
            except json.JSONDecodeError:
                feedback.status = "failed"
                feedback.error_message = "Failed to parse LLM response"
                session.commit()
                return

        feedback.analysis = analysis_json
        feedback.status = "completed"
        feedback.completed_at = datetime.now(UTC)
        session.commit()
        logger.info(
            "Rejection feedback %d completed for match %d",
            feedback.id,
            feedback.match_id,
        )

    except Exception:
        logger.exception(
            "Rejection feedback generation failed for id=%d", feedback_id
        )
        try:
            feedback = session.get(RejectionFeedback, feedback_id)
            if feedback:
                feedback.status = "failed"
                feedback.error_message = "Internal error during generation"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()


def filter_for_free_tier(analysis: dict) -> dict:
    """Strip content for free-tier users: no how_to_fix, no similar roles."""
    filtered = dict(analysis)
    causes = filtered.get("likely_causes", [])
    for cause in causes:
        cause.pop("how_to_fix", None)
    filtered["likely_causes"] = causes
    filtered.pop("similar_roles_to_consider", None)
    return filtered
