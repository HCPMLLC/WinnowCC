"""Tests for data export and account deletion endpoints."""

from __future__ import annotations

import io
import zipfile

from tests.helpers import create_test_job, create_test_match, create_test_profile

# ---------------------------------------------------------------------------
# Export preview
# ---------------------------------------------------------------------------


def test_export_preview_authenticated(auth_client):
    client, user = auth_client
    resp = client.get("/api/account/export/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert "profile_versions" in data
    assert "resume_documents" in data
    assert "matches" in data
    assert "tailored_resumes" in data
    assert "has_trust_record" in data


def test_export_preview_unauthenticated(client):
    resp = client.get("/api/account/export/preview")
    assert resp.status_code == 401


def test_export_preview_counts(auth_client, db_session):
    client, user = auth_client
    create_test_profile(db_session, user.id)
    job = create_test_job(db_session)
    create_test_match(db_session, user.id, job.id)

    resp = client.get("/api/account/export/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile_versions"] == 1
    assert data["matches"] == 1


# ---------------------------------------------------------------------------
# Export download
# ---------------------------------------------------------------------------


def test_export_data_blocked_free_tier(auth_client):
    """Free-tier users cannot export data."""
    client, user = auth_client
    resp = client.get("/api/account/export")
    assert resp.status_code == 403


def test_export_data_returns_zip(auth_client, db_session):
    client, user = auth_client
    # Grant starter tier so export is allowed
    from app.models.candidate import Candidate

    candidate = Candidate(user_id=user.id, plan_tier="starter")
    db_session.add(candidate)
    db_session.flush()

    resp = client.get("/api/account/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "winnow-export" in resp.headers.get("content-disposition", "")


def test_export_data_unauthenticated(client):
    resp = client.get("/api/account/export")
    assert resp.status_code == 401


def test_export_zip_contains_data(auth_client, db_session):
    client, user = auth_client
    # Grant starter tier so export is allowed
    from app.models.candidate import Candidate

    candidate = Candidate(user_id=user.id, plan_tier="starter")
    db_session.add(candidate)
    db_session.flush()

    create_test_profile(db_session, user.id)
    job = create_test_job(db_session)
    create_test_match(db_session, user.id, job.id)

    resp = client.get("/api/account/export")
    assert resp.status_code == 200

    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert any("account.json" in n for n in names)
        assert any("profile.json" in n for n in names)
        assert any("matches.json" in n for n in names)


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------


def test_delete_requires_auth(client):
    resp = client.post("/api/account/delete", json={"confirm": "DELETE MY ACCOUNT"})
    assert resp.status_code == 401


def test_delete_requires_confirmation(auth_client):
    client, user = auth_client
    resp = client.post("/api/account/delete", json={"confirm": "wrong"})
    assert resp.status_code == 400


def test_delete_wrong_confirmation(auth_client):
    client, user = auth_client
    resp = client.post("/api/account/delete", json={"confirm": "delete"})
    assert resp.status_code == 400
    assert "DELETE MY ACCOUNT" in resp.json()["detail"]


def test_delete_account_success(auth_client, db_session):
    client, user = auth_client
    user_id = user.id

    resp = client.post("/api/account/delete", json={"confirm": "DELETE MY ACCOUNT"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"
    assert "summary" in data

    # User should be gone
    from app.models.user import User

    assert db_session.query(User).filter(User.id == user_id).first() is None


def test_delete_cascades_all_data(auth_client, db_session):
    """Verify that deletion removes data from all related tables."""
    client, user = auth_client
    user_id = user.id

    create_test_profile(db_session, user_id)
    job = create_test_job(db_session)
    create_test_match(db_session, user_id, job.id)

    resp = client.post("/api/account/delete", json={"confirm": "DELETE MY ACCOUNT"})
    assert resp.status_code == 200

    from app.models.candidate_profile import CandidateProfile
    from app.models.match import Match

    assert (
        db_session.query(CandidateProfile)
        .filter(CandidateProfile.user_id == user_id)
        .count()
        == 0
    )
    assert db_session.query(Match).filter(Match.user_id == user_id).count() == 0
