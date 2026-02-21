"""Tests for admin job quality routes (GET /flagged, POST /fraud-override)."""

from __future__ import annotations

from datetime import UTC, datetime

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
from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.models.user import User
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
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
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
    def override():
        yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_admin(session) -> User:
    user = User(
        email="admin@example.com",
        password_hash="x",
        is_admin=True,
    )
    session.add(user)
    session.commit()
    return user


def _make_user(session) -> User:
    user = User(
        email="user@example.com",
        password_hash="x",
        is_admin=False,
    )
    session.add(user)
    session.commit()
    return user


def _admin_cookie(client, user: User):
    token = auth_service.make_token(
        user_id=user.id,
        email=user.email,
    )
    client.cookies.set(auth_service.COOKIE_NAME, token)


def _make_job(session, **overrides) -> Job:
    now = datetime.now(UTC)
    defaults = dict(
        source="test",
        source_job_id="j1",
        url="https://example.com/j1",
        title="Software Engineer",
        company="Acme Corp",
        location="Remote",
        remote_flag=True,
        description_text="Build things.",
        content_hash="abc123",
        ingested_at=now,
    )
    defaults.update(overrides)
    job = Job(**defaults)
    session.add(job)
    session.commit()
    return job


def _make_parsed(session, job_id: int, **overrides):
    defaults = dict(
        job_id=job_id,
        fraud_score=50,
        posting_quality_score=60,
        is_likely_fraudulent=False,
        red_flags=[
            {
                "code": "vague_description",
                "severity": "medium",
                "description": "Description is vague",
                "points": 15,
            },
        ],
        is_stale=False,
    )
    defaults.update(overrides)
    parsed = JobParsedDetail(**defaults)
    session.add(parsed)
    session.commit()
    return parsed


# ------------------------------------------------------------------
# GET /api/admin/jobs/flagged
# ------------------------------------------------------------------


class TestGetFlaggedJobs:
    def test_requires_auth(self, client):
        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 401

    def test_requires_admin(self, client, session):
        user = _make_user(session)
        _admin_cookie(client, user)
        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 403

    def test_returns_flagged_jobs(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(session, job.id, fraud_score=65)

        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_id"] == job.id
        assert data[0]["title"] == "Software Engineer"
        assert data[0]["company"] == "Acme Corp"
        assert data[0]["fraud_score"] == 65

    def test_excludes_below_threshold(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(session, job.id, fraud_score=30)

        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_includes_at_threshold(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(session, job.id, fraud_score=40)

        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_sorted_by_fraud_score_desc(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        j1 = _make_job(session, source_job_id="j1", content_hash="h1")
        j2 = _make_job(session, source_job_id="j2", content_hash="h2")
        j3 = _make_job(session, source_job_id="j3", content_hash="h3")
        _make_parsed(session, j1.id, fraud_score=45)
        _make_parsed(session, j2.id, fraud_score=90)
        _make_parsed(session, j3.id, fraud_score=60)

        resp = client.get("/api/admin/jobs/flagged")
        data = resp.json()
        assert len(data) == 3
        scores = [d["fraud_score"] for d in data]
        assert scores == [90, 60, 45]

    def test_returns_red_flags(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        flags = [
            {
                "code": "no_company_info",
                "severity": "high",
                "description": "No company info",
                "points": 25,
            },
        ]
        _make_parsed(session, job.id, fraud_score=70, red_flags=flags)

        resp = client.get("/api/admin/jobs/flagged")
        data = resp.json()
        assert len(data[0]["red_flags"]) == 1
        assert data[0]["red_flags"][0]["code"] == "no_company_info"
        assert data[0]["red_flags"][0]["severity"] == "high"
        assert data[0]["red_flags"][0]["points"] == 25

    def test_empty_when_no_flagged(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        resp = client.get("/api/admin/jobs/flagged")
        assert resp.status_code == 200
        assert resp.json() == []


# ------------------------------------------------------------------
# POST /api/admin/jobs/{job_id}/fraud-override
# ------------------------------------------------------------------


class TestFraudOverride:
    def test_requires_auth(self, client):
        resp = client.post(
            "/api/admin/jobs/1/fraud-override",
            json={"is_fraudulent": True},
        )
        assert resp.status_code == 401

    def test_requires_admin(self, client, session):
        user = _make_user(session)
        _admin_cookie(client, user)
        resp = client.post(
            "/api/admin/jobs/1/fraud-override",
            json={"is_fraudulent": True},
        )
        assert resp.status_code == 403

    def test_mark_fraudulent(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(session, job.id, fraud_score=55)

        resp = client.post(
            f"/api/admin/jobs/{job.id}/fraud-override",
            json={"is_fraudulent": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job.id
        assert data["is_likely_fraudulent"] is True
        assert data["is_active"] is False

        # Verify persisted
        session.refresh(job)
        assert job.is_active is False

    def test_mark_legitimate(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(
            session,
            job.id,
            fraud_score=55,
            is_likely_fraudulent=True,
        )

        resp = client.post(
            f"/api/admin/jobs/{job.id}/fraud-override",
            json={"is_fraudulent": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_likely_fraudulent"] is False
        assert data["is_active"] is True

    def test_missing_field_returns_400(self, client, session):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        job = _make_job(session)
        _make_parsed(session, job.id)

        resp = client.post(
            f"/api/admin/jobs/{job.id}/fraud-override",
            json={},
        )
        assert resp.status_code == 400

    def test_nonexistent_parsed_detail_returns_404(
        self,
        client,
        session,
    ):
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        resp = client.post(
            "/api/admin/jobs/9999/fraud-override",
            json={"is_fraudulent": True},
        )
        assert resp.status_code == 404

    def test_nonexistent_job_returns_404(self, client, session):
        """Parsed detail exists but job doesn't (edge case)."""
        admin = _make_admin(session)
        _admin_cookie(client, admin)

        # Create a parsed detail for a job_id that doesn't exist
        # This is an edge case — the FK normally prevents it,
        # but SQLite doesn't enforce FKs by default.
        parsed = JobParsedDetail(
            job_id=9999,
            fraud_score=50,
        )
        session.add(parsed)
        session.commit()

        resp = client.post(
            "/api/admin/jobs/9999/fraud-override",
            json={"is_fraudulent": True},
        )
        assert resp.status_code == 404
