import secrets
from datetime import UTC, datetime, timedelta
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
from app.models.user import User
from app.services import auth as auth_service


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


_EXTRA_TABLES_SQL = [
    (
        "CREATE TABLE IF NOT EXISTS mjass_application_drafts"
        " (id INTEGER PRIMARY KEY, user_id INTEGER)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS mjass_application_events"
        " (id INTEGER PRIMARY KEY, draft_id INTEGER)"
    ),
    ("CREATE TABLE IF NOT EXISTS consents (id INTEGER PRIMARY KEY, user_id INTEGER)"),
    (
        "CREATE TABLE IF NOT EXISTS candidate_preferences_v1"
        " (id INTEGER PRIMARY KEY, user_id INTEGER)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS onboarding_state"
        " (id INTEGER PRIMARY KEY, user_id INTEGER)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS parsed_resume_documents"
        " (id INTEGER PRIMARY KEY, resume_document_id INTEGER)"
    ),
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


def _make_user_with_password(
    session, email="reset@example.com", password="OldPassword123"
):
    user = User(
        email=email,
        password_hash=auth_service.hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _set_reset_token(session, user, raw_token, expires_at=None):
    user.password_reset_token = raw_token
    user.password_reset_expires_at = expires_at or (
        datetime.now(UTC) + timedelta(minutes=30)
    )
    session.commit()
    return raw_token


# ---- Forgot password tests ----


def test_forgot_password_sends_email(client, session) -> None:
    """User exists -> token stored in DB, email sending attempted."""
    user = _make_user_with_password(session)

    with patch("app.routers.auth.send_password_reset_email") as mock_send:
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "reset@example.com"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"

    # Token should be stored in DB
    session.refresh(user)
    assert user.password_reset_token is not None
    assert user.password_reset_expires_at is not None

    # Email sending was attempted
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[0][0] == "reset@example.com"


def test_forgot_password_unknown_email_still_200(client) -> None:
    """Unknown email -> 200 (no info leak)."""
    resp = client.post(
        "/api/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


def test_forgot_password_oauth_only_user_still_200(client, session) -> None:
    """OAuth-only user (empty password_hash) -> 200, token set (reset still works)."""
    user = User(
        email="oauth@example.com",
        password_hash="",
    )
    session.add(user)
    session.commit()

    with patch("app.routers.auth.send_password_reset_email"):
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "oauth@example.com"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


# ---- Reset password tests ----


def test_reset_password_success(client, session) -> None:
    """Valid token + new password -> password updated, token cleared."""
    user = _make_user_with_password(session)
    raw_token = secrets.token_urlsafe(32)
    _set_reset_token(session, user, raw_token)

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "NewSecurePass456"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Password updated
    session.refresh(user)
    assert auth_service.verify_password("NewSecurePass456", user.password_hash)

    # Token cleared
    assert user.password_reset_token is None
    assert user.password_reset_expires_at is None


def test_reset_password_expired_token(client, session) -> None:
    """Expired token -> 400."""
    user = _make_user_with_password(session)
    raw_token = secrets.token_urlsafe(32)
    expired = datetime.now(UTC) - timedelta(minutes=5)
    _set_reset_token(session, user, raw_token, expires_at=expired)

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "NewPassword123"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_reset_password_invalid_token(client) -> None:
    """Wrong token -> 400."""
    resp = client.post(
        "/api/auth/reset-password",
        json={"token": "totally-bogus-token", "password": "NewPassword123"},
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.json()["detail"]


def test_reset_password_clears_token_after_use(client, session) -> None:
    """After reset, same token can't be reused."""
    user = _make_user_with_password(session)
    raw_token = secrets.token_urlsafe(32)
    _set_reset_token(session, user, raw_token)

    # First reset succeeds
    resp1 = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "FirstNewPass123"},
    )
    assert resp1.status_code == 200

    # Second attempt with same token fails
    resp2 = client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "password": "SecondNewPass456"},
    )
    assert resp2.status_code == 400
