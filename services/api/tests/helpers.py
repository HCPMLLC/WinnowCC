"""Helper functions to create test data."""

from __future__ import annotations

from datetime import datetime, timedelta


def create_test_job(db_session, **overrides):
    """Create a job record for testing."""
    from app.models.job import Job

    defaults = {
        "source": "test",
        "source_job_id": f"test-{datetime.utcnow().timestamp()}",
        "url": "https://example.com/job/1",
        "title": "Senior Python Developer",
        "company": "Test Corp",
        "description_text": "Build awesome things with Python and FastAPI.",
        "location": "Remote",
        "remote_flag": True,
        "content_hash": f"hash-{datetime.utcnow().timestamp()}",
        "posted_at": datetime.utcnow() - timedelta(days=3),
    }
    defaults.update(overrides)
    job = Job(**defaults)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def create_test_match(db_session, user_id, job_id, **overrides):
    """Create a match record for testing."""
    from app.models.match import Match

    defaults = {
        "user_id": user_id,
        "job_id": job_id,
        "profile_version": 1,
        "match_score": 75,
        "interview_readiness_score": 68,
        "offer_probability": 45,
        "reasons": {"matched_skills": ["Python", "FastAPI"]},
    }
    defaults.update(overrides)
    match = Match(**defaults)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    return match


def create_test_profile(db_session, user_id, **overrides):
    """Create a candidate profile for testing."""
    from app.models.candidate_profile import CandidateProfile

    defaults = {
        "user_id": user_id,
        "version": 1,
        "profile_json": {
            "basics": {"name": "Test User", "email": "test@winnow.dev"},
            "experience": [],
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferences": {
                "target_titles": ["Backend Developer"],
                "remote_ok": True,
            },
        },
    }
    defaults.update(overrides)
    profile = CandidateProfile(**defaults)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile
