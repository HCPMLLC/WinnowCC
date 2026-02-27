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


# Raw SQL tables that cascade_delete references but have no ORM model
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


def test_signup_sets_cookie_and_returns_user(client) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "User@Example.com", "password": "Password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["user_id"] > 0
    assert data["onboarding_complete"] is False
    assert auth_service.COOKIE_NAME in resp.headers.get("set-cookie", "")


def test_signup_rejects_duplicate_email(client, session) -> None:
    session.add(User(email="dupe@example.com", password_hash="x"))
    session.commit()
    resp = client.post(
        "/api/auth/signup",
        json={"email": "dupe@example.com", "password": "Password123"},
    )
    assert resp.status_code == 400


def test_signup_rejects_invalid_email(client) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "not-an-email", "password": "Password123"},
    )
    assert resp.status_code == 422


def test_signup_rejects_long_password(client) -> None:
    resp = client.post(
        "/api/auth/signup",
        json={"email": "long@example.com", "password": "a" * 73},
    )
    assert resp.status_code == 400


def test_login_sets_cookie(client, session) -> None:
    user = User(
        email="login@example.com",
        password_hash=auth_service.hash_password("Password123"),
    )
    session.add(user)
    session.commit()
    resp = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "Password123"},
    )
    assert resp.status_code == 200
    assert auth_service.COOKIE_NAME in resp.headers.get("set-cookie", "")


def test_login_rejects_bad_password(client, session) -> None:
    user = User(
        email="login@example.com",
        password_hash=auth_service.hash_password("Password123"),
    )
    session.add(user)
    session.commit()
    resp = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "WrongPassword"},
    )
    assert resp.status_code == 401


def test_login_rejects_invalid_email(client) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "Password123"},
    )
    assert resp.status_code == 422


def test_login_rejects_long_password(client) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "a" * 73},
    )
    assert resp.status_code == 400


def test_me_requires_auth(client) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_user(client, session) -> None:
    user = User(email="me@example.com", password_hash="x")
    session.add(user)
    session.commit()
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


def test_logout_clears_cookie(client) -> None:
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert auth_service.COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie


def test_export_requires_auth(client) -> None:
    resp = client.get("/api/account/export")
    assert resp.status_code == 401


def test_export_returns_user_data(client, session) -> None:
    user = User(email="export@example.com", password_hash="x")
    session.add(user)
    session.commit()
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)
    resp = client.get("/api/account/export/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert "profile_versions" in data


def test_delete_account_requires_auth(client) -> None:
    resp = client.post(
        "/api/account/delete",
        json={"confirm": "DELETE MY ACCOUNT"},
    )
    assert resp.status_code == 401


def test_delete_account_wrong_email(client, session) -> None:
    user = User(email="del@example.com", password_hash="x")
    session.add(user)
    session.commit()
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)
    resp = client.post(
        "/api/account/delete",
        json={"confirm": "wrong"},
    )
    assert resp.status_code == 400


def test_delete_account_success(client, session) -> None:
    user = User(email="bye@example.com", password_hash="x")
    session.add(user)
    session.commit()
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)
    resp = client.post(
        "/api/account/delete",
        json={"confirm": "DELETE MY ACCOUNT"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    # User should be gone
    assert session.get(User, user.id) is None
