"""Tests for the unified resume parsing pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.resume_pipeline import (
    ParseOptions,
    ParseResult,
    merge_recruiter_reparse,
    merge_with_existing_profile,
    parse_text,
)


# ---------------------------------------------------------------------------
# parse_text — strategy tests
# ---------------------------------------------------------------------------

SAMPLE_TEXT = "\n".join(
    [
        "Jane Doe",
        "jane@example.com",
        "(555) 123-4567",
        "",
        "Skills",
        "Python, SQL, Docker",
    ]
)


def test_parse_text_regex_only() -> None:
    result = parse_text(SAMPLE_TEXT, ParseOptions(parser_strategy="regex_only"))
    assert result.parser_used == "regex"
    assert result.profile_json["basics"]["email"] == "jane@example.com"


def test_parse_text_llm_only_success() -> None:
    mock_json = {"basics": {"name": "Jane Doe"}, "skills": ["Python"]}

    with (
        patch(
            "app.services.llm_parser.is_llm_parser_available", return_value=True
        ),
        patch("app.services.llm_parser.parse_with_llm", return_value=mock_json),
    ):
        result = parse_text(SAMPLE_TEXT, ParseOptions(parser_strategy="llm_only"))

    assert result.parser_used == "llm"
    assert result.profile_json == mock_json


def test_parse_text_llm_only_raises_when_unavailable() -> None:
    with patch(
        "app.services.llm_parser.is_llm_parser_available", return_value=False
    ):
        with pytest.raises(RuntimeError, match="not available"):
            parse_text(SAMPLE_TEXT, ParseOptions(parser_strategy="llm_only"))


def test_parse_text_llm_then_regex_uses_llm_when_available() -> None:
    mock_json = {"basics": {"name": "Jane"}}

    with (
        patch(
            "app.services.llm_parser.is_llm_parser_available", return_value=True
        ),
        patch("app.services.llm_parser.parse_with_llm", return_value=mock_json),
    ):
        result = parse_text(
            SAMPLE_TEXT, ParseOptions(parser_strategy="llm_then_regex")
        )

    assert result.parser_used == "llm"


def test_parse_text_llm_then_regex_falls_back_to_regex() -> None:
    with patch(
        "app.services.llm_parser.is_llm_parser_available", return_value=False
    ):
        result = parse_text(
            SAMPLE_TEXT, ParseOptions(parser_strategy="llm_then_regex")
        )

    assert result.parser_used == "regex"
    assert result.profile_json["basics"]["email"] == "jane@example.com"


def test_parse_text_llm_then_regex_falls_back_on_llm_exception() -> None:
    with (
        patch(
            "app.services.llm_parser.is_llm_parser_available", return_value=True
        ),
        patch(
            "app.services.llm_parser.parse_with_llm",
            side_effect=Exception("API error"),
        ),
    ):
        result = parse_text(
            SAMPLE_TEXT, ParseOptions(parser_strategy="llm_then_regex")
        )

    assert result.parser_used == "regex"


# ---------------------------------------------------------------------------
# merge_recruiter_reparse
# ---------------------------------------------------------------------------


def test_merge_recruiter_reparse_preserves_email_and_name() -> None:
    existing = {
        "basics": {"email": "j@co.com", "name": "Jane", "first_name": "Jane", "last_name": "Doe"},
        "skills": ["Excel"],
        "source": "recruiter_resume_upload",
        "sourced_by_user_id": 42,
    }
    llm = {
        "basics": {"summary": "Experienced engineer"},
        "skills": ["Python", "Docker"],
    }

    merged = merge_recruiter_reparse(existing, llm)

    assert merged["basics"]["email"] == "j@co.com"
    assert merged["basics"]["name"] == "Jane"
    assert merged["basics"]["first_name"] == "Jane"
    assert merged["basics"]["last_name"] == "Doe"
    assert merged["basics"]["summary"] == "Experienced engineer"
    assert merged["source"] == "recruiter_resume_upload"
    assert merged["sourced_by_user_id"] == 42
    assert "Python" in merged["skills"]


def test_merge_recruiter_reparse_does_not_overwrite_llm_basics() -> None:
    """If LLM already extracted email, keep the LLM version."""
    existing = {"basics": {"email": "old@co.com"}}
    llm = {"basics": {"email": "new@co.com", "name": "New Name"}}

    merged = merge_recruiter_reparse(existing, llm)
    assert merged["basics"]["email"] == "new@co.com"
    assert merged["basics"]["name"] == "New Name"


# ---------------------------------------------------------------------------
# merge_with_existing_profile
# ---------------------------------------------------------------------------


def test_merge_with_existing_profile_no_user() -> None:
    parsed = {"basics": {"name": "Jane"}, "skills": ["Python"]}
    result = merge_with_existing_profile(MagicMock(), None, parsed)
    assert result is parsed


def test_merge_with_existing_profile_preserves_manual_edits() -> None:
    existing_profile = MagicMock()
    existing_profile.profile_json = {
        "basics": {"name": "Jane Doe", "email": "jane@co.com", "phone": "555-1234"},
        "preferences": {"target_titles": ["Engineer"], "remote_ok": True},
        "skill_years": {"Python": 5},
    }

    mock_session = MagicMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = existing_profile

    parsed = {
        "basics": {"name": "J Doe", "email": "new@co.com", "summary": "Great dev"},
        "skills": ["Python", "Docker"],
        "preferences": {},
    }

    result = merge_with_existing_profile(mock_session, 1, parsed)

    # Preserved from existing
    assert result["basics"]["name"] == "Jane Doe"
    assert result["basics"]["email"] == "jane@co.com"
    assert result["basics"]["phone"] == "555-1234"
    assert result["preferences"]["target_titles"] == ["Engineer"]
    assert result["skill_years"]["Python"] == 5
    # Overwritten from parse
    assert result["basics"]["summary"] == "Great dev"
    assert result["skills"] == ["Python", "Docker"]


# ---------------------------------------------------------------------------
# min_text_length enforcement (via extract_and_parse)
# ---------------------------------------------------------------------------


def test_extract_and_parse_min_text_length() -> None:
    from app.services.resume_pipeline import extract_and_parse

    with patch(
        "app.services.text_extraction.extract_text", return_value="short"
    ):
        with pytest.raises(ValueError, match="too short"):
            extract_and_parse(
                MagicMock(),
                ParseOptions(min_text_length=100),
            )
