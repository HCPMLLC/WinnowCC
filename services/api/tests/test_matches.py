from datetime import UTC, datetime

from app.main import app
from app.services.trust_gate import require_allowed_trust
from tests.helpers import create_test_job, create_test_match, create_test_profile


def _noop_trust():
    """No-op replacement for require_allowed_trust."""
    return None


def test_get_matches_empty(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    app.dependency_overrides[require_allowed_trust] = _noop_trust
    try:
        response = client.get("/api/matches")
    finally:
        app.dependency_overrides.pop(require_allowed_trust, None)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_matches_unauthenticated(client):
    response = client.get("/api/matches")
    assert response.status_code == 401


def test_patch_match_status(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    create_test_profile(db_session, user.id)
    job = create_test_job(db_session)
    match = create_test_match(db_session, user.id, job.id)
    app.dependency_overrides[require_allowed_trust] = _noop_trust
    try:
        response = client.patch(
            f"/api/matches/{match.id}/status",
            json={"status": "applied"},
        )
    finally:
        app.dependency_overrides.pop(require_allowed_trust, None)
    assert response.status_code == 200
    assert response.json()["application_status"] == "applied"


def test_patch_match_referred(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    create_test_profile(db_session, user.id)
    job = create_test_job(db_session)
    match = create_test_match(db_session, user.id, job.id)
    app.dependency_overrides[require_allowed_trust] = _noop_trust
    try:
        response = client.patch(
            f"/api/matches/{match.id}/referred",
            json={"referred": True},
        )
    finally:
        app.dependency_overrides.pop(require_allowed_trust, None)
    assert response.status_code == 200
    assert response.json()["referred"] is True
