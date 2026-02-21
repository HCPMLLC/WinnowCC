"""Tests for the Sieve chatbot endpoint and service."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import all models so Base.metadata knows about them
import app.models as _models  # noqa: F401
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.services import auth as auth_service
from app.services.sieve_chat import (
    _get_fallback_response,
    check_escalation_needed,
    get_suggested_actions,
    load_user_context,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


# Raw SQL tables that cascade_delete references but have no ORM model
_EXTRA_TABLES_SQL = [
    "CREATE TABLE IF NOT EXISTS mjass_application_drafts "
    "(id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS mjass_application_events "
    "(id INTEGER PRIMARY KEY, draft_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS consents (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS candidate_preferences_v1 "
    "(id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS onboarding_state "
    "(id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS parsed_resume_documents "
    "(id INTEGER PRIMARY KEY, resume_document_id INTEGER)",
]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for sql in _EXTRA_TABLES_SQL:
            conn.execute(text(sql))
        conn.commit()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setattr(auth_service, "JWT_SECRET", "test-secret")
    monkeypatch.setattr(auth_service, "JWT_ALG", "HS256")
    monkeypatch.setattr(auth_service, "COOKIE_NAME", "rm_session")
    monkeypatch.setattr(auth_service, "COOKIE_SECURE", False)
    monkeypatch.setattr(auth_service, "SESSION_DAYS", 7)


@pytest.fixture()
def client(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _create_user(session, email="sieve@example.com") -> User:
    user = User(email=email, password_hash="x")
    session.add(user)
    session.commit()
    return user


def _auth_cookie(user: User) -> dict:
    token = auth_service.make_token(user_id=user.id, email=user.email)
    return {auth_service.COOKIE_NAME: token}


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


def test_sieve_chat_requires_auth(client) -> None:
    resp = client.post("/api/sieve/chat", json={"message": "hello"})
    assert resp.status_code == 401


@patch("app.routers.sieve.handle_chat")
def test_sieve_chat_returns_response(mock_handle, client, session) -> None:
    mock_handle.return_value = "Hello! Check /matches for jobs."
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/chat", json={"message": "hi there"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Hello! Check /matches for jobs."
    assert "conversation_id" in data
    assert "suggested_actions" in data

    # Verify handle_chat was called
    mock_handle.assert_called_once()
    kwargs = mock_handle.call_args.kwargs
    assert kwargs["message"] == "hi there"
    assert kwargs["user_id"] == user.id


@patch("app.routers.sieve.handle_chat")
def test_sieve_chat_handles_missing_profile(mock_handle, client, session) -> None:
    """Chat works even when user has no candidate/profile records."""
    mock_handle.return_value = "I see you're new! Head to /upload."
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/chat", json={"message": "what should I do?"})
    assert resp.status_code == 200
    assert resp.json()["response"] == "I see you're new! Head to /upload."


@patch("app.routers.sieve.handle_chat")
def test_sieve_chat_forwards_history(mock_handle, client, session) -> None:
    mock_handle.return_value = "Sure, let me elaborate."
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    history = [
        {"role": "user", "content": "Tell me about my matches"},
        {"role": "assistant", "content": "You have 5 matches."},
    ]
    resp = client.post(
        "/api/sieve/chat",
        json={"message": "Tell me more", "conversation_history": history},
    )
    assert resp.status_code == 200

    kwargs = mock_handle.call_args.kwargs
    assert len(kwargs["conversation_history"]) == 2
    assert kwargs["conversation_history"][0]["role"] == "user"


@patch(
    "app.routers.sieve.handle_chat",
    return_value="I'm having trouble connecting right now. "
    "Please try again in a moment.",
)
def test_sieve_chat_returns_fallback_on_error(mock_handle, client, session) -> None:
    """When LLM fails, handle_chat returns fallback — never 500."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "trouble" in data["response"]


