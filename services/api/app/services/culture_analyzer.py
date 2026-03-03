"""Company Culture Summarizer — AI-generated culture insights from job postings."""

import hashlib
import json
import logging
import os
import re

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail

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
You are a workplace culture analyst. Given a job posting, extract company culture \
signals to help candidates decide if this workplace is a good fit for them.

Analyze the job description's tone, language, benefits, requirements, and implicit \
signals about the company's work environment.

Return valid JSON with these exact keys:

{
  "summary": "A 2-3 sentence overview of what working here is likely like",
  "values": ["3-5 core company values inferred from the posting"],
  "work_style": "collaborative|independent|hybrid|structured|flexible",
  "pace": "fast-paced|steady|relaxed|intense|balanced",
  "remote_culture": "fully_remote|remote_friendly|hybrid|in_office|unclear",
  "growth_focus": "high|moderate|low|unclear",
  "signals": {
    "positive": ["3-5 green flags about working here"],
    "watch_for": ["1-3 things candidates should ask about or be aware of"]
  }
}

Rules:
- Base analysis ONLY on what the job posting actually says or strongly implies
- Be balanced — identify genuine positives but also flag potential concerns
- "watch_for" items should not be alarming, just things worth clarifying
- If a signal is unclear, say so rather than guessing
- Keep the summary conversational and helpful, not corporate-speak
- Values should be inferred from language patterns, not just listed perks
"""


def analyze_company_culture(
    company: str, job_description: str, job_title: str
) -> dict:
    """Call LLM to analyze company culture from a job posting."""
    user_msg = (
        f"## Company: {company}\n"
        f"## Job Title: {job_title}\n\n"
        f"## Job Description\n{job_description[:4000]}\n"
    )

    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw_text = _extract_json(response.content[0].text)
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        salvaged = raw_text.rstrip()
        open_braces = salvaged.count("{") - salvaged.count("}")
        open_brackets = salvaged.count("[") - salvaged.count("]")
        salvaged += "]" * max(0, open_brackets) + "}" * max(0, open_braces)
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            logger.warning("Failed to parse culture LLM response")
            return _generate_fallback_culture(company, job_description)


def _generate_fallback_culture(company: str, description: str) -> dict:
    """Deterministic fallback when LLM is unavailable."""
    desc_lower = description.lower()

    # Infer work_style
    collab = ["collaborative", "team-oriented", "cross-functional"]
    solo = ["self-starter", "autonomous", "independently"]
    if any(w in desc_lower for w in collab):
        work_style = "collaborative"
    elif any(w in desc_lower for w in solo):
        work_style = "independent"
    else:
        work_style = "hybrid"

    # Infer pace
    fast = ["fast-paced", "rapidly", "high-growth", "startup"]
    slow = ["stable", "established", "steady"]
    if any(w in desc_lower for w in fast):
        pace = "fast-paced"
    elif any(w in desc_lower for w in slow):
        pace = "steady"
    else:
        pace = "balanced"

    # Infer remote culture
    full_remote = ["fully remote", "100% remote", "work from anywhere"]
    part_remote = ["remote-friendly", "remote option", "work from home"]
    if any(w in desc_lower for w in full_remote):
        remote_culture = "fully_remote"
    elif any(w in desc_lower for w in part_remote):
        remote_culture = "remote_friendly"
    elif any(w in desc_lower for w in ["hybrid", "flexible location"]):
        remote_culture = "hybrid"
    elif any(w in desc_lower for w in ["on-site", "in-office"]):
        remote_culture = "in_office"
    else:
        remote_culture = "unclear"

    # Use a hash for deterministic variety in signals
    h = int(hashlib.md5(f"{company}{description[:200]}".encode()).hexdigest()[:8], 16)

    positive_pool = [
        "Job description is detailed and transparent",
        "Company describes a clear role scope",
        "Standard benefits appear to be offered",
    ]
    watch_pool = [
        "Limited culture details in posting — worth asking about team dynamics",
        "Consider asking about work-life balance expectations",
    ]

    return {
        "summary": (
            f"Based on the job posting, {company} appears to offer "
            f"a {pace}, {work_style} work environment. Limited "
            f"culture signals were available in the posting "
            f"— consider researching on Glassdoor or in interviews."
        ),
        "values": ["Professionalism", "Delivery", "Teamwork"],
        "work_style": work_style,
        "pace": pace,
        "remote_culture": remote_culture,
        "growth_focus": "unclear",
        "signals": {
            "positive": positive_pool[: 2 + (h % 2)],
            "watch_for": watch_pool[: 1 + (h % 2)],
        },
    }


def get_or_create_culture_summary(job_id: int, db: Session) -> dict:
    """Return cached culture summary or generate and cache a new one."""
    parsed = db.execute(
        select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
    ).scalar_one_or_none()

    if parsed and parsed.culture_summary:
        return parsed.culture_summary

    job = db.get(Job, job_id)
    if job is None:
        return {"error": "Job not found"}

    culture = analyze_company_culture(
        company=job.company,
        job_description=job.description_text or "",
        job_title=job.title,
    )

    # Cache the result
    if parsed:
        parsed.culture_summary = culture
    else:
        parsed = JobParsedDetail(job_id=job_id, culture_summary=culture)
        db.add(parsed)

    db.commit()
    return culture
