"""Unified resume parsing pipeline.

Provides a shared core for candidate, recruiter batch, and recruiter LLM
reparse flows.  Each caller controls behavior via ``ParseOptions``:

- candidate flow:  ``parser_strategy="llm_then_regex"``
- recruiter batch:  ``parser_strategy="regex_only", min_text_length=20``
- recruiter reparse: ``parser_strategy="llm_only", min_text_length=20``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParseOptions:
    parser_strategy: str = "llm_then_regex"  # "llm_then_regex" | "regex_only" | "llm_only"
    min_text_length: int = 1


@dataclass
class ParseResult:
    profile_json: dict = field(default_factory=dict)
    parser_used: str = "regex"  # "llm" or "regex"


# ---------------------------------------------------------------------------
# Core pipeline functions
# ---------------------------------------------------------------------------


def extract_and_parse(file_path: Path, options: ParseOptions | None = None) -> ParseResult:
    """Full pipeline: extract text from file then parse with configured strategy."""
    from app.services.text_extraction import extract_text

    options = options or ParseOptions()
    text = extract_text(file_path)
    if not text or len(text.strip()) < options.min_text_length:
        raise ValueError(
            f"Extracted text too short ({len(text.strip()) if text else 0} chars, "
            f"minimum {options.min_text_length})."
        )
    return parse_text(text, options)


def parse_text(text: str, options: ParseOptions | None = None) -> ParseResult:
    """Parse already-extracted text using the configured strategy."""
    from app.services.profile_parser import parse_profile_from_text

    options = options or ParseOptions()
    strategy = options.parser_strategy

    if strategy == "regex_only":
        return ParseResult(
            profile_json=parse_profile_from_text(text),
            parser_used="regex",
        )

    if strategy == "llm_only":
        return _parse_with_llm_or_fail(text)

    # llm_then_regex (default): try LLM first, fall back to regex
    try:
        return _parse_with_llm_or_fail(text)
    except Exception as exc:
        logger.warning("LLM parse failed, falling back to regex: %s", exc)
        return ParseResult(
            profile_json=parse_profile_from_text(text),
            parser_used="regex",
        )


def _parse_with_llm_or_fail(text: str) -> ParseResult:
    """Attempt LLM parsing.  Raises on failure or unavailability."""
    from app.services.llm_parser import is_llm_parser_available, parse_with_llm

    if not is_llm_parser_available():
        raise RuntimeError("LLM parser not available")

    profile_json = parse_with_llm(text)
    return ParseResult(profile_json=profile_json, parser_used="llm")


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def merge_with_existing_profile(
    session: Session, user_id: int | None, parsed: dict
) -> dict:
    """Merge parsed resume data with the user's latest existing profile.

    - Overwrite from parse: experience, skills, education, certifications
    - Preserve from existing (if populated): basics fields, preferences,
      skill_years, llm_enrichment
    - Always update summary from parse (it comes from resume text)
    """
    from app.models.candidate_profile import CandidateProfile

    if user_id is None:
        return parsed

    stmt = (
        select(CandidateProfile)
        .where(CandidateProfile.user_id == user_id)
        .order_by(CandidateProfile.version.desc())
        .limit(1)
    )
    existing_profile = session.execute(stmt).scalar_one_or_none()
    if existing_profile is None:
        return parsed

    existing = existing_profile.profile_json or {}
    existing_basics = existing.get("basics") or {}
    parsed_basics = parsed.get("basics") or {}

    _BASICS_PRESERVE_KEYS = (
        "first_name",
        "last_name",
        "name",
        "email",
        "phone",
        "location",
        "work_authorization",
        "total_years_experience",
    )
    merged_basics = dict(parsed_basics)
    for key in _BASICS_PRESERVE_KEYS:
        existing_val = existing_basics.get(key)
        if existing_val:
            merged_basics[key] = existing_val

    # Always overwrite summary from parsed data (it comes from resume text)
    if parsed_basics.get("summary"):
        merged_basics["summary"] = parsed_basics["summary"]

    parsed["basics"] = merged_basics

    # Preserve preferences entirely from existing profile
    existing_prefs = existing.get("preferences")
    if existing_prefs:
        parsed["preferences"] = existing_prefs

    # Preserve skill_years if existing has it and parsed doesn't
    if existing.get("skill_years") and not parsed.get("skill_years"):
        parsed["skill_years"] = existing["skill_years"]

    # Preserve llm_enrichment if existing has it and parsed doesn't
    if existing.get("llm_enrichment") and not parsed.get("llm_enrichment"):
        parsed["llm_enrichment"] = existing["llm_enrichment"]

    return parsed


def merge_recruiter_reparse(existing_json: dict, llm_json: dict) -> dict:
    """Merge LLM-parsed data into an existing recruiter-uploaded profile.

    Preserves regex-extracted email/name (critical for pipeline matching)
    and recruiter metadata; upgrades everything else with LLM data.
    """
    existing_basics = existing_json.get("basics", {})
    llm_basics = llm_json.get("basics", {})

    for key in ("email", "name", "first_name", "last_name"):
        if existing_basics.get(key) and not llm_basics.get(key):
            llm_basics[key] = existing_basics[key]

    llm_json["basics"] = llm_basics

    # Preserve recruiter metadata
    for key in ("source", "sourced_by_user_id"):
        if existing_json.get(key):
            llm_json[key] = existing_json[key]

    return llm_json
