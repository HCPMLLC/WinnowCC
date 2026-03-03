"""Application Status Predictor.

Estimates where a candidate's application likely stands based on:
- Days since application
- Days job has been open
- Match score relative to role
- Historical patterns (when available)
"""

import json
import logging
import os
import re
from datetime import UTC, datetime

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

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


def predict_application_status(match_id: int, session: Session) -> dict:
    """Predict the likely status of an application.

    Returns:
        {
            "predicted_stage": "screening",
            "confidence": "medium",
            "days_since_applied": 5,
            "days_job_open": 18,
            "explanation": "Based on timing and your strong match...",
            "next_milestone": "Expect response within 1-2 weeks if moving forward",
            "tips": ["Follow up on LinkedIn if no response by day 14"],
            "match_score": 75,
        }
    """
    match = session.execute(
        select(Match).where(Match.id == match_id)
    ).scalar_one_or_none()
    if not match:
        return {"error": "Match not found"}

    job = session.execute(
        select(Job).where(Job.id == match.job_id)
    ).scalar_one_or_none()
    if not job:
        return {"error": "Job not found"}

    # Calculate timing
    now = datetime.now(UTC)
    # Match.created_at is the best proxy for when application was tracked
    applied_at = match.created_at
    posted_at = job.posted_at or job.ingested_at

    days_since_applied = (now - applied_at).days if applied_at else 0
    days_job_open = (now - posted_at).days if posted_at else 0

    # Deterministic stage estimation
    stage_data = _estimate_stage(
        days_since_applied=days_since_applied,
        days_job_open=days_job_open,
        match_score=match.match_score or 0,
    )

    # Generate human-friendly explanation with LLM
    explanation = _generate_explanation(
        stage_data=stage_data,
        job_title=job.title,
        company=job.company,
        match_score=match.match_score or 0,
    )

    return {
        **stage_data,
        **explanation,
        "days_since_applied": days_since_applied,
        "days_job_open": days_job_open,
        "match_score": match.match_score,
    }


def _estimate_stage(
    days_since_applied: int,
    days_job_open: int,
    match_score: int,
) -> dict:
    """Deterministic stage estimation based on timing patterns.

    Based on industry averages from recruiting data.
    """
    # submitted (0-3 days) -> screening (3-10) -> review (10-21) -> decision (21+)
    if days_since_applied <= 3:
        stage = "submitted"
        confidence = "high"
        next_milestone = "Application enters screening queue within 3-5 business days"
    elif days_since_applied <= 10:
        stage = "screening"
        confidence = "medium"
        next_milestone = (
            "Initial review typically completes within 2 weeks of application"
        )
    elif days_since_applied <= 21:
        stage = "review"
        confidence = "medium" if match_score >= 70 else "low"
        next_milestone = "Decision usually made within 3 weeks for active roles"
    else:
        if days_job_open > 45:
            stage = "stale"
            confidence = "low"
            next_milestone = "Role may be on hold or filled — consider following up"
        else:
            stage = "decision"
            confidence = "low"
            next_milestone = "Final decisions typically within 4 weeks"

    if match_score >= 80:
        tips = ["Strong match — you're likely competitive for this role"]
    elif match_score >= 60:
        tips = ["Solid match — continue applying to similar roles while waiting"]
    else:
        tips = ["Consider strengthening your profile for better matches"]

    return {
        "predicted_stage": stage,
        "confidence": confidence,
        "next_milestone": next_milestone,
        "tips": tips,
    }


def _generate_explanation(
    stage_data: dict,
    job_title: str,
    company: str,
    match_score: int,
) -> dict:
    """Generate a friendly, encouraging explanation with LLM."""
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        return _fallback_explanation(stage_data)

    prompt = f"""Write a brief, encouraging status update for a job applicant.

Job: {job_title} at {company}
Match Score: {match_score}%
Predicted Stage: {stage_data["predicted_stage"]}
Next Milestone: {stage_data["next_milestone"]}

Return JSON:
{{"explanation": "2-3 sentence status update - honest but encouraging"}}

Rules:
1. Be realistic but not discouraging
2. If stage is "stale", gently suggest moving on while keeping hope
3. Mention their match score positively if >= 70
4. Keep it brief and actionable

Return ONLY JSON."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response
        text = re.sub(r"<[\w-]+>.*?</[\w-]+>", "", text, flags=re.DOTALL).strip()
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
        return json.loads(text)
    except Exception:
        logger.exception("Failed to generate status explanation via LLM")
        return _fallback_explanation(stage_data)


def _fallback_explanation(stage_data: dict) -> dict:
    """Deterministic fallback when LLM is unavailable."""
    stage_explanations = {
        "submitted": ("Your application was recently submitted and is in the queue."),
        "screening": (
            "Your application is likely being reviewed by the recruiting team."
        ),
        "review": (
            "If you're still in consideration, "
            "hiring managers are reviewing candidates."
        ),
        "decision": "The team is likely in final decision-making stages.",
        "stale": (
            "This role has been open a while — "
            "consider following up or exploring other options."
        ),
    }
    return {
        "explanation": stage_explanations.get(
            stage_data["predicted_stage"],
            "Your application is being processed.",
        )
    }
