"""Tests for the billing endpoints and usage enforcement."""

from datetime import date
from unittest.mock import MagicMock, patch

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
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.services import auth as auth_service
from app.services import billing as billing_service


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
    with SessionLocal() as sess:
        yield sess


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


def _create_user_and_candidate(session, email="bill@example.com", plan_tier=None):
    user = User(email=email, password_hash="x")
    session.add(user)
    session.flush()
    candidate = Candidate(
        user_id=user.id,
        plan_tier=plan_tier,
        desired_job_types=[],
        desired_locations=[],
        communication_channels=[],
    )
    session.add(candidate)
    session.commit()
    return user, candidate


def _auth_cookie(client, user):
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)


# ---------- Billing status ----------


def test_billing_status_free_tier(client, session):
    user, _ = _create_user_and_candidate(session)
    _auth_cookie(client, user)

    resp = client.get("/api/billing/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_tier"] == "free"
    assert data["match_refreshes_used"] == 0
    assert data["match_refreshes_limit"] == 10
    assert data["tailor_requests_used"] == 0
    assert data["tailor_requests_limit"] == 1


def test_billing_status_pro_tier(client, session):
    user, candidate = _create_user_and_candidate(session, plan_tier="pro")
    # Admin override path: plan_tier=pro, subscription_status=None → pro
    _auth_cookie(client, user)

    resp = client.get("/api/billing/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_tier"] == "pro"
    assert data["match_refreshes_limit"] is None  # unlimited
    assert data["tailor_requests_limit"] is None


# ---------- Checkout ----------


def test_checkout_creates_session(client, session, monkeypatch):
    user, _ = _create_user_and_candidate(session)
    _auth_cookie(client, user)

    monkeypatch.setattr(billing_service, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(billing_service, "STRIPE_WEBHOOK_SECRET", "whsec_test_fake")
    monkeypatch.setattr(billing_service, "STRIPE_PRICE_MONTHLY", "price_test_monthly")
    monkeypatch.setattr(billing_service, "STRIPE_PRICE_ANNUAL", "price_test_annual")
    # Unified checkout uses PRICE_IDS dict
    monkeypatch.setattr(
        billing_service,
        "PRICE_IDS",
        {
            **billing_service.PRICE_IDS,
            ("candidate", "pro", "monthly"): "price_test_monthly",
        },
    )

    mock_customer = MagicMock()
    mock_customer.id = "cus_test123"
    mock_checkout = MagicMock()
    mock_checkout.url = "https://checkout.stripe.com/test"

    with patch("app.services.billing._stripe_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.customers.create.return_value = mock_customer
        mock_client.checkout.sessions.create.return_value = mock_checkout
        mock_client_fn.return_value = mock_client

        resp = client.post("/api/billing/checkout?billing_cycle=monthly")
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"


def test_checkout_rejects_invalid_cycle(client, session):
    user, _ = _create_user_and_candidate(session)
    _auth_cookie(client, user)

    resp = client.post("/api/billing/checkout?billing_cycle=weekly")
    assert resp.status_code == 400


# ---------- Webhook ----------


def test_webhook_checkout_completed(client, session):
    user, candidate = _create_user_and_candidate(session)
    candidate.stripe_customer_id = "cus_wh123"
    session.commit()

    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object.customer = "cus_wh123"
    mock_event.data.object.subscription = "sub_wh123"
    # Provide real metadata dict so .get() returns strings, not MagicMock
    mock_event.data.object.metadata = {"segment": "candidate", "tier": "pro"}

    mock_sub = MagicMock()
    mock_sub.items.data = [MagicMock()]
    mock_sub.items.data[0].price.recurring.interval = "month"

    with patch("app.services.billing._stripe_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.webhooks.construct_event.return_value = mock_event
        mock_client.subscriptions.retrieve.return_value = mock_sub
        mock_client_fn.return_value = mock_client

        with patch.object(billing_service, "STRIPE_WEBHOOK_SECRET", "whsec_test"):
            resp = client.post(
                "/api/billing/webhook",
                content=b"raw_body",
                headers={"stripe-signature": "sig_test"},
            )

    assert resp.status_code == 200
    session.refresh(candidate)
    assert candidate.plan_tier == "pro"
    assert candidate.subscription_status == "active"
    assert candidate.stripe_subscription_id == "sub_wh123"


# ---------- Usage enforcement ----------


def test_match_refresh_limit_blocks_at_10(session):
    user, candidate = _create_user_and_candidate(session)
    usage = UsageCounter(
        user_id=user.id,
        period_start=date.today().replace(day=1),
        match_refreshes=10,
        tailor_requests=0,
    )
    session.add(usage)
    session.commit()

    with pytest.raises(Exception) as exc_info:
        billing_service.check_match_refresh_limit(session, user, candidate)
    assert "429" in str(exc_info.value.status_code)


def test_tailor_limit_blocks_at_3(session):
    user, candidate = _create_user_and_candidate(session)
    usage = UsageCounter(
        user_id=user.id,
        period_start=date.today().replace(day=1),
        match_refreshes=0,
        tailor_requests=3,
    )
    session.add(usage)
    session.commit()

    with pytest.raises(Exception) as exc_info:
        billing_service.check_tailor_limit(session, user, candidate)
    assert "429" in str(exc_info.value.status_code)


def test_pro_user_bypasses_limits(session):
    user, candidate = _create_user_and_candidate(session, plan_tier="pro")
    usage = UsageCounter(
        user_id=user.id,
        period_start=date.today().replace(day=1),
        match_refreshes=999,
        tailor_requests=999,
    )
    session.add(usage)
    session.commit()

    # Should not raise
    billing_service.check_match_refresh_limit(session, user, candidate)
    billing_service.check_tailor_limit(session, user, candidate)


# ---------- Admin override ----------


def test_admin_override_changes_plan(client, session, monkeypatch):
    user, candidate = _create_user_and_candidate(session)
    _auth_cookie(client, user)

    monkeypatch.setattr("app.routers.billing.ADMIN_TOKEN", "admin-secret")

    resp = client.post(
        f"/api/billing/admin/override/{user.id}",
        json={"plan_tier": "pro", "billing_cycle": "annual"},
        headers={"x-admin-token": "admin-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_tier"] == "pro"
    assert data["billing_cycle"] == "annual"

    session.refresh(candidate)
    assert candidate.plan_tier == "pro"


def test_admin_override_rejects_bad_token(client, session, monkeypatch):
    user, _ = _create_user_and_candidate(session)
    monkeypatch.setattr("app.routers.billing.ADMIN_TOKEN", "admin-secret")

    resp = client.post(
        f"/api/billing/admin/override/{user.id}",
        json={"plan_tier": "pro"},
        headers={"x-admin-token": "wrong-token"},
    )
    assert resp.status_code == 403
