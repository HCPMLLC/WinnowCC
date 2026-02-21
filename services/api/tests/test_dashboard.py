from datetime import UTC, datetime


def test_dashboard_metrics_authenticated(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "profile_completeness_score" in data
    assert "qualified_jobs_count" in data


def test_dashboard_metrics_unauthenticated(client):
    response = client.get("/api/dashboard/metrics")
    assert response.status_code == 401