@patch("app.routers.sieve.handle_chat")
def test_sieve_chat_with_full_profile(mock_handle, client, session) -> None:
    """Verify suggested_actions are returned when profile exists."""
    mock_handle.return_value = "Based on your Python skills..."
    user = _create_user(session)

    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        plan_tier="pro",
        desired_job_types=["Software Engineer"],
        desired_locations=["Remote"],
        remote_preference="remote",
    )
    session.add(candidate)
    session.flush()

    profile = CandidateProfile(
        user_id=user.id,
        version=1,
        profile_json={
            "skills": ["Python", "FastAPI", "React", "TypeScript", "SQL"],
            "experience": [
                {"title": "Senior Engineer", "company": "Acme Corp"},
                {"title": "Engineer", "company": "StartupCo"},
            ],
        },
    )
    session.add(profile)
    session.commit()

    client.cookies.update(_auth_cookie(user))
    resp = client.post("/api/sieve/chat", json={"message": "what are my skills?"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["suggested_actions"], list)


def test_sieve_chat_empty_message(client, session) -> None:
    """Empty message returns a polite prompt."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/chat", json={"message": " "})
    assert resp.status_code == 200
    assert "catch that" in resp.json()["response"].lower()


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


def test_load_user_context_empty(session) -> None:
    """Context for a user with no candidate/profile."""
    user = _create_user(session)
    ctx = load_user_context(user.id, session)
    profile = ctx.get("profile", {})
    assert profile.get("completeness_score", 0) == 0
    assert profile.get("skills_count", 0) == 0
    assert ctx.get("matches", {}).get("total_count", 0) == 0
    assert ctx.get("tailored_resumes_count", 0) == 0


def test_load_user_context_with_profile(session) -> None:
    """Context includes profile data when candidate + profile exist."""
    user = _create_user(session)
    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        desired_job_types=["Engineer"],
        desired_locations=["Remote"],
        remote_preference="remote",
    )
    session.add(candidate)
    session.flush()

    profile = CandidateProfile(
        user_id=user.id,
        version=1,
        profile_json={
            "basics": {"first_name": "Jane", "email": "jane@test.com"},
            "skills": ["Python", "FastAPI", "React"],
            "experience": [
                {"title": "Engineer", "company": "Acme"},
            ],
            "preferences": {"target_titles": ["Backend Developer"]},
        },
    )
    session.add(profile)
    session.commit()

    ctx = load_user_context(user.id, session)
    assert ctx["profile"]["name"] == "Jane Doe"
    assert ctx["profile"]["skills_count"] == 3
    assert ctx["profile"]["experience_count"] == 1
    assert "Backend Developer" in ctx["profile"]["target_titles"]
    assert ctx["profile"]["remote_preference"] == "remote"


def test_fallback_responses() -> None:
    """Keyword-based fallback returns relevant responses."""
    assert (
        "profile" in _get_fallback_response("help me").lower()
        or "navigate" in _get_fallback_response("help me").lower()
    )
    assert "matches" in _get_fallback_response("show my jobs").lower()
    assert "profile" in _get_fallback_response("my resume").lower()
    assert "ats" in _get_fallback_response("tailor").lower()
    assert "job search" in _get_fallback_response("random").lower()


def test_get_suggested_actions_incomplete_profile() -> None:
    """Suggests profile improvement when completeness < 70%."""
    ctx = {
        "profile": {"completeness_score": 50},
        "matches": {"total_count": 0},
        "tracking": {},
    }
    actions = get_suggested_actions(ctx)
    assert any("profile" in a.lower() for a in actions)


def test_get_suggested_actions_has_matches_no_applications() -> None:
    """Suggests applying when user has matches but no applications."""
    ctx = {
        "profile": {"completeness_score": 85},
        "matches": {"total_count": 10},
        "tracking": {"applied": 0},
    }
    actions = get_suggested_actions(ctx)
    assert any("apply" in a.lower() for a in actions)


def test_get_suggested_actions_default() -> None:
    """Returns default suggestions when no specific triggers apply."""
    ctx = {
        "profile": {"completeness_score": 90},
        "matches": {"total_count": 0},
        "tracking": {},
    }
    actions = get_suggested_actions(ctx)
    assert len(actions) == 3
    assert any("help" in a.lower() for a in actions)


# ---------------------------------------------------------------------------
# Sieve v2: Triggers endpoint (POST)
# ---------------------------------------------------------------------------


def test_triggers_endpoint_post(client, session) -> None:
    """POST /api/sieve/triggers returns triggers list."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/triggers", json={"dismissed_ids": []})
    assert resp.status_code == 200
    data = resp.json()
    assert "triggers" in data
    assert isinstance(data["triggers"], list)


