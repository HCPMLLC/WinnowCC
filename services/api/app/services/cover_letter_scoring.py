"""Cover Letter Scoring Service

Computes Cover Letter Score (C_s) using the formula:
C_s = (keyword_match * 0.5) + (length_quality * 0.3) + (personalization * 0.2)

Default C_s = 50 if no cover letter exists.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.text_extraction import extract_text_from_docx


def compute_cover_letter_score(
    cover_letter_path: str | Path | None,
    job_description: str,
    company_name: str,
    hiring_manager_name: str | None = None,
) -> int:
    """
    Compute Cover Letter Score (C_s).

    Args:
        cover_letter_path: Path to the cover letter docx file
        job_description: Job description text for keyword matching
        company_name: Company name for personalization check
        hiring_manager_name: Hiring manager name for personalization check

    Returns:
        Cover letter score (0-100), defaults to 50 if no cover letter
    """
    if cover_letter_path is None:
        return 50

    path = Path(cover_letter_path)
    if not path.exists():
        return 50

    try:
        cover_text = extract_text_from_docx(path)
    except Exception:
        return 50

    if not cover_text.strip():
        return 50

    keyword_match = _compute_keyword_match(cover_text, job_description)
    length_quality = _compute_length_quality(cover_text)
    personalization = _compute_personalization(
        cover_text, company_name, hiring_manager_name
    )

    c_s = int((keyword_match * 0.5) + (length_quality * 0.3) + (personalization * 0.2))
    return max(0, min(100, c_s))


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words."""
    return {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9+.#]+", text)
        if len(token) >= 3
    }


def _compute_keyword_match(cover_text: str, job_description: str) -> int:
    """
    Compute keyword match score (0-100).

    Measures how many job description keywords appear in the cover letter.
    """
    cover_tokens = _tokenize(cover_text)
    job_tokens = _tokenize(job_description)

    if not job_tokens:
        return 50

    # Focus on important keywords (longer words, technical terms)
    important_job_tokens = {t for t in job_tokens if len(t) >= 4}
    if not important_job_tokens:
        important_job_tokens = job_tokens

    matched = cover_tokens & important_job_tokens
    match_ratio = len(matched) / len(important_job_tokens)

    # Scale: 30% match = 60 score, 50% match = 80 score, 70%+ = 100
    if match_ratio >= 0.70:
        return 100
    elif match_ratio >= 0.50:
        return 80 + int((match_ratio - 0.50) * 100)
    elif match_ratio >= 0.30:
        return 60 + int((match_ratio - 0.30) * 100)
    else:
        return int(match_ratio * 200)


def _compute_length_quality(cover_text: str) -> int:
    """
    Compute length quality score (0-100).

    Optimal cover letter length: 250-400 words.
    """
    word_count = len(cover_text.split())

    if 250 <= word_count <= 400:
        return 100
    elif 200 <= word_count < 250:
        return 85
    elif 400 < word_count <= 500:
        return 85
    elif 150 <= word_count < 200:
        return 70
    elif 500 < word_count <= 600:
        return 70
    elif 100 <= word_count < 150:
        return 50
    elif 600 < word_count <= 800:
        return 50
    else:
        # Too short or too long
        return 30


def _compute_personalization(
    cover_text: str, company_name: str, hiring_manager_name: str | None
) -> int:
    """
    Compute personalization score (0-100).

    Checks for company name mentions and hiring manager address.
    """
    cover_lower = cover_text.lower()
    score = 0

    # Company name mentioned (40 points)
    if company_name and company_name.lower() in cover_lower:
        score += 40
        # Extra points for multiple mentions
        company_mentions = cover_lower.count(company_name.lower())
        if company_mentions >= 2:
            score += 10

    # Hiring manager addressed (30 points)
    if hiring_manager_name:
        if hiring_manager_name.lower() in cover_lower:
            score += 30
        elif "dear" in cover_lower and "manager" not in cover_lower:
            # Addressed to someone specific, even if not the exact name
            score += 15
    else:
        # No hiring manager known, give partial credit for any personalized greeting
        if "dear" in cover_lower:
            score += 10

    # Role/title mentioned (20 points)
    role_keywords = ["position", "role", "opportunity", "team"]
    for keyword in role_keywords:
        if keyword in cover_lower:
            score += 5
            break

    # Enthusiasm indicators (max 10 points)
    enthusiasm_keywords = ["excited", "passionate", "eager", "thrilled", "enthusiastic"]
    for keyword in enthusiasm_keywords:
        if keyword in cover_lower:
            score += 10
            break

    return min(100, score)
