"""Interview Prep Coach — generates personalized interview preparation."""

import json
import logging
import os
import re
from datetime import UTC, datetime

import anthropic
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.interview_prep import InterviewPrep
from app.models.job import Job
from app.models.match import Match

logger = logging.getLogger(__name__)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

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
You are a senior interview coach. Given a candidate's profile and a job posting, \
generate comprehensive interview preparation materials.

Return valid JSON with these exact keys:

{
  "likely_questions": [
    {
      "category": "Behavioral|Technical|Situational|Culture Fit",
      "question": "The interview question",
      "star_answer": {
        "situation": "Set the scene",
        "task": "What was your responsibility",
        "action": "What you did (specific steps)",
        "result": "Measurable outcome"
      },
      "source": "Brief note on which resume experience supports this answer"
    }
  ],
  "company_insights": {
    "culture_signals": ["Signal derived from job posting or company info"],
    "values": ["Company value or priority inferred from the posting"],
    "concerns": ["Potential red flags or things to ask about"]
  },
  "gap_strategies": [
    {
      "skill": "The skill or requirement you're missing",
      "severity": "critical|moderate|minor",
      "strategy": "How to address this gap in the interview"
    }
  ],
  "closing_questions": [
    "Smart question to ask the interviewer"
  ]
}

Rules:
- Generate 6-10 likely questions spanning all categories
- STAR answers MUST use real experiences from the candidate's profile — never fabricate
- If no direct experience exists, note that honestly in the source field
- Gap strategies should be actionable and specific
- Closing questions should demonstrate research and genuine interest
- Keep all text concise and direct
"""


def generate_interview_prep_job(interview_prep_id: int) -> None:
    """RQ worker job: generate interview prep content for a given InterviewPrep row."""
    session = None
    try:
        session = get_session_factory()()
        prep = session.get(InterviewPrep, interview_prep_id)
        if prep is None:
            logger.error("InterviewPrep %d not found", interview_prep_id)
            return

        prep.status = "processing"
        session.flush()

        # Load match, job, and profile
        match = session.get(Match, prep.match_id)
        if match is None:
            prep.status = "failed"
            prep.error_message = "Match not found"
            session.commit()
            return

        job = session.get(Job, prep.job_id)
        if job is None:
            prep.status = "failed"
            prep.error_message = "Job not found"
            session.commit()
            return

        profile = session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == prep.user_id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        ).scalar_one_or_none()

        profile_data = profile.profile_json if profile else {}
        match_reasons = match.reasons or {}

        # Build the user message
        user_msg = (
            f"## Candidate Profile\n{json.dumps(profile_data, default=str)}\n\n"
            f"## Job Details\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location or 'Not specified'}\n"
            f"Description: {(job.description_text or '')[:3000]}\n\n"
            f"## Match Analysis\n"
            f"Match Score: {match.match_score}\n"
            f"Matched Skills: {json.dumps(match_reasons.get('matched_skills', []))}\n"
            f"Missing Skills: {json.dumps(match_reasons.get('missing_skills', []))}\n"
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
            prep_json = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to salvage truncated JSON
            salvaged = raw_text.rstrip()
            open_braces = salvaged.count("{") - salvaged.count("}")
            open_brackets = salvaged.count("[") - salvaged.count("]")
            salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
            try:
                prep_json = json.loads(salvaged)
            except json.JSONDecodeError:
                prep.status = "failed"
                prep.error_message = "Failed to parse LLM response"
                session.commit()
                return

        prep.prep_content = prep_json
        prep.status = "completed"
        prep.completed_at = datetime.now(UTC)
        session.commit()
        logger.info("Interview prep %d completed for match %d", prep.id, prep.match_id)

    except Exception:
        logger.exception(
            "Interview prep generation failed for id=%d", interview_prep_id
        )
        if session:
            try:
                prep = session.get(InterviewPrep, interview_prep_id)
                if prep:
                    prep.status = "failed"
                    prep.error_message = "Internal error during generation"
                    session.commit()
            except Exception:
                session.rollback()
    finally:
        if session:
            session.close()
