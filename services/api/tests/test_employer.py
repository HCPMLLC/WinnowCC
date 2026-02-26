"""Comprehensive employer test suite — tier enforcement, billing helpers,
profile CRUD, job limits, candidate views, AI parsing, distribution,
analytics, compliance, team management, and access control.

Uses the Postgres test database via conftest.py fixtures (db_session, client).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models.candidate_profile import CandidateProfile
from app.models.employer import (
    EmployerCandidateView,
    EmployerJob,
    EmployerProfile,
)
from app.models.user import User
from app.services.auth import hash_password, make_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMAIL_SEQ = 0


def _unique_email(prefix="emp"):
    global _EMAIL_SEQ
    _EMAIL_SEQ += 1
    return f"{prefix}{_EMAIL_SEQ}@test.dev"


def _create_employer_user(db_session, email=None, role="employer"):
    user = User(
        email=email or _unique_email(),
        password_hash=hash_password("Pass123!"),
        is_admin=False,
        role=role,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_employer_profile(
    db_session,
    user,
    *,
    tier="free",
    sub_status="active",
    ai_parsing_used=0,
):
    profile = EmployerProfile(
        user_id=user.id,
        company_name="Test Corp",
        subscription_tier=tier,
        subscription_status=sub_status,
        ai_parsing_used=ai_parsing_used,
        usage_reset_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.flush()
    return profile


def _auth_cookie(client, user):
    token = make_token(user_id=user.id, email=user.email)
    client.cookies.set("rm_session", token)
    return client


def _create_job(db_session, employer, *, title="Test Job", status_val="active"):
    job = EmployerJob(
        employer_id=employer.id,
        title=title,
        description="A comprehensive test job description.",
        status=status_val,
    )
    db_session.add(job)
    db_session.flush()
    return job


def _create_candidate_profile(db_session, *, open_to=True):
    """Create a candidate user + profile for employer view tests."""
    user = _create_employer_user(db_session, role="candidate")
    from app.models.candidate import Candidate

    candidate = Candidate(
        user_id=user.id,
        plan_tier="free",
        desired_job_types=[],
        desired_locations=[],
        communication_channels=[],
    )
    db_session.add(candidate)
    db_session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        version=1,
        profile_json={"basics": {"full_name": "Jane Doe", "total_years_experience": 5}},
        open_to_opportunities=open_to,
        profile_visibility="public",
    )
    db_session.add(profile)
    db_session.flush()
    return profile


# ============================================================================
# 1. BILLING HELPERS (unit tests — no HTTP)
# ============================================================================


class TestGetEmployerTier:
    def test_free_tier(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="free")
        assert get_employer_tier(p) == "free"

    def test_starter_active(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="starter", sub_status="active")
        assert get_employer_tier(p) == "starter"

    def test_pro_active(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="pro", sub_status="active")
        assert get_employer_tier(p) == "pro"

    def test_enterprise_trialing(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="enterprise", sub_status="trialing")
        assert get_employer_tier(p) == "enterprise"

    def test_canceled_falls_to_free(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="starter", sub_status="canceled")
        assert get_employer_tier(p) == "free"

    def test_none_tier_defaults_to_free(self, db_session):
        from app.services.billing import get_employer_tier

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="free")
        p.subscription_tier = None
        assert get_employer_tier(p) == "free"


class TestGetEmployerLimit:
    def test_active_jobs_free(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("free", "active_jobs") == 1

    def test_active_jobs_starter(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("starter", "active_jobs") == 5

    def test_active_jobs_pro(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("pro", "active_jobs") == 25

    def test_active_jobs_enterprise(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("enterprise", "active_jobs") == 999

    def test_candidate_views_free(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("free", "candidate_views_per_month") == 5

    def test_ai_parsing_starter(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("starter", "ai_job_parsing_per_month") == 10

    def test_multi_board_free(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("free", "multi_board_distribution") == ["google_jobs"]

    def test_cross_board_analytics_free(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("free", "cross_board_analytics") is False

    def test_bias_detection_starter(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("starter", "bias_detection") == "basic"

    def test_unknown_tier_defaults_to_free(self):
        from app.services.billing import get_employer_limit

        assert get_employer_limit("diamond", "active_jobs") == 1


class TestMaybeResetEmployerCounters:
    def test_resets_on_new_month(self, db_session):
        from app.services.billing import _maybe_reset_employer_counters

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=5)
        # Set reset_at to previous month
        p.usage_reset_at = datetime.now(UTC) - timedelta(days=35)
        db_session.flush()

        _maybe_reset_employer_counters(p, db_session)
        assert p.ai_parsing_used == 0

    def test_no_reset_same_month(self, db_session):
        from app.services.billing import _maybe_reset_employer_counters

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=3)
        _maybe_reset_employer_counters(p, db_session)
        assert p.ai_parsing_used == 3

    def test_reset_when_none(self, db_session):
        from app.services.billing import _maybe_reset_employer_counters

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=2)
        p.usage_reset_at = None
        db_session.flush()

        _maybe_reset_employer_counters(p, db_session)
        assert p.ai_parsing_used == 0


class TestCheckEmployerMonthlyLimit:
    def test_under_limit_passes(self, db_session):
        from app.services.billing import check_employer_monthly_limit

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=0)
        # Should not raise
        check_employer_monthly_limit(p, "ai_parsing_used", "ai_job_parsing_per_month", db_session)

    def test_at_limit_raises_429(self, db_session):
        from fastapi import HTTPException

        from app.services.billing import check_employer_monthly_limit

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="free", ai_parsing_used=1)
        with pytest.raises(HTTPException) as exc_info:
            check_employer_monthly_limit(p, "ai_parsing_used", "ai_job_parsing_per_month", db_session)
        assert exc_info.value.status_code == 429

    def test_unlimited_passes(self, db_session):
        from app.services.billing import check_employer_monthly_limit

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="pro", ai_parsing_used=500)
        # Pro = 999, should not raise
        check_employer_monthly_limit(p, "ai_parsing_used", "ai_job_parsing_per_month", db_session)


class TestIncrementEmployerCounter:
    def test_increments(self, db_session):
        from app.services.billing import increment_employer_counter

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=0)
        new_val = increment_employer_counter(p, "ai_parsing_used", db_session)
        assert new_val == 1
        assert p.ai_parsing_used == 1

    def test_increments_from_existing(self, db_session):
        from app.services.billing import increment_employer_counter

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, ai_parsing_used=5)
        new_val = increment_employer_counter(p, "ai_parsing_used", db_session)
        assert new_val == 6


class TestCheckEmployerFeature:
    def test_boolean_false(self, db_session):
        from app.services.billing import check_employer_feature

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="free")
        assert check_employer_feature(p, "salary_intelligence") is False

    def test_boolean_true(self, db_session):
        from app.services.billing import check_employer_feature

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="pro")
        assert check_employer_feature(p, "salary_intelligence") is True

    def test_string_feature(self, db_session):
        from app.services.billing import check_employer_feature

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="starter")
        val = check_employer_feature(p, "bias_detection")
        assert val == "basic"

    def test_list_feature(self, db_session):
        from app.services.billing import check_employer_feature

        user = _create_employer_user(db_session)
        p = _create_employer_profile(db_session, user, tier="free")
        val = check_employer_feature(p, "multi_board_distribution")
        assert val == ["google_jobs"]


# ============================================================================
# 2. ACCESS CONTROL
# ============================================================================


class TestAccessControl:
    def test_candidate_user_rejected(self, client, db_session):
        user = _create_employer_user(db_session, role="candidate")
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.get("/api/employer/profile")
        assert resp.status_code == 403

    def test_no_profile_auto_creates(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.get("/api/employer/profile")
        assert resp.status_code == 200

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/employer/profile")
        assert resp.status_code == 401


# ============================================================================
# 3. PROFILE CRUD
# ============================================================================


class TestProfileCRUD:
    def test_create_profile(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.post(
            "/api/employer/profile",
            json={"company_name": "Acme Inc", "company_size": "11-50"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "Acme Inc"
        assert data["subscription_tier"] == "free"

    def test_duplicate_profile_blocked(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user)
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.post(
            "/api/employer/profile",
            json={"company_name": "Dupe Corp"},
        )
        assert resp.status_code in (400, 409)

    def test_get_profile(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="starter")
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.get("/api/employer/profile")
        assert resp.status_code == 200
        assert resp.json()["subscription_tier"] == "starter"

    def test_patch_profile(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user)
        db_session.commit()
        _auth_cookie(client, user)
        resp = client.patch(
            "/api/employer/profile",
            json={"company_name": "Updated Corp"},
        )
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Updated Corp"


# ============================================================================
# 4. JOB LIMIT ENFORCEMENT
# ============================================================================


class TestJobLimitEnforcement:
    def test_free_tier_allows_1_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "Job 1", "description": "A test job description text."},
            )
        assert resp.status_code == 201

    def test_free_tier_blocks_2nd_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        _create_job(db_session, ep, status_val="active")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/employer/jobs",
            json={"title": "Job 2", "description": "Another test description."},
        )
        assert resp.status_code == 403
        assert "1 active job" in resp.json()["detail"]

    def test_starter_allows_5_jobs(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        for i in range(4):
            _create_job(db_session, ep, title=f"Job {i}", status_val="active")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "Job 5", "description": "Fifth job description."},
            )
        assert resp.status_code == 201

    def test_starter_blocks_6th_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        for i in range(5):
            _create_job(db_session, ep, title=f"Job {i}", status_val="active")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/employer/jobs",
            json={"title": "Job 6", "description": "Sixth job description."},
        )
        assert resp.status_code == 403

    def test_pro_allows_25_jobs(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        for i in range(24):
            _create_job(db_session, ep, title=f"Job {i}", status_val="active")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "Job 25", "description": "Twenty-fifth job."},
            )
        assert resp.status_code == 201

    def test_enterprise_unlimited(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="enterprise")
        # Create many jobs
        for i in range(50):
            _create_job(db_session, ep, title=f"Job {i}", status_val="active")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "Job 51", "description": "Still posting."},
            )
        assert resp.status_code == 201

    def test_closed_jobs_dont_count(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        _create_job(db_session, ep, status_val="closed")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "New Active", "description": "Active job."},
            )
        assert resp.status_code == 201


# ============================================================================
# 5. CANDIDATE VIEW LIMITS
# ============================================================================


class TestCandidateViewLimits:
    def test_free_allows_5_views(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        cp = _create_candidate_profile(db_session)
        # Pre-fill 4 views
        for _ in range(4):
            db_session.add(
                EmployerCandidateView(
                    employer_id=ep.id, candidate_id=cp.id, source="test"
                )
            )
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/employer/candidates/{cp.id}")
        assert resp.status_code == 200

    def test_free_blocks_6th_view(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        cp = _create_candidate_profile(db_session)
        for _ in range(5):
            db_session.add(
                EmployerCandidateView(
                    employer_id=ep.id, candidate_id=cp.id, source="test"
                )
            )
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/employer/candidates/{cp.id}")
        assert resp.status_code == 403
        assert "5 candidate views" in resp.json()["detail"]

    def test_starter_allows_50_views(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        cp = _create_candidate_profile(db_session)
        for _ in range(49):
            db_session.add(
                EmployerCandidateView(
                    employer_id=ep.id, candidate_id=cp.id, source="test"
                )
            )
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/employer/candidates/{cp.id}")
        assert resp.status_code == 200

    def test_view_creates_record(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        cp = _create_candidate_profile(db_session)
        db_session.commit()
        _auth_cookie(client, user)

        client.get(f"/api/employer/candidates/{cp.id}")
        from sqlalchemy import select, func

        count = db_session.execute(
            select(func.count(EmployerCandidateView.id)).where(
                EmployerCandidateView.employer_id == ep.id
            )
        ).scalar()
        assert count == 1


# ============================================================================
# 6. AI PARSING LIMITS
# ============================================================================


class TestAIParsingLimits:
    def test_free_allows_1_parse(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free", ai_parsing_used=0)
        db_session.commit()
        _auth_cookie(client, user)

        mock_parsed = {"title": "Test Job", "description": "A test."}
        with patch(
            "app.services.employer_job_parser.parse_job_document",
            return_value=mock_parsed,
        ):
            resp = client.post(
                "/api/employer/jobs/upload-document",
                files={"file": ("test.docx", b"fake", "application/octet-stream")},
            )
        assert resp.status_code == 200

    def test_free_blocks_2nd_parse(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free", ai_parsing_used=1)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/employer/jobs/upload-document",
            files={"file": ("test.docx", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 429
        assert "Monthly limit" in resp.json()["detail"]

    def test_pro_allows_unlimited(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="pro", ai_parsing_used=500)
        db_session.commit()
        _auth_cookie(client, user)

        mock_parsed = {"title": "Another Job", "description": "Pro parse."}
        with patch(
            "app.services.employer_job_parser.parse_job_document",
            return_value=mock_parsed,
        ):
            resp = client.post(
                "/api/employer/jobs/upload-document",
                files={"file": ("test.docx", b"fake", "application/octet-stream")},
            )
        assert resp.status_code == 200


# ============================================================================
# 7. DISTRIBUTION BOARD ALLOWLIST
# ============================================================================


class TestDistributionBoardAllowlist:
    def test_free_blocks_indeed(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            f"/api/distribution/jobs/{job.id}/distribute",
            json={"board_types": ["indeed"]},
        )
        assert resp.status_code == 403
        assert "google_jobs" in resp.json()["detail"]

    def test_free_allows_google_jobs(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.routers.distribution.distribute_job", return_value=[]):
            resp = client.post(
                f"/api/distribution/jobs/{job.id}/distribute",
                json={"board_types": ["google_jobs"]},
            )
        assert resp.status_code == 200

    def test_starter_allows_indeed(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.routers.distribution.distribute_job", return_value=[]):
            resp = client.post(
                f"/api/distribution/jobs/{job.id}/distribute",
                json={"board_types": ["indeed"]},
            )
        assert resp.status_code == 200

    def test_starter_blocks_glassdoor(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            f"/api/distribution/jobs/{job.id}/distribute",
            json={"board_types": ["glassdoor"]},
        )
        assert resp.status_code == 403

    def test_pro_allows_all_boards(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.routers.distribution.distribute_job", return_value=[]):
            resp = client.post(
                f"/api/distribution/jobs/{job.id}/distribute",
                json={"board_types": ["glassdoor", "linkedin", "indeed"]},
            )
        assert resp.status_code == 200


# ============================================================================
# 8. ANALYTICS TIER GATING
# ============================================================================


class TestAnalyticsTierGating:
    def test_overview_accessible_all_tiers(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.employer_analytics.get_overview", return_value={}):
            resp = client.get("/api/employer/analytics/overview")
        assert resp.status_code == 200

    def test_funnel_blocked_free(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/funnel")
        assert resp.status_code == 403
        assert "Starter or Pro" in resp.json()["detail"]

    def test_cost_blocked_free(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/cost")
        assert resp.status_code == 403

    def test_recommendations_blocked_free(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/recommendations")
        assert resp.status_code == 403

    def test_funnel_allowed_starter(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="starter")
        db_session.commit()
        _auth_cookie(client, user)

        with patch(
            "app.services.employer_analytics.get_funnel_by_board", return_value={}
        ):
            resp = client.get("/api/employer/analytics/funnel")
        assert resp.status_code == 200


# ============================================================================
# 9. BIAS DETECTION GATING
# ============================================================================


class TestBiasDetectionGating:
    def test_bias_scan_blocked_free(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="free")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/distribution/jobs/{job.id}/bias-scan")
        assert resp.status_code == 403
        assert "Starter or Pro" in resp.json()["detail"]

    def test_bias_scan_allowed_starter(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="starter")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        with patch(
            "app.services.job_bias_scanner.scan_job_for_bias", return_value={}
        ):
            resp = client.get(f"/api/distribution/jobs/{job.id}/bias-scan")
        assert resp.status_code == 200

    def test_dei_blocked_free(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/compliance/dei-recommendations/1")
        assert resp.status_code == 403

    def test_dei_allowed_pro(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="pro")
        db_session.commit()
        _auth_cookie(client, user)

        with patch(
            "app.services.dei_sourcing.analyze_candidate_pool_diversity",
            return_value={},
        ):
            resp = client.get("/api/employer/compliance/dei-recommendations/1")
        assert resp.status_code == 200


# ============================================================================
# 10. TEAM MANAGEMENT
# ============================================================================


class TestTeamManagement:
    def test_invite_team_member(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user)
        team_user = _create_employer_user(db_session, role="employer")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(
            "/api/employer/team/invite",
            json={"user_id": team_user.id, "role": "reviewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "invited"

    def test_list_team_members(self, client, db_session):
        from app.models.employer_team import EmployerTeamMember

        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user)
        other = _create_employer_user(db_session, role="employer")
        member = EmployerTeamMember(
            employer_id=ep.id, user_id=other.id, role="viewer"
        )
        db_session.add(member)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/team")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_team_member_role(self, client, db_session):
        from app.models.employer_team import EmployerTeamMember

        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user)
        other = _create_employer_user(db_session, role="employer")
        member = EmployerTeamMember(
            employer_id=ep.id, user_id=other.id, role="viewer"
        )
        db_session.add(member)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.patch(
            f"/api/employer/team/{member.id}",
            json={"role": "editor"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "editor"

    def test_update_team_member_invalid_role(self, client, db_session):
        from app.models.employer_team import EmployerTeamMember

        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user)
        other = _create_employer_user(db_session, role="employer")
        member = EmployerTeamMember(
            employer_id=ep.id, user_id=other.id, role="viewer"
        )
        db_session.add(member)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.patch(
            f"/api/employer/team/{member.id}",
            json={"role": "superadmin"},
        )
        assert resp.status_code == 400

    def test_remove_team_member(self, client, db_session):
        from app.models.employer_team import EmployerTeamMember

        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user)
        other = _create_employer_user(db_session, role="employer")
        member = EmployerTeamMember(
            employer_id=ep.id, user_id=other.id, role="viewer"
        )
        db_session.add(member)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.delete(f"/api/employer/team/{member.id}")
        assert resp.status_code == 204

    def test_remove_nonexistent_member(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.delete("/api/employer/team/99999")
        assert resp.status_code == 404


# ============================================================================
# 11. JOB CRUD
# ============================================================================


class TestJobCRUD:
    def test_create_and_list(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.post(
                "/api/employer/jobs",
                json={"title": "Dev", "description": "Build things."},
            )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        resp = client.get("/api/employer/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_single_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get(f"/api/employer/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Job"

    def test_update_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        job = _create_job(db_session, ep, status_val="draft")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.patch(
            f"/api/employer/jobs/{job.id}",
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_delete_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        job = _create_job(db_session, ep, status_val="draft")
        db_session.commit()
        _auth_cookie(client, user)

        with patch("app.services.queue.get_queue", return_value=MagicMock()):
            resp = client.delete(f"/api/employer/jobs/{job.id}")
        assert resp.status_code == 204

    def test_archive_job(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        ep = _create_employer_profile(db_session, user, tier="pro")
        job = _create_job(db_session, ep)
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.post(f"/api/employer/jobs/{job.id}/archive")
        assert resp.status_code == 200
        assert resp.json()["job_id"] == job.id

    def test_job_not_found(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="pro")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/jobs/99999")
        assert resp.status_code == 404


# ============================================================================
# 12. ANALYTICS SUMMARY
# ============================================================================


class TestAnalyticsSummary:
    def test_summary_returns_correct_view_limit(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="starter")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_views_limit"] == 50
        assert data["subscription_tier"] == "starter"

    def test_summary_free_tier_limit(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="free")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/summary")
        assert resp.status_code == 200
        assert resp.json()["candidate_views_limit"] == 5

    def test_summary_pro_tier_limit(self, client, db_session):
        user = _create_employer_user(db_session, role="employer")
        _create_employer_profile(db_session, user, tier="pro")
        db_session.commit()
        _auth_cookie(client, user)

        resp = client.get("/api/employer/analytics/summary")
        assert resp.status_code == 200
        assert resp.json()["candidate_views_limit"] == 200
