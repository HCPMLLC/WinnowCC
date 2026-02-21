"""Tests for the references CRUD router."""

from datetime import UTC, datetime

from app.models.candidate_profile import CandidateProfile


def test_list_references_empty(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()
    resp = client.get("/api/profile/references")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_reference(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()

    resp = client.post(
        "/api/profile/references",
        json={
            "name": "Jane Smith",
            "company": "Acme Corp",
            "phone": "(555) 111-2222",
            "relationship": "Supervisor",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Jane Smith"
    assert data["relationship"] == "Supervisor"
    assert data["id"].startswith("ref-")
    assert data["is_active"] is True


def test_add_reference_creates_new_profile_version(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()

    # Create initial profile
    client.put(
        "/api/profile",
        json={
            "profile_json": {
                "basics": {"name": "Test"},
                "skills": [],
                "preferences": {},
            }
        },
    )

    # Add reference (should create version 2)
    client.post(
        "/api/profile/references",
        json={
            "name": "Ref One",
            "company": "Co",
            "phone": "1234567890",
            "relationship": "Peer",
        },
    )

    # Check versions
    from sqlalchemy import select, func

    count = db_session.execute(
        select(func.count(CandidateProfile.id)).where(
            CandidateProfile.user_id == user.id
        )
    ).scalar()
    assert count >= 2


def test_update_reference(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()

    # Add
    resp = client.post(
        "/api/profile/references",
        json={
            "name": "John Doe",
            "company": "Tech Inc",
            "phone": "(555) 333-4444",
            "relationship": "Manager",
        },
    )
    ref_id = resp.json()["id"]

    # Update
    resp = client.put(
        f"/api/profile/references/{ref_id}",
        json={"company": "New Tech Inc"},
    )
    assert resp.status_code == 200
    assert resp.json()["company"] == "New Tech Inc"
    assert resp.json()["name"] == "John Doe"


def test_delete_reference(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()

    # Add
    resp = client.post(
        "/api/profile/references",
        json={
            "name": "Del Me",
            "company": "Corp",
            "phone": "0000000000",
            "relationship": "Peer",
        },
    )
    ref_id = resp.json()["id"]

    # Delete
    resp = client.delete(f"/api/profile/references/{ref_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Should not appear in list
    resp = client.get("/api/profile/references")
    assert all(r["id"] != ref_id for r in resp.json())


def test_has_references_flag_set_at_3(auth_client, db_session):
    client, user = auth_client
    user.onboarding_completed_at = datetime.now(UTC)
    db_session.commit()

    for i in range(3):
        client.post(
            "/api/profile/references",
            json={
                "name": f"Ref {i}",
                "company": f"Co {i}",
                "phone": f"555000000{i}",
                "relationship": "Peer",
            },
        )

    # Latest profile should have has_references=True
    from sqlalchemy import select

    profile = (
        db_session.execute(
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user.id)
            .order_by(CandidateProfile.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    assert profile is not None
    assert profile.has_references is True
