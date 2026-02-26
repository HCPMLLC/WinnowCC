"""Comprehensive tests for recruiter endpoints, billing helpers, and actions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_job_candidate import RecruiterJobCandidate
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.user import User
from app.services import auth as auth_service
from app.services import billing as billing_service


# ---------------------------------------------------------------------------
# SQLite JSONB compat
# ---------------------------------------------------------------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


_EXTRA_TABLES_SQL = [
    "CREATE TABLE IF NOT EXISTS mjass_application_drafts (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS mjass_application_events (id INTEGER PRIMARY KEY, draft_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS consents (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS candidate_preferences_v1 (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS onboarding_state (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS parsed_resume_documents (id INTEGER PRIMARY KEY, resume_document_id INTEGER)",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_recruiter_user(session, email="rec@example.com", role="recruiter"):
    """Create a user with recruiter role."""
    user = User(email=email, password_hash="x", role=role)
    session.add(user)
    session.flush()
    return user


def _create_recruiter_profile(
    session,
    user,
    *,
    tier="trial",
    sub_status="trialing",
    company_name="Test Agency",
    briefs_used=0,
    salary_used=0,
):
    """Create a RecruiterProfile with given tier and usage.

    Note: We do NOT set trial_started_at / trial_ends_at because SQLite stores
    naive datetimes, but is_trial_active compares against datetime.now(tz.utc)
    (timezone-aware), which causes a TypeError.  Tests that need trial
    functionality should mock the is_trial_active / trial_days_remaining
    properties directly.
    """
    now = datetime.now(timezone.utc)
    profile = RecruiterProfile(
        user_id=user.id,
        company_name=company_name,
        subscription_tier=tier,
        subscription_status=sub_status,
        candidate_briefs_used=briefs_used,
        salary_lookups_used=salary_used,
        usage_reset_at=now,
    )
    session.add(profile)
    session.flush()
    return profile


def _auth_cookie(client, user):
    """Set auth cookie for a user."""
    token = auth_service.make_token(user_id=user.id, email=user.email)
    client.cookies.set(auth_service.COOKIE_NAME, token)


def _create_client(session, profile, company_name="Acme Corp"):
    """Create a recruiter client."""
    c = RecruiterClient(
        recruiter_profile_id=profile.id,
        company_name=company_name,
    )
    session.add(c)
    session.flush()
    return c


def _create_pipeline_candidate(session, profile, **kwargs):
    """Create a pipeline candidate."""
    defaults = {
        "recruiter_profile_id": profile.id,
        "external_name": "Jane Doe",
        "stage": "sourced",
    }
    defaults.update(kwargs)
    pc = RecruiterPipelineCandidate(**defaults)
    session.add(pc)
    session.flush()
    return pc


def _create_recruiter_job(session, profile, *, title="Python Dev", status="draft"):
    """Create a recruiter job posting."""
    job = RecruiterJob(
        recruiter_profile_id=profile.id,
        title=title,
        description="Build great things with Python and FastAPI. Minimum 10 chars.",
        status=status,
    )
    session.add(job)
    session.flush()
    return job


# ===========================================================================
# BILLING HELPERS — unit tests (no HTTP, just service functions)
# ===========================================================================


class TestGetRecruiterTier:
    """Test get_recruiter_tier() for various profile states."""

    def test_trial_active(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, tier="trial", sub_status="trialing")
        assert billing_service.get_recruiter_tier(profile) == "trial"

    def test_trial_expired_still_returns_trial(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, tier="trial", sub_status="trialing")
        profile.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.flush()
        assert billing_service.get_recruiter_tier(profile) == "trial"

    def test_solo_active(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        assert billing_service.get_recruiter_tier(profile) == "solo"

    def test_team_active(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="team", sub_status="active",
        )
        assert billing_service.get_recruiter_tier(profile) == "team"

    def test_agency_active(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="agency", sub_status="active",
        )
        assert billing_service.get_recruiter_tier(profile) == "agency"

    def test_canceled_sub_falls_to_trial(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="canceled",
        )
        assert billing_service.get_recruiter_tier(profile) == "trial"

    def test_none_tier_defaults_trial(self):
        """When tier is None (in-memory only), get_recruiter_tier returns trial."""
        profile = MagicMock()
        profile.subscription_tier = None
        profile.subscription_status = None
        profile.is_trial_active = False
        profile.billing_exempt = False
        assert billing_service.get_recruiter_tier(profile) == "trial"

    def test_billing_exempt_returns_stored_tier(self, session):
        """billing_exempt=True with canceled status still returns stored tier."""
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="agency", sub_status="canceled",
        )
        profile.billing_exempt = True
        session.flush()
        assert billing_service.get_recruiter_tier(profile) == "agency"

    def test_billing_exempt_with_no_subscription_status(self, session):
        """billing_exempt=True with None status returns stored tier."""
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="agency", sub_status=None,
        )
        profile.billing_exempt = True
        session.flush()
        assert billing_service.get_recruiter_tier(profile) == "agency"

    def test_admin_override_null_status_returns_tier(self, session):
        """subscription_status=None returns stored tier (admin override)."""
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="agency", sub_status=None,
        )
        assert billing_service.get_recruiter_tier(profile) == "agency"


class TestGetRecruiterLimit:
    """Test get_recruiter_limit() lookups."""

    def test_trial_briefs_unlimited(self):
        assert billing_service.get_recruiter_limit("trial", "candidate_briefs_per_month") == 999

    def test_solo_briefs(self):
        assert billing_service.get_recruiter_limit("solo", "candidate_briefs_per_month") == 20

    def test_solo_clients(self):
        assert billing_service.get_recruiter_limit("solo", "clients") == 5

    def test_solo_pipeline(self):
        assert billing_service.get_recruiter_limit("solo", "pipeline_candidates") == 100

    def test_solo_active_jobs(self):
        assert billing_service.get_recruiter_limit("solo", "active_job_orders") == 10

    def test_team_seats(self):
        assert billing_service.get_recruiter_limit("team", "seats") == 10

    def test_agency_seats_unlimited(self):
        assert billing_service.get_recruiter_limit("agency", "seats") == 999

    def test_unknown_tier_falls_to_trial(self):
        assert billing_service.get_recruiter_limit("unknown", "seats") == 1

    def test_unknown_key_returns_zero(self):
        assert billing_service.get_recruiter_limit("solo", "nonexistent_key") == 0


class TestMaybeResetRecruiterCounters:
    """Test _maybe_reset_recruiter_counters() monthly rollover."""

    def test_reset_when_no_reset_at(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, briefs_used=5, salary_used=3)
        profile.usage_reset_at = None
        session.flush()

        billing_service._maybe_reset_recruiter_counters(profile, session)
        assert profile.candidate_briefs_used == 0
        assert profile.salary_lookups_used == 0
        assert profile.usage_reset_at is not None

    def test_reset_when_different_month(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, briefs_used=10, salary_used=7)
        # Set reset_at to last month
        last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
        profile.usage_reset_at = last_month
        session.flush()

        billing_service._maybe_reset_recruiter_counters(profile, session)
        assert profile.candidate_briefs_used == 0
        assert profile.salary_lookups_used == 0

    def test_no_reset_same_month(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, briefs_used=5, salary_used=3)
        # Already reset this month
        profile.usage_reset_at = datetime.now(timezone.utc)
        session.flush()

        billing_service._maybe_reset_recruiter_counters(profile, session)
        assert profile.candidate_briefs_used == 5
        assert profile.salary_lookups_used == 3


class TestCheckRecruiterMonthlyLimit:
    """Test check_recruiter_monthly_limit() enforcement."""

    def test_unlimited_tier_never_blocks(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, briefs_used=999)
        # Trial tier has 999 (unlimited) briefs
        billing_service.check_recruiter_monthly_limit(
            profile, "candidate_briefs_used", "candidate_briefs_per_month", session,
        )

    def test_solo_blocks_at_limit(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            briefs_used=20,
        )
        with pytest.raises(Exception) as exc_info:
            billing_service.check_recruiter_monthly_limit(
                profile, "candidate_briefs_used", "candidate_briefs_per_month", session,
            )
        assert exc_info.value.status_code == 429

    def test_solo_allows_under_limit(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            briefs_used=5,
        )
        # Should not raise
        billing_service.check_recruiter_monthly_limit(
            profile, "candidate_briefs_used", "candidate_briefs_per_month", session,
        )

    def test_salary_lookup_limit_solo(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            salary_used=5,
        )
        with pytest.raises(Exception) as exc_info:
            billing_service.check_recruiter_monthly_limit(
                profile, "salary_lookups_used", "salary_lookups_per_month", session,
            )
        assert exc_info.value.status_code == 429


class TestIncrementRecruiterCounter:
    """Test increment_recruiter_counter()."""

    def test_increment_briefs(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, briefs_used=3)
        new_val = billing_service.increment_recruiter_counter(
            profile, "candidate_briefs_used", session,
        )
        assert new_val == 4
        assert profile.candidate_briefs_used == 4

    def test_increment_salary(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, salary_used=0)
        new_val = billing_service.increment_recruiter_counter(
            profile, "salary_lookups_used", session,
        )
        assert new_val == 1

    def test_increment_from_none(self, session):
        """When counter attr is None in-memory, increment treats it as 0."""
        profile = MagicMock()
        profile.candidate_briefs_used = None
        profile.salary_lookups_used = 0
        profile.usage_reset_at = datetime.now(timezone.utc)
        new_val = billing_service.increment_recruiter_counter(
            profile, "candidate_briefs_used", session,
        )
        assert new_val == 1


class TestCheckRecruiterFeature:
    """Test check_recruiter_feature()."""

    def test_chrome_extension_all_tiers(self, session):
        user = _create_recruiter_user(session)
        for tier in ("trial", "solo", "team", "agency"):
            profile = _create_recruiter_profile(
                session, user, tier=tier, sub_status="active",
            )
            assert billing_service.check_recruiter_feature(profile, "chrome_extension") is True
            session.delete(profile)
            session.flush()

    def test_migration_toolkit_all_tiers(self, session):
        user = _create_recruiter_user(session)
        profile = _create_recruiter_profile(session, user, tier="solo", sub_status="active")
        assert billing_service.check_recruiter_feature(profile, "migration_toolkit") is True


# ===========================================================================
# PROFILE ENDPOINTS
# ===========================================================================


class TestRecruiterProfileCreate:
    """Test POST /api/recruiter/profile."""

    def test_create_profile(self, client, session):
        user = _create_recruiter_user(session, email="new_rec@example.com")
        session.commit()
        _auth_cookie(client, user)

        # Patch start_trial to avoid SQLite tz-aware datetime issues
        with patch.object(RecruiterProfile, "start_trial", lambda self: setattr(self, "subscription_tier", "trial") or setattr(self, "subscription_status", "trialing")):
            resp = client.post(
                "/api/recruiter/profile",
                json={
                    "company_name": "Test Staffing",
                    "company_type": "staffing_agency",
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "Test Staffing"
        assert data["subscription_tier"] == "trial"

    def test_create_duplicate_fails(self, client, session):
        user = _create_recruiter_user(session, email="dup@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/profile",
            json={"company_name": "Second Profile"},
        )
        assert resp.status_code == 400

    def test_non_recruiter_role_rejected(self, client, session):
        user = _create_recruiter_user(session, email="cand@example.com", role="candidate")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/profile",
            json={"company_name": "Nope"},
        )
        assert resp.status_code == 403


class TestRecruiterProfileGet:
    """Test GET /api/recruiter/profile."""

    def test_get_own_profile(self, client, session):
        user = _create_recruiter_user(session, email="get@example.com")
        _create_recruiter_profile(
            session, user, company_name="My Agency",
            tier="solo", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "My Agency"

    def test_no_profile_auto_creates(self, client, session):
        user = _create_recruiter_user(session, email="noprof@example.com")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 200


class TestRecruiterProfileUpdate:
    """Test PATCH /api/recruiter/profile."""

    def test_partial_update(self, client, session):
        user = _create_recruiter_user(session, email="upd@example.com")
        _create_recruiter_profile(
            session, user, company_name="Old Name",
            tier="solo", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.patch(
            "/api/recruiter/profile",
            json={"company_name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "New Name"


# ===========================================================================
# PLAN ENDPOINT
# ===========================================================================


class TestRecruiterPlan:
    """Test GET /api/recruiter/plan."""

    def test_trial_plan_info(self, client, session):
        user = _create_recruiter_user(session, email="plan@example.com")
        _create_recruiter_profile(session, user, tier="trial")
        session.commit()
        _auth_cookie(client, user)

        # Mock trial_days_remaining to avoid SQLite tz-aware comparison
        with patch.object(RecruiterProfile, "trial_days_remaining", new_callable=lambda: property(lambda self: 14)):
            resp = client.get("/api/recruiter/plan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "trial"
        assert data["crm_level"] == "full"
        assert "limits" in data

    def test_solo_plan_info(self, client, session):
        user = _create_recruiter_user(session, email="solo_plan@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/plan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "solo"
        assert data["crm_level"] == "basic"
        assert data["trial_days_remaining"] is None


# ===========================================================================
# CRM TIER GATING — client/pipeline/job limits
# ===========================================================================


class TestClientTierGating:
    """Test that solo tier enforces client limits."""

    def test_solo_blocks_at_5_clients(self, client, session):
        user = _create_recruiter_user(session, email="soloc@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        # Create 5 clients to hit the limit
        for i in range(5):
            _create_client(session, profile, company_name=f"Client {i}")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/clients",
            json={"company_name": "Sixth Client"},
        )
        assert resp.status_code == 429
        assert "Client limit" in resp.json()["detail"]

    def test_team_allows_more_clients(self, client, session):
        user = _create_recruiter_user(session, email="teamc@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="team", sub_status="active",
        )
        for i in range(5):
            _create_client(session, profile, company_name=f"Client {i}")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/clients",
            json={"company_name": "Sixth Client"},
        )
        assert resp.status_code == 201


class TestPipelineTierGating:
    """Test that solo tier enforces pipeline candidate limits."""

    def test_solo_blocks_at_100_candidates(self, client, session):
        user = _create_recruiter_user(session, email="solop@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        # Create 100 pipeline candidates
        for i in range(100):
            _create_pipeline_candidate(
                session, profile, external_name=f"Candidate {i}",
            )
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/pipeline",
            json={"external_name": "Overflow Candidate", "stage": "sourced", "source": "manual"},
        )
        assert resp.status_code == 429
        assert "Pipeline limit" in resp.json()["detail"]


class TestJobOrderTierGating:
    """Test that solo tier enforces active job order limits."""

    def test_solo_blocks_at_10_active_jobs(self, client, session):
        user = _create_recruiter_user(session, email="soloj@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        # Create 10 active jobs
        for i in range(10):
            _create_recruiter_job(
                session, profile, title=f"Job {i}", status="active",
            )
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/jobs",
            json={
                "title": "Overflow Job",
                "description": "This job should be blocked by tier limits.",
                "status": "active",
            },
        )
        assert resp.status_code == 429
        assert "Active job limit" in resp.json()["detail"]

    def test_draft_jobs_dont_count_toward_limit(self, client, session):
        user = _create_recruiter_user(session, email="solod@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        # Create 10 draft jobs (should NOT count toward active limit)
        for i in range(10):
            _create_recruiter_job(session, profile, title=f"Draft {i}", status="draft")
        session.commit()
        _auth_cookie(client, user)

        # Patch out the background job sync to avoid Redis dependency
        with patch("app.routers.recruiter._enqueue_recruiter_job_sync"):
            resp = client.post(
                "/api/recruiter/jobs",
                json={
                    "title": "Active Job",
                    "description": "This should succeed because drafts don't count.",
                    "status": "active",
                },
            )
        assert resp.status_code == 201


# ===========================================================================
# INTELLIGENCE ENDPOINTS
# ===========================================================================


class TestIntelligenceUsage:
    """Test GET /api/recruiter/intelligence/usage."""

    def test_usage_returns_tier_and_counts(self, client, session):
        user = _create_recruiter_user(session, email="intl@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            briefs_used=3, salary_used=1,
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/intelligence/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "solo"
        assert data["briefs"]["used"] == 3
        assert data["briefs"]["limit"] == 20
        assert data["salary_lookups"]["used"] == 1
        assert data["salary_lookups"]["limit"] == 5


class TestBriefEndpoint:
    """Test POST /api/recruiter/briefs."""

    def test_blocks_when_at_limit(self, client, session):
        user = _create_recruiter_user(session, email="bf@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            briefs_used=20,
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/briefs?candidate_profile_id=1&brief_type=general",
        )
        assert resp.status_code == 429

    def test_rejects_invalid_brief_type(self, client, session):
        user = _create_recruiter_user(session, email="bft@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active", briefs_used=0,
        )
        session.commit()
        _auth_cookie(client, user)

        with patch("app.services.career_intelligence.generate_candidate_brief"):
            resp = client.post(
                "/api/recruiter/briefs?candidate_profile_id=1&brief_type=invalid",
            )
        assert resp.status_code == 400

    def test_brief_success_increments_counter(self, client, session):
        user = _create_recruiter_user(session, email="bfs@example.com")
        profile = _create_recruiter_profile(session, user, briefs_used=0)
        session.commit()
        _auth_cookie(client, user)

        mock_result = {"brief_type": "general", "headline": "Great candidate"}
        with patch(
            "app.services.career_intelligence.generate_candidate_brief",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/recruiter/briefs?candidate_profile_id=1&brief_type=general",
            )
        assert resp.status_code == 200
        session.refresh(profile)
        assert profile.candidate_briefs_used == 1


class TestSalaryIntelligenceEndpoint:
    """Test GET /api/recruiter/salary-intelligence."""

    def test_blocks_when_at_limit(self, client, session):
        user = _create_recruiter_user(session, email="sal@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
            salary_used=5,
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/salary-intelligence?role=Python+Developer")
        assert resp.status_code == 429

    def test_salary_success_increments_counter(self, client, session):
        user = _create_recruiter_user(session, email="sals@example.com")
        profile = _create_recruiter_profile(session, user, salary_used=0)
        session.commit()
        _auth_cookie(client, user)

        mock_result = {"role": "Python Developer", "p50": 120000}
        with patch(
            "app.services.career_intelligence.salary_intelligence",
            return_value=mock_result,
        ):
            resp = client.get("/api/recruiter/salary-intelligence?role=Python+Developer")
        assert resp.status_code == 200
        session.refresh(profile)
        assert profile.salary_lookups_used == 1


class TestCareerTrajectoryEndpoint:
    """Test GET /api/recruiter/career-trajectory/{id}."""

    def test_trajectory_success(self, client, session):
        user = _create_recruiter_user(session, email="traj@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        mock_result = {"predictions": [{"role": "Senior Developer", "months": 12}]}
        with patch(
            "app.services.career_intelligence.predict_career_trajectory",
            return_value=mock_result,
        ):
            resp = client.get("/api/recruiter/career-trajectory/1")
        assert resp.status_code == 200
        assert "predictions" in resp.json()


class TestMarketPositionEndpoint:
    """Test GET /api/recruiter/market-position/{id}/{job_id}."""

    def test_market_position_success(self, client, session):
        user = _create_recruiter_user(session, email="mkt@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        mock_result = {"percentile": 75, "total_candidates": 50}
        with patch(
            "app.services.career_intelligence.compute_market_position",
            return_value=mock_result,
        ):
            resp = client.get("/api/recruiter/market-position/1/2")
        assert resp.status_code == 200
        assert resp.json()["percentile"] == 75


# ===========================================================================
# BULK OUTREACH
# ===========================================================================


class TestBulkOutreach:
    """Test POST /api/recruiter/outreach/bulk."""

    def test_solo_rejected(self, client, session):
        user = _create_recruiter_user(session, email="bulk_s@example.com")
        _create_recruiter_profile(
            session, user, tier="solo", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/outreach/bulk",
            params={
                "candidate_ids": [1, 2, 3],
                "message_template": "Hello!",
                "subject": "Opportunity",
            },
        )
        assert resp.status_code == 403
        assert "Team or Agency" in resp.json()["detail"]

    def test_team_allowed(self, client, session):
        user = _create_recruiter_user(session, email="bulk_t@example.com")
        profile = _create_recruiter_profile(
            session, user, tier="team", sub_status="active",
        )
        # Create pipeline candidates for the IDs
        pc1 = _create_pipeline_candidate(session, profile, external_name="A")
        pc2 = _create_pipeline_candidate(session, profile, external_name="B")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/outreach/bulk",
            params={
                "candidate_ids": [pc1.id, pc2.id],
                "message_template": "Hi there!",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["queued"] == 2

    def test_max_50_batch(self, client, session):
        user = _create_recruiter_user(session, email="bulk_m@example.com")
        _create_recruiter_profile(
            session, user, tier="team", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/outreach/bulk",
            params={
                "candidate_ids": list(range(1, 52)),  # 51 IDs
                "message_template": "Hi!",
            },
        )
        assert resp.status_code == 400

    def test_trial_allowed(self, client, session):
        user = _create_recruiter_user(session, email="bulk_trial@example.com")
        profile = _create_recruiter_profile(session, user, tier="trial")
        pc = _create_pipeline_candidate(session, profile, external_name="C")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/outreach/bulk",
            params={
                "candidate_ids": [pc.id],
                "message_template": "Hello from trial!",
            },
        )
        assert resp.status_code == 200


# ===========================================================================
# RECRUITER ACTIONS
# ===========================================================================


class TestRecruiterActions:
    """Test recruiter action queue endpoints."""

    def test_get_actions_empty(self, client, session):
        user = _create_recruiter_user(session, email="act@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/actions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_stale_pipeline_generates_action(self, client, session):
        user = _create_recruiter_user(session, email="stale@example.com")
        profile = _create_recruiter_profile(session, user)
        # Create a candidate stuck in 'screening' for 10 days
        pc = _create_pipeline_candidate(session, profile, stage="screening")
        # Force updated_at to 10 days ago
        old_date = datetime.now(timezone.utc) - timedelta(days=10)
        session.execute(
            RecruiterPipelineCandidate.__table__.update()
            .where(RecruiterPipelineCandidate.id == pc.id)
            .values(updated_at=old_date)
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/actions")
        assert resp.status_code == 200
        actions = resp.json()
        stale = [a for a in actions if a["type"] == "stale_pipeline"]
        assert len(stale) == 1
        assert stale[0]["priority"] == 1

    def test_draft_jobs_generate_action(self, client, session):
        user = _create_recruiter_user(session, email="draft_act@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_recruiter_job(session, profile, title="Unpublished Job", status="draft")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/actions")
        assert resp.status_code == 200
        actions = resp.json()
        drafts = [a for a in actions if a["type"] == "draft_jobs"]
        assert len(drafts) == 1

    def test_dismiss_action(self, client, session):
        user = _create_recruiter_user(session, email="dis@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.post("/api/recruiter/actions/test-123/dismiss")
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

    def test_snooze_action(self, client, session):
        user = _create_recruiter_user(session, email="snz@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.post("/api/recruiter/actions/test-123/snooze?hours=8")
        assert resp.status_code == 200
        assert resp.json()["snooze_hours"] == 8

    def test_unauthenticated_returns_401(self, client, session):
        resp = client.get("/api/recruiter/actions")
        assert resp.status_code == 401


# ===========================================================================
# JOB CRUD
# ===========================================================================


class TestRecruiterJobCRUD:
    """Test job create/list/get/update/delete."""

    def test_create_draft_job(self, client, session):
        user = _create_recruiter_user(session, email="jcreate@example.com")
        _create_recruiter_profile(session, user, tier="solo", sub_status="active")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/jobs",
            json={
                "title": "Senior Python Developer",
                "description": "Build scalable systems with Python and FastAPI.",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Senior Python Developer"
        assert data["status"] == "draft"

    def test_list_jobs(self, client, session):
        user = _create_recruiter_user(session, email="jlist@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_recruiter_job(session, profile, title="Job A")
        _create_recruiter_job(session, profile, title="Job B")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_jobs_filter_by_status(self, client, session):
        user = _create_recruiter_user(session, email="jfilter@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_recruiter_job(session, profile, title="Draft", status="draft")
        _create_recruiter_job(session, profile, title="Active", status="active")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/jobs?status=draft")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["status"] == "draft"

    def test_get_job_by_id(self, client, session):
        user = _create_recruiter_user(session, email="jget@example.com")
        profile = _create_recruiter_profile(session, user)
        job = _create_recruiter_job(session, profile, title="Specific Job")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/recruiter/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Specific Job"

    def test_get_nonexistent_job_404(self, client, session):
        user = _create_recruiter_user(session, email="jmiss@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/jobs/99999")
        assert resp.status_code == 404

    def test_update_job(self, client, session):
        user = _create_recruiter_user(session, email="jupd@example.com")
        profile = _create_recruiter_profile(session, user)
        job = _create_recruiter_job(session, profile, title="Old Title")
        session.commit()
        _auth_cookie(client, user)

        with patch("app.routers.recruiter._enqueue_recruiter_job_sync"):
            resp = client.patch(
                f"/api/recruiter/jobs/{job.id}",
                json={"title": "New Title"},
            )
        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"

    def test_delete_job(self, client, session):
        user = _create_recruiter_user(session, email="jdel@example.com")
        profile = _create_recruiter_profile(session, user)
        job = _create_recruiter_job(session, profile, title="To Delete")
        session.commit()
        _auth_cookie(client, user)

        with patch("app.routers.recruiter._enqueue_recruiter_job_sync"):
            resp = client.delete(f"/api/recruiter/jobs/{job.id}")
        assert resp.status_code == 204

    def test_cannot_access_other_recruiters_job(self, client, session):
        user1 = _create_recruiter_user(session, email="owner@example.com")
        profile1 = _create_recruiter_profile(session, user1)
        job = _create_recruiter_job(session, profile1, title="Private Job")

        user2 = _create_recruiter_user(session, email="other@example.com")
        _create_recruiter_profile(session, user2, company_name="Other Agency")
        session.commit()
        _auth_cookie(client, user2)

        resp = client.get(f"/api/recruiter/jobs/{job.id}")
        assert resp.status_code == 404


# ===========================================================================
# CLIENT CRUD
# ===========================================================================


class TestRecruiterClientCRUD:
    """Test client create/list/get/update/delete."""

    def test_create_client(self, client, session):
        user = _create_recruiter_user(session, email="ccreate@example.com")
        _create_recruiter_profile(session, user, tier="team", sub_status="active")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/clients",
            json={"company_name": "Acme Corp", "industry": "Technology"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "Acme Corp"

    def test_list_clients(self, client, session):
        user = _create_recruiter_user(session, email="clist@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_client(session, profile, "Alpha Inc")
        _create_client(session, profile, "Beta LLC")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/clients")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_delete_client(self, client, session):
        user = _create_recruiter_user(session, email="cdel@example.com")
        profile = _create_recruiter_profile(session, user)
        rc = _create_client(session, profile, "To Delete")
        session.commit()
        _auth_cookie(client, user)

        resp = client.delete(f"/api/recruiter/clients/{rc.id}")
        assert resp.status_code == 204


# ===========================================================================
# PIPELINE CRUD
# ===========================================================================


class TestRecruiterPipelineCRUD:
    """Test pipeline candidate operations."""

    def test_add_external_candidate(self, client, session):
        user = _create_recruiter_user(session, email="padd@example.com")
        _create_recruiter_profile(session, user, tier="team", sub_status="active")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/pipeline",
            json={
                "external_name": "John Smith",
                "external_email": "john@example.com",
                "stage": "sourced",
                "source": "manual",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["external_name"] == "John Smith"

    def test_list_pipeline(self, client, session):
        user = _create_recruiter_user(session, email="plist@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_pipeline_candidate(session, profile, external_name="Alice")
        _create_pipeline_candidate(session, profile, external_name="Bob")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/pipeline")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_pipeline_candidate(self, client, session):
        user = _create_recruiter_user(session, email="pupd@example.com")
        profile = _create_recruiter_profile(session, user)
        pc = _create_pipeline_candidate(session, profile, stage="sourced")
        session.commit()
        _auth_cookie(client, user)

        resp = client.put(
            f"/api/recruiter/pipeline/{pc.id}",
            json={"stage": "screening"},
        )
        assert resp.status_code == 200
        assert resp.json()["stage"] == "screening"

    def test_delete_pipeline_candidate(self, client, session):
        user = _create_recruiter_user(session, email="pdel@example.com")
        profile = _create_recruiter_profile(session, user)
        pc = _create_pipeline_candidate(session, profile)
        session.commit()
        _auth_cookie(client, user)

        resp = client.delete(f"/api/recruiter/pipeline/{pc.id}")
        assert resp.status_code == 204


# ===========================================================================
# ACTIVITIES
# ===========================================================================


class TestRecruiterActivities:
    """Test activity logging."""

    def test_create_activity(self, client, session):
        user = _create_recruiter_user(session, email="alog@example.com")
        _create_recruiter_profile(session, user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/recruiter/activities",
            json={"activity_type": "call", "subject": "Follow-up call"},
        )
        assert resp.status_code == 201
        assert resp.json()["activity_type"] == "call"

    def test_list_activities(self, client, session):
        user = _create_recruiter_user(session, email="alist@example.com")
        profile = _create_recruiter_profile(session, user)
        # Manually create activities
        a1 = RecruiterActivity(
            recruiter_profile_id=profile.id,
            user_id=user.id,
            activity_type="email",
        )
        a2 = RecruiterActivity(
            recruiter_profile_id=profile.id,
            user_id=user.id,
            activity_type="call",
        )
        session.add_all([a1, a2])
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/activities")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ===========================================================================
# ONBOARDING
# ===========================================================================


class TestRecruiterOnboarding:
    """Test onboarding completion."""

    def test_complete_onboarding(self, client, session):
        user = _create_recruiter_user(session, email="onb@example.com")
        session.commit()
        _auth_cookie(client, user)

        resp = client.post("/api/recruiter/onboarding/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        session.refresh(user)
        assert user.onboarding_completed_at is not None


# ===========================================================================
# DASHBOARD
# ===========================================================================


class TestRecruiterDashboard:
    """Test dashboard endpoint returns stats."""

    def test_dashboard_returns_stats(self, client, session):
        user = _create_recruiter_user(session, email="dash@example.com")
        profile = _create_recruiter_profile(session, user)
        _create_recruiter_job(session, profile, title="Active Job", status="active")
        _create_client(session, profile, "Dash Client")
        _create_pipeline_candidate(session, profile, external_name="Dash Candidate")
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_active_jobs"] == 1
        assert data["total_clients"] == 1
        assert data["total_pipeline_candidates"] == 1
        assert data["subscription_tier"] == "trial"


# ===========================================================================
# AUTH / ACCESS CONTROL
# ===========================================================================


class TestRecruiterAccessControl:
    """Test that non-recruiter users can't access recruiter endpoints."""

    def test_candidate_cannot_access_recruiter(self, client, session):
        user = User(email="cand_no@example.com", password_hash="x", role="candidate")
        session.add(user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 403

    def test_employer_cannot_access_recruiter(self, client, session):
        user = User(email="emp_no@example.com", password_hash="x", role="employer")
        session.add(user)
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 403

    def test_both_role_can_access(self, client, session):
        user = User(email="both@example.com", password_hash="x", role="both")
        session.add(user)
        session.flush()
        _create_recruiter_profile(
            session, user, company_name="Both Agency",
            tier="solo", sub_status="active",
        )
        session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/recruiter/profile")
        assert resp.status_code == 401
