"""Tests for cover_letter_generator — LLM cover letter generation."""

from __future__ import annotations

from unittest.mock import patch

from app.services.cover_letter_generator import (
    _build_user_prompt,
    generate_cover_letter_text,
    is_cover_letter_llm_available,
)

# -------------------------------------------------------------------
# Shared fixtures
# -------------------------------------------------------------------

SAMPLE_JOB_DESC = (
    "We are looking for a Senior Python Developer to join our team. "
    "You will build scalable APIs and mentor junior developers."
)

SAMPLE_SKILLS = ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"]

SAMPLE_EXPERIENCE = [
    {
        "title": "Senior Software Engineer",
        "company": "Acme Corp",
        "duties": [
            "Built REST APIs serving 10M requests/day",
            "Led migration from monolith to microservices",
        ],
    },
    {
        "title": "Software Engineer",
        "company": "StartupCo",
        "duties": [
            "Developed ETL pipelines",
            "Implemented CI/CD with GitHub Actions",
        ],
    },
]

GOOD_LLM_RESPONSE = (
    "Dear Jane Smith,\n\n"
    "I am excited to apply for the Senior Python Developer "
    "position at TechCorp. With over eight years of experience "
    "building scalable APIs and leading engineering teams, I am "
    "confident I can make an immediate impact at TechCorp.\n\n"
    "In my most recent role as Senior Software Engineer at "
    "Acme Corp, I built REST APIs serving 10 million requests "
    "per day and led a successful migration from a monolith to "
    "microservices architecture. These experiences have given "
    "me deep expertise in Python, FastAPI, and cloud "
    "infrastructure which align directly with your needs.\n\n"
    "I am passionate about writing clean, maintainable code "
    "and mentoring junior developers. I would welcome the "
    "opportunity to bring this experience to your team and "
    "contribute to your mission of building world-class "
    "developer tools.\n\n"
    "I appreciate your time and look forward to discussing "
    "how I can contribute to your team's success.\n\n"
    "Sincerely,\nRonald Lawson"
)


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------


_ENV_OPENAI = {
    "OPENAI_API_KEY": "sk-test",
    "COVER_LETTER_LLM_ENABLED": "true",
}
_ENV_BOTH = {
    "OPENAI_API_KEY": "sk-test",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "COVER_LETTER_LLM_ENABLED": "true",
}


class TestStaticFallbackWhenNoKeys:
    """No API keys → returns static template."""

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_static(self):
        result = generate_cover_letter_text(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            hiring_manager="Jane Smith",
            candidate_name="Ronald Lawson",
        )
        assert "Dear Jane Smith" in result
        assert "TechCorp" in result
        assert "Ronald Lawson" in result
        assert "[" not in result


class TestLLMGenerationOpenAI:
    """Mock OpenAI → returns LLM-generated text."""

    @patch.dict("os.environ", _ENV_OPENAI)
    @patch("app.services.cover_letter_generator._call_openai")
    def test_openai_success(self, mock_openai):
        mock_openai.return_value = GOOD_LLM_RESPONSE
        result = generate_cover_letter_text(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            hiring_manager="Jane Smith",
            candidate_name="Ronald Lawson",
            candidate_skills=SAMPLE_SKILLS,
            candidate_experience=SAMPLE_EXPERIENCE,
        )
        assert result == GOOD_LLM_RESPONSE
        mock_openai.assert_called_once()


class TestOpenAIFailsFallsBackToAnthropic:
    """OpenAI raises → falls back to Claude."""

    @patch.dict("os.environ", _ENV_BOTH)
    @patch("app.services.cover_letter_generator._call_anthropic")
    @patch("app.services.cover_letter_generator._call_openai")
    def test_fallback_to_anthropic(self, mock_oai, mock_ant):
        mock_oai.side_effect = RuntimeError("OpenAI down")
        mock_ant.return_value = GOOD_LLM_RESPONSE
        result = generate_cover_letter_text(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            candidate_name="Ronald Lawson",
        )
        assert result == GOOD_LLM_RESPONSE
        mock_oai.assert_called_once()
        mock_ant.assert_called_once()


class TestBothLLMFailFallsBackToStatic:
    """Both LLMs fail → returns static (no crash)."""

    @patch.dict("os.environ", _ENV_BOTH)
    @patch("app.services.cover_letter_generator._call_anthropic")
    @patch("app.services.cover_letter_generator._call_openai")
    def test_both_fail_static(self, mock_oai, mock_ant):
        mock_oai.side_effect = RuntimeError("OpenAI down")
        mock_ant.side_effect = RuntimeError("Anthropic down")
        result = generate_cover_letter_text(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            hiring_manager="Jane Smith",
            candidate_name="Ronald Lawson",
        )
        assert "Dear Jane Smith" in result
        assert "TechCorp" in result
        assert "Ronald Lawson" in result


class TestTooShortResponseFallsBack:
    """LLM returns <100 words → falls back to static."""

    @patch.dict("os.environ", _ENV_OPENAI)
    @patch("app.services.cover_letter_generator._call_openai")
    def test_short_response_fallback(self, mock_openai):
        mock_openai.return_value = "Dear Hiring Manager, I want this job. Thanks."
        result = generate_cover_letter_text(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            candidate_name="Ronald Lawson",
        )
        assert "I am excited to apply" in result
        assert "TechCorp" in result


class TestPromptConstruction:
    """Verify _build_user_prompt includes key data."""

    def test_prompt_includes_all_fields(self):
        summary = "Experienced engineer with 8 years in backend development."
        prompt = _build_user_prompt(
            job_title="Senior Python Developer",
            company="TechCorp",
            job_description=SAMPLE_JOB_DESC,
            hiring_manager="Jane Smith",
            candidate_name="Ronald Lawson",
            candidate_summary=summary,
            candidate_skills=SAMPLE_SKILLS,
            candidate_experience=SAMPLE_EXPERIENCE,
        )
        assert "Senior Python Developer" in prompt
        assert "TechCorp" in prompt
        assert "Jane Smith" in prompt
        assert "Ronald Lawson" in prompt
        assert "Python" in prompt
        assert "FastAPI" in prompt
        assert "Acme Corp" in prompt
        assert "Built REST APIs" in prompt
        assert "Experienced engineer" in prompt


class TestDisabledViaEnvVar:
    """COVER_LETTER_LLM_ENABLED controls availability."""

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test", "COVER_LETTER_LLM_ENABLED": "false"},
    )
    def test_disabled_returns_false(self):
        assert is_cover_letter_llm_available() is False

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "sk-test", "COVER_LETTER_LLM_ENABLED": "true"},
    )
    def test_enabled_returns_true(self):
        assert is_cover_letter_llm_available() is True

    @patch.dict(
        "os.environ",
        {"COVER_LETTER_LLM_ENABLED": "true"},
        clear=True,
    )
    def test_no_keys_returns_false(self):
        assert is_cover_letter_llm_available() is False
