from datetime import UTC, datetime


def test_get_profile_empty(auth_client, db_session):
    client, user = auth_client
    # Mark user as onboarded so the endpoint doesn't 403
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    response = client.get("/api/profile")
    assert response.status_code in (200, 404)


def test_update_profile(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    response = client.put(
        "/api/profile",
        json={
            "profile_json": {
                "basics": {"name": "Test User", "email": user.email},
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "preferences": {
                    "target_titles": ["Backend Developer"],
                    "remote_ok": True,
                    "salary_min": 100000,
                    "salary_max": 150000,
                },
            },
        },
    )
    assert response.status_code == 200


def test_profile_completeness(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    response = client.get("/api/profile/completeness")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data or "completeness_score" in data
