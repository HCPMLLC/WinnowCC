"""Content optimizer — tailors job postings per board audience."""

import logging
import os

from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)

# Board-specific optimization prompts
BOARD_GUIDELINES: dict[str, str] = {
    "linkedin": (
        "Professional tone. Emphasize growth, culture, and impact. "
        "Include company story. Use concise paragraphs. "
        "Add industry keywords for LinkedIn's algorithm."
    ),
    "indeed": (
        "Clear and scannable format. Emphasize pay, benefits, and schedule. "
        "Use simple, direct language. Bullet points for requirements. "
        "Front-load the most important details."
    ),
    "ziprecruiter": (
        "Keyword-dense for matching algorithm. Highlight qualifications "
        "clearly. Include specific technical terms. Use structured format "
        "with clear sections."
    ),
    "google_jobs": (
        "Structured data optimized. Salary transparency required. "
        "Clean HTML without excessive formatting. Clear job title "
        "without marketing fluff."
    ),
    "usajobs": (
        "Government format compliance. Use KSA (Knowledge, Skills, "
        "Abilities) language. Include GS grade mapping. Follow merit "
        "system principles. Formal tone."
    ),
}


def optimize_for_board(job: EmployerJob, board_type: str) -> dict:
    """Optimize a job posting's content for a specific board.

    Returns dict with optimized title, description, requirements,
    and a content_diff explaining changes.
    """
    guidelines = BOARD_GUIDELINES.get(board_type, "")

    original = {
        "title": job.title or "",
        "description": job.description or "",
        "requirements": job.requirements or "",
    }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # No API key — return original content with note
        return {
            **original,
            "content_diff": "No ANTHROPIC_API_KEY configured; "
            "returning original content.",
            "optimized": False,
        }

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, max_retries=3)
        prompt = _build_prompt(job, board_type, guidelines)

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return _parse_response(message.content[0].text, original)

    except Exception as e:
        logger.warning("Content optimization failed: %s", e)
        return {
            **original,
            "content_diff": f"Optimization failed: {e}",
            "optimized": False,
        }


def _build_prompt(job: EmployerJob, board_type: str, guidelines: str) -> str:
    return f"""Optimize this job posting for {board_type}.

RULES:
- NEVER fabricate information. Only rephrase and restructure.
- Maintain factual accuracy of salary, location, requirements.
- Adapt tone and emphasis, not substance.
- Return JSON with keys: title, description, requirements, content_diff

Board guidelines: {guidelines}

Original posting:
Title: {job.title}
Description: {job.description or "N/A"}
Requirements: {job.requirements or "N/A"}
Location: {job.location or "N/A"}
Salary: {job.salary_min or "N/A"} - {job.salary_max or "N/A"}

Return valid JSON only."""


def _parse_response(text: str, original: dict) -> dict:
    import json

    try:
        # Try to extract JSON from the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            return {
                "title": data.get("title", original["title"]),
                "description": data.get("description", original["description"]),
                "requirements": data.get("requirements", original["requirements"]),
                "content_diff": data.get("content_diff", ""),
                "optimized": True,
            }
    except json.JSONDecodeError:
        pass

    return {
        **original,
        "content_diff": "Failed to parse optimization response.",
        "optimized": False,
    }
