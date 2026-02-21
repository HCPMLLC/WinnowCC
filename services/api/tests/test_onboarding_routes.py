import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.candidate import Candidate
from app.models.user import User
from app.services import auth as auth_service


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__, Candidate.__table__])
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


def _auth_cookie_for(user_id: int, email: str) -> str:
    token = auth_service.make_token(user_id=user_id, email=email)
    return token


def _set_auth_cookie(client: TestClient, user_id: int, email: str) -> None:
    token = _auth_cookie_for(user_id, email)
    client.cookies.set(auth_service.COOKIE_NAME, token)


def test_onboarding_requires_auth(client) -> None:
    resp = client.get("/api/onboarding/me")
    assert resp.status_code == 401


def test_onboarding_me_missing_returns_404(client, session) -> None:
    user = User(email="me@example.com", password_hash="x")
    session.add(user)
    session.commit()
    _set_auth_cookie(client, user.id, user.email)
    resp = client.get("/api/onboarding/me")
    assert resp.status_code == 404


def test_onboarding_complete_requires_consents(client, session) -> None:
    user = User(email="me@example.com", password_hash="x")
    session.add(user)
    session.commit()
    _set_auth_cookie(client, user.id, user.email)

    resp = client.post("/api/onboarding/complete", json={})
    assert resp.status_code == 400


def test_onboarding_complete_creates_candidate(client, session) -> None:
    user = User(email="me@example.com", password_hash="x")
    session.add(user)
    session.commit()
    _set_auth_cookie(client, user.id, user.email)

    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "desired_job_types": ["Full-time"],
        "desired_locations": ["Remote"],
        "communication_channels": ["email"],
        "consent_terms": True,
        "consent_privacy": True,
        "consent_auto_renewal": True,
        "consent_marketing": False,
    }

    resp = client.post("/api/onboarding/complete", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == user.id
    assert data["first_name"] == "Jane"
    assert data["desired_job_types"] == ["Full-time"]

    session.refresh(user)
    assert user.onboarding_completed_at is not None


def test_onboarding_me_returns_candidate(client, session) -> None:
    user = User(email="me@example.com", password_hash="x")
    session.add(user)
    session.commit()
    record = Candidate(
        user_id=user.id,
        first_name="Alex",
        desired_job_types=["Contract"],
        desired_locations=["NYC"],
        communication_channels=["email"],
        consent_terms=True,
        consent_privacy=True,
        consent_auto_renewal=True,
        consent_marketing=False,
    )
    session.add(record)
    session.commit()

    _set_auth_cookie(client, user.id, user.email)
    resp = client.get("/api/onboarding/me")
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Alex"
