"""Tests for profile enhancement suggestions (PROMPT71)."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("AUTH_COOKIE_NAME", "rm_session")

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.candidate_profile import CandidateProfile  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import auth as auth_service  # noqa: E402
from app.services.profile_enhancement import (  # noqa: E402
    _build_user_prompt,
    _is_profile_empty,
    generate_enhancement_suggestions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Replace Postgres-only types with SQLite-compatible ones
    from sqlalchemy import JSON as _JSON
    from sqlalchemy import Text as _Text

    _PG_TYPES = {"Vector", "JSONB", "TSVECTOR"}
    for table in Base.metadata.tables.values():
        for col in table.columns:
            type_name = type(col.type).__name__
            if type_name == "Vector":
                col.type = _Text()
            elif type_name in ("JSONB", "TSVECTOR"):
                col.type = _JSON()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    SessionLocal = sessionmaker(
        bind=engine, expire_on_commit=False
    )
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setattr(auth_service, "JWT_SECRET", "test-secret")
    monkeypatch.setattr(auth_service, "JWT_ALG", "HS256")
    monkeypatch.setattr(auth_service, "COOKIE_NAME", "rm_session")
    monkeypatch.setattr(auth_service, "COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "SESSION_DAYS", 7)


@pytest.fixture()
def client(session):
    def override():
        yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(session: Session, email: str = "enhance@test.dev") -> User:
    from datetime import UTC, datetime

    user = User(
        email=email,
        password_hash="x",
        onboarding_completed_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_cookie(user: User) -> dict:
    token = auth_service.make_token(user_id=user.id, email=user.email)
    return {auth_service.COOKIE_NAME: token}


def _create_profile(
    session: Session, user: User, version: int = 1, **extra
) -> CandidateProfile:
    profile_json = {
        "basics": {"first_name": "Jane", "last_name": "Doe", "email": "jane@test.dev"},
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Product Manager",
                "start_date": "2020-01",
                "end_date": "2024-01",
                "bullets": ["Led agile team of 8"],
                "duties": ["Roadmap planning"],
                "skills_used": ["Agile", "Jira"],
                "technologies_used": ["Jira", "Confluence"],
                "quantified_accomplishments": [],
            }
        ],
        "education": [{"school": "MIT", "degree": "BS", "field": "CS"}],
        "skills": ["Python", "Agile", "Leadership"],
        "preferences": {
            "target_titles": ["Product Manager"],
            "locations": ["San Francisco, CA"],
            "remote_ok": True,
            "job_type": None,
            "salary_min": None,
            "salary_max": None,
        },
    }
    profile_json.update(extra)
    cp = CandidateProfile(
        user_id=user.id,
        version=version,
        profile_json=profile_json,
    )
    session.add(cp)
    session.commit()
    session.refresh(cp)
    return cp


# ---------------------------------------------------------------------------
# Unit tests — _is_profile_empty
# ---------------------------------------------------------------------------


class TestIsProfileEmpty:
    def test_empty_profile(self):
        assert _is_profile_empty({}) is True

    def test_empty_lists(self):
        assert _is_profile_empty({"experience": [], "skills": [], "basics": {}}) is True

    def test_with_experience(self):
        assert _is_profile_empty({"experience": [{"title": "PM"}]}) is False

    def test_with_skills(self):
        assert _is_profile_empty({"skills": ["Python"]}) is False

    def test_with_summary(self):
        assert _is_profile_empty({"basics": {"summary": "Expert PM"}}) is False


# ---------------------------------------------------------------------------
# Unit tests — _build_user_prompt
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    def test_returns_empty_for_blank_profile(self):
        assert _build_user_prompt({}) == ""

    def test_includes_sections(self):
        prompt = _build_user_prompt(
            {
                "basics": {"first_name": "Jane"},
                "experience": [{"title": "PM"}],
                "skills": ["Python"],
            }
        )
        assert "Basic Info" in prompt
        assert "Experience" in prompt
        assert "Skills" in prompt


# ---------------------------------------------------------------------------
# Unit tests — generate_enhancement_suggestions (mocked LLM)
# ---------------------------------------------------------------------------

_MOCK_LLM_RESPONSE = json.dumps(
    {
        "suggestions": [
            {
                "category": "experience",
                "section_ref": "Acme Corp - Product Manager",
                "priority": "high",
                "current_issue": "No quantified accomplishments",
                "suggestion": "Add metrics to your PM experience",
                "example": (
                    "Before: Led team -> After: "
                    "Led team of 8, shipping 3 features/quarter"
                ),
                "impact": "Quantified results improve match scores by ~15%",
            }
        ],
        "overall_assessment": {
            "strengths": ["Clear progression", "Relevant skills"],
            "biggest_opportunity": "Add metrics to experience entries",
            "estimated_improvement": "15-20%",
        },
    }
)


class TestGenerateEnhancementSuggestions:
    @patch("app.services.profile_enhancement.get_session_factory")
    @patch("app.services.profile_enhancement._get_client")
    def test_successful_generation(self, mock_client_fn, mock_session_factory, session):
        user = _create_user(session, "gen1@test.dev")
        _create_profile(session, user, version=1)

        # Mock the session factory to return our test session
        mock_session_factory.return_value = lambda: session

        # Mock Anthropic response
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=_MOCK_LLM_RESPONSE)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        mock_client_fn.return_value = mock_client

        generate_enhancement_suggestions(user.id, 1)

        # Verify the profile was updated
        cp = (
            session.query(CandidateProfile)
            .filter_by(user_id=user.id, version=1)
            .first()
        )
        es = cp.profile_json.get("enhancement_suggestions")
        assert es is not None
        assert es["status"] == "completed"
        assert len(es["suggestions"]) == 1
        assert es["suggestions"][0]["category"] == "experience"
        assert (
            es["overall_assessment"]["biggest_opportunity"]
            == "Add metrics to experience entries"
        )

    @patch("app.services.profile_enhancement.get_session_factory")
    def test_empty_profile_skips_llm(self, mock_session_factory, session):
        user = _create_user(session, "gen2@test.dev")
        _create_profile(session, user, version=1, experience=[], skills=[], basics={})

        mock_session_factory.return_value = lambda: session

        generate_enhancement_suggestions(user.id, 1)

        cp = (
            session.query(CandidateProfile)
            .filter_by(user_id=user.id, version=1)
            .first()
        )
        es = cp.profile_json.get("enhancement_suggestions")
        assert es is not None
        assert es["status"] == "completed"
        assert es["suggestions"] == []
        assert "Add work experience" in es["overall_assessment"]["biggest_opportunity"]

    @patch("app.services.profile_enhancement.get_session_factory")
    @patch("app.services.profile_enhancement._get_client")
    def test_llm_failure_writes_failed(
        self, mock_client_fn, mock_session_factory, session
    ):
        user = _create_user(session, "gen3@test.dev")
        _create_profile(session, user, version=1)

        mock_session_factory.return_value = lambda: session

        # Make LLM raise
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API down")
        mock_client_fn.return_value = mock_client

        generate_enhancement_suggestions(user.id, 1)

        cp = (
            session.query(CandidateProfile)
            .filter_by(user_id=user.id, version=1)
            .first()
        )
        es = cp.profile_json.get("enhancement_suggestions")
        assert es is not None
        assert es["status"] == "failed"


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


class TestGetEnhancementSuggestionsAPI:
    def test_not_generated(self, client, session):
        user = _create_user(session, "api1@test.dev")
        _create_profile(session, user, version=1)
        client.cookies.update(_auth_cookie(user))

        resp = client.get("/api/profile/enhancement-suggestions")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_generated"

    def test_returns_completed(self, client, session):
        user = _create_user(session, "api2@test.dev")
        cp = _create_profile(session, user, version=1)

        pj = dict(cp.profile_json)
        pj["enhancement_suggestions"] = {
            "status": "completed",
            "suggestions": [
                {"category": "skills", "priority": "medium", "suggestion": "Add more"}
            ],
            "overall_assessment": {
                "strengths": ["Good skills"],
                "biggest_opportunity": "More certs",
            },
            "generated_at": "2026-03-01T00:00:00Z",
        }
        cp.profile_json = pj
        session.commit()

        client.cookies.update(_auth_cookie(user))
        resp = client.get("/api/profile/enhancement-suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert len(data["suggestions"]) == 1

    def test_returns_generating(self, client, session):
        user = _create_user(session, "api3@test.dev")
        cp = _create_profile(session, user, version=1)

        pj = dict(cp.profile_json)
        pj["enhancement_suggestions"] = {"status": "generating", "suggestions": []}
        cp.profile_json = pj
        session.commit()

        client.cookies.update(_auth_cookie(user))
        resp = client.get("/api/profile/enhancement-suggestions")
        assert resp.status_code == 200
        assert resp.json()["status"] == "generating"


class TestRegenerateAPI:
    @patch("app.routers.profile.get_queue")
    def test_regenerate_enqueues_job(self, mock_get_queue, client, session):
        user = _create_user(session, "regen@test.dev")
        _create_profile(session, user, version=1)
        client.cookies.update(_auth_cookie(user))

        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        resp = client.post("/api/profile/enhancement-suggestions/regenerate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "generating"

    def test_regenerate_no_profile_404(self, client, session):
        user = _create_user(session, "regen404@test.dev")
        client.cookies.update(_auth_cookie(user))

        resp = client.post("/api/profile/enhancement-suggestions/regenerate")
        assert resp.status_code == 404


class TestManualSaveClearsSuggestions:
    def test_save_clears_enhancement(self, client, session):
        user = _create_user(session, "save@test.dev")
        cp = _create_profile(session, user, version=1)

        # Add suggestions to current profile
        pj = dict(cp.profile_json)
        pj["enhancement_suggestions"] = {
            "status": "completed",
            "suggestions": [{"category": "skills"}],
        }
        cp.profile_json = pj
        session.commit()

        client.cookies.update(_auth_cookie(user))

        # Save profile (PUT) — should create new version without enhancement_suggestions
        save_payload = {
            "profile_json": {
                "basics": {"first_name": "Jane", "last_name": "Doe"},
                "experience": [],
                "education": [],
                "skills": [],
                "preferences": {
                    "target_titles": [],
                    "locations": [],
                    "remote_ok": None,
                    "job_type": None,
                    "salary_min": None,
                    "salary_max": None,
                },
                "enhancement_suggestions": {
                    "status": "completed",
                    "suggestions": [{"category": "skills"}],
                },
            }
        }
        resp = client.put("/api/profile", json=save_payload)
        assert resp.status_code == 200

        # The new version should NOT have enhancement_suggestions
        data = resp.json()
        assert "enhancement_suggestions" not in data["profile_json"]
