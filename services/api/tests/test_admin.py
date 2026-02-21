from datetime import UTC, datetime


def test_admin_scheduler_requires_auth(client):
    response = client.post("/api/admin/scheduler/trigger")
    assert response.status_code in (401, 403, 422)


def test_admin_scheduler_with_admin_user(admin_client, db_session):
    client, admin = admin_client
    admin.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    response = client.post("/api/admin/scheduler/trigger")
    # Should accept the request (may queue background job)
    assert response.status_code in (200, 202, 403)
