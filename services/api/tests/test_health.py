def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_checks_db(client):
    response = client.get("/ready")
    assert response.status_code == 200
    # Should be "ok" or "degraded"
    assert response.json()["status"] in ("ok", "degraded")