def test_triggers_requires_auth(client) -> None:
    """POST /api/sieve/triggers requires authentication."""
    resp = client.post("/api/sieve/triggers", json={"dismissed_ids": []})
    assert resp.status_code == 401


def test_triggers_dismissed_filtered(client, session) -> None:
    """Triggers with IDs in dismissed_ids are not returned."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    # First call: get whatever triggers exist
    resp1 = client.post("/api/sieve/triggers", json={"dismissed_ids": []})
    triggers1 = resp1.json()["triggers"]

    if triggers1:
        # Dismiss all trigger IDs and re-fetch
        dismissed = [t["id"] for t in triggers1]
        resp2 = client.post("/api/sieve/triggers", json={"dismissed_ids": dismissed})
        triggers2 = resp2.json()["triggers"]
        # All dismissed triggers should be filtered out
        for t in triggers2:
            assert t["id"] not in dismissed


def test_trigger_has_action_fields(client, session) -> None:
    """Each trigger includes action_label, action_type, action_target."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.post("/api/sieve/triggers", json={"dismissed_ids": []})
    for trigger in resp.json()["triggers"]:
        assert "action_label" in trigger
        assert "action_type" in trigger
        assert "action_target" in trigger
        assert isinstance(trigger["priority"], int)


# ---------------------------------------------------------------------------
# Sieve v2: History endpoints
# ---------------------------------------------------------------------------


def test_history_empty_by_default(client, session) -> None:
    """GET /api/sieve/history returns empty list for new user."""
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    resp = client.get("/api/sieve/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_history_requires_auth(client) -> None:
    resp = client.get("/api/sieve/history")
    assert resp.status_code == 401


@patch("app.routers.sieve.handle_chat")
def test_chat_persists_messages(mock_handle, client, session) -> None:
    """After a chat exchange, messages appear in history."""
    mock_handle.return_value = "Sure, I can help with that."
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    # Send a message
    client.post("/api/sieve/chat", json={"message": "Help me with jobs"})

    # Check history
    resp = client.get("/api/sieve/history")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Help me with jobs"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Sure, I can help with that."


@patch("app.routers.sieve.handle_chat")
def test_history_clears(mock_handle, client, session) -> None:
    """DELETE /api/sieve/history removes all messages."""
    mock_handle.return_value = "Response"
    user = _create_user(session)
    client.cookies.update(_auth_cookie(user))

    # Create some history
    client.post("/api/sieve/chat", json={"message": "hello"})

    # Verify history exists
    resp = client.get("/api/sieve/history")
    assert len(resp.json()) == 2

    # Clear
    resp = client.delete("/api/sieve/history")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2

    # Verify empty
    resp = client.get("/api/sieve/history")
    assert resp.json() == []


def test_delete_history_requires_auth(client) -> None:
    resp = client.delete("/api/sieve/history")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Sieve v2: Escalation detection
# ---------------------------------------------------------------------------


def test_escalation_not_triggered_on_normal_response() -> None:
    """Normal responses don't trigger escalation."""
    assert not check_escalation_needed(
        "Here are your top matches!",
        [
            {"role": "user", "content": "show matches"},
            {"role": "assistant", "content": "You have 5 matches."},
        ],
    )


def test_escalation_not_triggered_on_single_uncertain() -> None:
    """A single uncertain response is not enough for escalation."""
    assert not check_escalation_needed(
        "I'm not sure about that.",
        [
            {"role": "user", "content": "something"},
            {"role": "assistant", "content": "Here are your matches."},
        ],
    )


def test_escalation_triggered_after_three_consecutive() -> None:
    """Three consecutive uncertain responses trigger escalation."""
    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "I'm not sure about that."},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "I can't help with that directly."},
    ]
    assert check_escalation_needed(
        "I don't have that information for you.",
        history,
    )


def test_escalation_not_triggered_if_middle_was_confident() -> None:
    """If one of the three recent assistant responses was confident, no escalation."""
    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "I'm not sure about that."},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "Your match score is 85%."},  # Confident
    ]
    assert not check_escalation_needed(
        "I don't have that information.",
        history,
    )
