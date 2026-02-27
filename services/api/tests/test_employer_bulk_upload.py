"""Tests for employer bulk job document upload."""

import io
from unittest.mock import patch

import pytest

from app.models.employer import EmployerJob, EmployerProfile
from app.models.user import User
from app.services.auth import hash_password, make_token


@pytest.fixture()
def employer_user(db_session):
    """Create an employer user with profile."""
    user = User(
        email="employer@winnow.dev",
        password_hash=hash_password("EmpPass123!"),
        is_admin=False,
        role="employer",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_employer(db_session, user, tier="free"):
    """Create an EmployerProfile with a given tier."""
    employer = EmployerProfile(
        user_id=user.id,
        company_name="Test Corp",
        subscription_tier=tier,
    )
    db_session.add(employer)
    db_session.commit()
    db_session.refresh(employer)
    return employer


def _employer_client(client, user):
    """Return client with auth cookie set."""
    token = make_token(user_id=user.id, email=user.email)
    client.cookies.set("rm_session", token)
    return client


def _fake_docx_bytes():
    """Return minimal bytes that look like a file (parser will be mocked)."""
    return b"fake docx content"


_PARSED_JOB = {
    "title": "Software Engineer",
    "description": "Build great software.",
    "requirements": "3+ years experience",
    "parsing_confidence": 0.85,
}


# --------------------------------------------------------------------------
# Batch limit enforcement
# --------------------------------------------------------------------------


class TestBatchLimits:
    """Batch size validation per tier."""

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_free_tier_allows_1_file(
        self, mock_parse, client, employer_user, db_session
    ):
        _make_employer(db_session, employer_user, "free")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    "job.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 1

    def test_free_tier_rejects_2_files(self, client, employer_user, db_session):
        _make_employer(db_session, employer_user, "free")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    "job1.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            ),
            (
                "files",
                (
                    "job2.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            ),
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 400
        assert "1 file(s) per batch" in resp.json()["detail"]

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_starter_tier_allows_5_files(
        self, mock_parse, client, employer_user, db_session
    ):
        _make_employer(db_session, employer_user, "starter")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(5)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        assert resp.json()["total_succeeded"] == 5

    def test_starter_tier_rejects_6_files(self, client, employer_user, db_session):
        _make_employer(db_session, employer_user, "starter")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(6)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 400
        assert "5 file(s) per batch" in resp.json()["detail"]

    def test_pro_tier_rejects_11_files(self, client, employer_user, db_session):
        _make_employer(db_session, employer_user, "pro")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(11)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 400
        assert "10 file(s) per batch" in resp.json()["detail"]
        assert "XML/JSON" in resp.json()["detail"]


# --------------------------------------------------------------------------
# Quota enforcement for capped tiers
# --------------------------------------------------------------------------


class TestQuotaEnforcement:
    """Total job limit enforcement for free/starter tiers."""

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_starter_with_existing_jobs_clamps(
        self, mock_parse, client, employer_user, db_session
    ):
        """Starter tier with 3 existing jobs can only create 2 more."""
        employer = _make_employer(db_session, employer_user, "starter")
        # Create 3 existing jobs
        for i in range(3):
            db_session.add(
                EmployerJob(
                    employer_id=employer.id,
                    title=f"Existing Job {i}",
                    description="Existing job description.",
                    status="active",
                )
            )
        db_session.commit()

        c = _employer_client(client, employer_user)
        files = [
            (
                "files",
                (
                    f"new{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(5)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        # Only 2 should succeed (5 total limit - 3 existing = 2 remaining)
        assert data["total_succeeded"] == 2
        assert data["total_failed"] == 3
        # The 3 excess should show quota error
        failed = [r for r in data["results"] if not r["success"]]
        assert len(failed) == 3
        assert "limit reached" in failed[0]["error"].lower()

    def test_free_tier_no_quota_remaining(self, client, employer_user, db_session):
        """Free tier with 1 existing job has no quota left."""
        employer = _make_employer(db_session, employer_user, "free")
        db_session.add(
            EmployerJob(
                employer_id=employer.id,
                title="Existing Job",
                description="Existing job description.",
                status="draft",
            )
        )
        db_session.commit()

        c = _employer_client(client, employer_user)
        files = [
            (
                "files",
                (
                    "new.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 400
        assert "limit reached" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------
# Successful upload and job creation
# --------------------------------------------------------------------------


class TestBulkUploadSuccess:
    """Verify EmployerJob records are created on success."""

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_creates_employer_jobs(self, mock_parse, client, employer_user, db_session):
        employer = _make_employer(db_session, employer_user, "pro")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(3)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 3

        # Verify DB records
        jobs = db_session.query(EmployerJob).filter_by(employer_id=employer.id).all()
        assert len(jobs) == 3
        for job in jobs:
            assert job.status == "draft"
            assert job.parsed_from_document is True
            assert job.title == "Software Engineer"


# --------------------------------------------------------------------------
# Partial failure
# --------------------------------------------------------------------------


class TestPartialFailure:
    """Some files parse, some don't."""

    def test_mix_of_success_and_failure(self, client, employer_user, db_session):
        _make_employer(db_session, employer_user, "pro")
        c = _employer_client(client, employer_user)

        good_parsed = {
            "title": "Good Job",
            "description": "A good job.",
            "parsing_confidence": 0.9,
        }
        bad_parsed: dict = {}  # no title → failure

        call_count = {"n": 0}

        def alternating_parse(path):
            call_count["n"] += 1
            if call_count["n"] % 2 == 1:
                return good_parsed
            return bad_parsed

        with patch(
            "app.services.employer_job_parser.parse_job_document",
            side_effect=alternating_parse,
        ):
            files = [
                (
                    "files",
                    (
                        "good1.docx",
                        io.BytesIO(_fake_docx_bytes()),
                        "application/octet-stream",
                    ),
                ),
                (
                    "files",
                    (
                        "bad1.docx",
                        io.BytesIO(_fake_docx_bytes()),
                        "application/octet-stream",
                    ),
                ),
                (
                    "files",
                    (
                        "good2.docx",
                        io.BytesIO(_fake_docx_bytes()),
                        "application/octet-stream",
                    ),
                ),
            ]
            resp = c.post("/api/employer/jobs/upload-documents", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_succeeded"] == 2
        assert data["total_failed"] == 1

        results = data["results"]
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    def test_unsupported_file_type(self, client, employer_user, db_session):
        _make_employer(db_session, employer_user, "pro")
        c = _employer_client(client, employer_user)

        files = [
            ("files", ("image.png", io.BytesIO(b"fake png"), "image/png")),
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_failed"] == 1
        assert "Unsupported file type" in data["results"][0]["error"]


# --------------------------------------------------------------------------
# Upgrade recommendations
# --------------------------------------------------------------------------


class TestUpgradeRecommendation:
    """Verify upgrade messaging appears at the right times."""

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_pro_at_batch_limit_gets_recommendation(
        self, mock_parse, client, employer_user, db_session
    ):
        _make_employer(db_session, employer_user, "pro")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(10)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["upgrade_recommendation"] is not None
        assert "XML/JSON" in data["upgrade_recommendation"]

    @patch(
        "app.services.employer_job_parser.parse_job_document",
        return_value=_PARSED_JOB,
    )
    def test_starter_at_limit_gets_upgrade_message(
        self, mock_parse, client, employer_user, db_session
    ):
        _make_employer(db_session, employer_user, "starter")
        c = _employer_client(client, employer_user)

        files = [
            (
                "files",
                (
                    f"job{i}.docx",
                    io.BytesIO(_fake_docx_bytes()),
                    "application/octet-stream",
                ),
            )
            for i in range(5)
        ]
        resp = c.post("/api/employer/jobs/upload-documents", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["upgrade_recommendation"] is not None
        assert "Upgrade" in data["upgrade_recommendation"]
