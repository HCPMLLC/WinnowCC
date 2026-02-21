"""LLM-powered cover letter generation.

Chain: OpenAI (primary) → Anthropic Claude (fallback) → static template (final).
Mirrors the LLM call pattern in llm_parser.py.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def is_cover_letter_llm_available() -> bool:
    """Check if cover-letter LLM generation is enabled."""
    enabled = os.getenv(
        "COVER_LETTER_LLM_ENABLED",
        "true",
    ).lower() in ("true", "1", "yes")
    return enabled and (_has_openai_key() or _has_anthropic_key())


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a professional cover letter writer. Write a compelling cover letter that:

- Is 250-400 words long
- Mentions the company name at least 2 times
- Addresses the hiring manager by name if provided
- Uses at least one enthusiasm keyword \
(excited, passionate, eager, thrilled, enthusiastic)
- Connects the candidate's specific experience and skills to the job requirements
- Has a professional but warm tone
- Contains NO placeholder brackets like [company mission] or [skill]
- Does NOT fabricate experience the candidate doesn't have
- Does NOT use markdown formatting (no bold, italic, headers, or bullet points)
- Outputs ONLY the cover letter text, starting with "Dear" \
and ending with the candidate's name
- Uses standard paragraph breaks between sections
"""


def _build_user_prompt(
    job_title: str,
    company: str,
    job_description: str,
    hiring_manager: str | None,
    candidate_name: str,
    candidate_summary: str | None,
    candidate_skills: list[str],
    candidate_experience: list[dict],
) -> str:
    """Build the user prompt with concise, relevant candidate and job data."""
    parts: list[str] = []

    # Job info
    parts.append(f"JOB TITLE: {job_title}")
    parts.append(f"COMPANY: {company}")
    if hiring_manager:
        parts.append(f"HIRING MANAGER: {hiring_manager}")
    desc = (job_description or "")[:2000]
    parts.append(f"JOB DESCRIPTION:\n{desc}")

    # Candidate info
    parts.append(f"\nCANDIDATE NAME: {candidate_name}")
    if candidate_summary:
        parts.append(f"PROFESSIONAL SUMMARY: {candidate_summary}")
    if candidate_skills:
        top_skills = candidate_skills[:15]
        parts.append(f"KEY SKILLS: {', '.join(top_skills)}")
    if candidate_experience:
        parts.append("RECENT EXPERIENCE:")
        for exp in candidate_experience[:3]:
            title = exp.get("title") or "Role"
            comp = exp.get("company") or "Company"
            parts.append(f"  - {title} at {comp}")
            duties = exp.get("duties") or exp.get("bullets") or []
            for duty in duties[:4]:
                parts.append(f"    * {duty}")

    parts.append("\nWrite a cover letter for this candidate applying to this job.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI API. Raises on failure."""
    from openai import OpenAI  # lazy import

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv(
        "COVER_LETTER_OPENAI_MODEL",
        os.getenv("LLM_PARSER_MODEL", "gpt-4o-mini"),
    )
    timeout = int(os.getenv("COVER_LETTER_TIMEOUT", "60"))

    client = OpenAI(api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=800,
    )
    return (response.choices[0].message.content or "").strip()


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Call Anthropic Claude API. Raises on failure."""
    from anthropic import Anthropic  # lazy import

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv(
        "COVER_LETTER_ANTHROPIC_MODEL",
        os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
    )
    timeout = int(os.getenv("COVER_LETTER_TIMEOUT", "60"))

    client = Anthropic(api_key=api_key, timeout=timeout)
    response = client.messages.create(
        model=model,
        max_tokens=800,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    return (response.content[0].text or "").strip()


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Try OpenAI first, then Anthropic Claude. Raises on total failure."""
    last_exc: Exception | None = None

    if _has_openai_key():
        try:
            logger.info("Cover letter: trying OpenAI")
            return _call_openai(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Cover letter OpenAI failed: %s", exc)

    if _has_anthropic_key():
        try:
            logger.info("Cover letter: trying Anthropic Claude")
            return _call_anthropic(system_prompt, user_prompt)
        except Exception as exc:
            last_exc = exc
            logger.warning("Cover letter Anthropic failed: %s", exc)

    raise last_exc or RuntimeError("No LLM API keys configured for cover letter")


# ---------------------------------------------------------------------------
# Static fallback (reproduces the original _build_cover_letter_doc text)
# ---------------------------------------------------------------------------


def _top_requirements(description: str) -> list[str]:
    sentences = [s.strip() for s in description.split(".") if s.strip()]
    return sentences[:3] if sentences else []


def _generate_static_cover_letter(
    job_title: str,
    company: str,
    job_description: str,
    hiring_manager: str | None,
    candidate_name: str,
) -> str:
    """Generate the same static cover letter the old code produced."""
    greeting_name = hiring_manager or "Hiring Manager"
    lines: list[str] = []

    lines.append(f"Dear {greeting_name},")
    lines.append("")
    lines.append(
        f"I am excited to apply for the {job_title} role at {company}. "
        "My background aligns closely with your needs, and I would welcome the chance "
        "to contribute immediately."
    )
    lines.append("")
    lines.append(
        f"I am especially interested in {company}'s mission and the opportunity "
        "to make a meaningful impact."
    )
    lines.append("")

    requirements = _top_requirements(job_description)
    if requirements:
        lines.append("Key alignments:")
        for req in requirements[:3]:
            lines.append(f"  - {req}")
        lines.append("")

    lines.append(
        "I appreciate the opportunity to bring my experience to your team. "
        "If helpful, I can share additional examples of impact and walk through "
        "how I would approach your immediate priorities."
    )
    lines.append("")
    lines.append(f"Sincerely,\n{candidate_name}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_cover_letter_text(
    job_title: str,
    company: str,
    job_description: str,
    hiring_manager: str | None = None,
    candidate_name: str = "Candidate",
    candidate_summary: str | None = None,
    candidate_skills: list[str] | None = None,
    candidate_experience: list[dict] | None = None,
) -> str:
    """Generate a cover letter. Uses LLM if available, otherwise static template.

    Returns plain text (no DOCX formatting).
    """
    if not is_cover_letter_llm_available():
        logger.info("Cover letter LLM not available, using static template")
        return _generate_static_cover_letter(
            job_title,
            company,
            job_description,
            hiring_manager,
            candidate_name,
        )

    try:
        user_prompt = _build_user_prompt(
            job_title=job_title,
            company=company,
            job_description=job_description,
            hiring_manager=hiring_manager,
            candidate_name=candidate_name,
            candidate_summary=candidate_summary,
            candidate_skills=candidate_skills or [],
            candidate_experience=candidate_experience or [],
        )
        text = _call_llm(_SYSTEM_PROMPT, user_prompt)

        # Validate: if too short, fall back to static
        word_count = len(text.split())
        if word_count < 100:
            logger.warning(
                "Cover letter LLM too short (%d words), static fallback",
                word_count,
            )
            return _generate_static_cover_letter(
                job_title,
                company,
                job_description,
                hiring_manager,
                candidate_name,
            )

        return text

    except Exception as exc:
        logger.error("Cover letter LLM generation failed: %s", exc)
        return _generate_static_cover_letter(
            job_title,
            company,
            job_description,
            hiring_manager,
            candidate_name,
        )
