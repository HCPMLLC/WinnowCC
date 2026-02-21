from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.routers import auth as auth_router
from app.services import auth as auth_service


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


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

_OAUTH_CB = "/api/auth/oauth/callback"
_REDIRECT_URI = "http://localhost/api/auth/callback"


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
    with SessionLocal() as s:
        yield s


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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _mock_auth0_responses(
    userinfo: dict,
    token_status: int = 200,
    userinfo_status: int = 200,
):
    """Mock httpx.AsyncClient for Auth0 calls."""

    class FakeResponse:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data

        def json(self):
            return self._data

    class FakeClient:
        async def post(self, url, json=None):
            if token_status != 200:
                return FakeResponse(
                    token_status,
                    {"error_description": "invalid_grant"},
                )
            return FakeResponse(200, {"access_token": "fake-access-token"})

        async def get(self, url, headers=None):
            if userinfo_status != 200:
                return FakeResponse(userinfo_status, {})
            return FakeResponse(200, userinfo)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    return FakeClient


@pytest.fixture(autouse=True)
def set_auth0_env(monkeypatch):
    monkeypatch.setattr(auth_router, "AUTH0_DOMAIN", "test.auth0.com")
    monkeypatch.setattr(auth_router, "AUTH0_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(auth_router, "AUTH0_CLIENT_SECRET", "test-client-secret")


def test_oauth_callback_creates_new_user(client, session):
    """OAuth callback creates a new user for unknown email."""
    userinfo = {
        "sub": "auth0|123",
        "email": "new@example.com",
    }
    mock_client = _mock_auth0_responses(userinfo)

    with patch("app.routers.auth.httpx.AsyncClient", mock_client):
        resp = client.post(
            _OAUTH_CB,
            json={
                "code": "test-code",
                "redirect_uri": _REDIRECT_URI,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["onboarding_complete"] is False

    user = session.query(User).filter_by(email="new@example.com").first()
    assert user is not None
    assert user.oauth_provider == "auth0"
    assert user.oauth_sub == "auth0|123"
    assert user.password_hash == ""


def test_oauth_callback_links_existing_user(client, session):
    """OAuth callback links OAuth fields to existing user."""
    user = User(
        email="existing@example.com",
        password_hash=auth_service.hash_password("Password123"),
    )
    session.add(user)
    session.commit()
    assert user.oauth_provider is None

    userinfo = {
        "sub": "auth0|456",
        "email": "existing@example.com",
    }
    mock_client = _mock_auth0_responses(userinfo)

    with patch("app.routers.auth.httpx.AsyncClient", mock_client):
        resp = client.post(
            _OAUTH_CB,
            json={
                "code": "test-code",
                "redirect_uri": _REDIRECT_URI,
            },
        )

    assert resp.status_code == 200
    session.refresh(user)
    assert user.oauth_provider == "auth0"
    assert user.oauth_sub == "auth0|456"


def test_oauth_callback_already_linked_user(client, session):
    """Already-linked user keeps original OAuth fields."""
    user = User(
        email="linked@example.com",
        password_hash="",
        oauth_provider="auth0",
        oauth_sub="auth0|original",
    )
    session.add(user)
    session.commit()

    userinfo = {
        "sub": "auth0|different",
        "email": "linked@example.com",
    }
    mock_client = _mock_auth0_responses(userinfo)

    with patch("app.routers.auth.httpx.AsyncClient", mock_client):
        resp = client.post(
            _OAUTH_CB,
            json={
                "code": "test-code",
                "redirect_uri": _REDIRECT_URI,
            },
        )

    assert resp.status_code == 200
    session.refresh(user)
    assert user.oauth_provider == "auth0"
    assert user.oauth_sub == "auth0|original"


def test_oauth_callback_no_config_returns_503(client, monkeypatch):
    """OAuth callback without Auth0 config returns 503."""
    monkeypatch.setattr(auth_router, "AUTH0_DOMAIN", "")

    resp = client.post(
        _OAUTH_CB,
        json={
            "code": "test-code",
            "redirect_uri": _REDIRECT_URI,
        },
    )
    assert resp.status_code == 503


def test_oauth_callback_bad_code_returns_401(client):
    """Invalid authorization code returns 401."""
    mock_client = _mock_auth0_responses({}, token_status=400)

    with patch("app.routers.auth.httpx.AsyncClient", mock_client):
        resp = client.post(
            _OAUTH_CB,
            json={
                "code": "bad-code",
                "redirect_uri": _REDIRECT_URI,
            },
        )

    assert resp.status_code == 401


def test_oauth_callback_no_email_returns_400(client):
    """Userinfo without email returns 400."""
    userinfo = {"sub": "auth0|789"}
    mock_client = _mock_auth0_responses(userinfo)

    with patch("app.routers.auth.httpx.AsyncClient", mock_client):
        resp = client.post(
            _OAUTH_CB,
            json={
                "code": "test-code",
                "redirect_uri": _REDIRECT_URI,
            },
        )

    assert resp.status_code == 400
    assert "email" in resp.json()["detail"].lower()


def test_login_rejects_oauth_only_user(client, session):
    """OAuth-only user gets generic auth error (timing-safe, no user enumeration)."""
    user = User(
        email="oauth@example.com",
        password_hash="",
        oauth_provider="auth0",
        oauth_sub="auth0|999",
    )
    session.add(user)
    session.commit()

    resp = client.post(
        "/api/auth/login",
        json={
            "email": "oauth@example.com",
            "password": "SomePassword123",
        },
    )
    assert resp.status_code == 401
    # Timing-safe: same generic error for all auth failures
    assert "invalid" in resp.json()["detail"].lower()
