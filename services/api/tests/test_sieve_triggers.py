"""Tests for proactive Sieve trigger computation."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import all models so Base.metadata knows about them
import app.models as _models  # noqa: F401
from app.db.base import Base
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.match import Match
from app.models.tailored_resume import TailoredResume
from app.models.user import User
from app.services.sieve_triggers import (
    compute_all_triggers,
    compute_new_matches_trigger,
    compute_profile_completeness_trigger,
    compute_stale_application_trigger,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


# Raw SQL tables that cascade_delete references but have no ORM model
_EXTRA_TABLES_SQL = [
    "CREATE TABLE IF NOT EXISTS mjass_application_drafts (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS mjass_application_events (id INTEGER PRIMARY KEY, draft_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS consents (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS candidate_preferences_v1 (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS onboarding_state (id INTEGER PRIMARY KEY, user_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS parsed_resume_documents (id INTEGER PRIMARY KEY, resume_document_id INTEGER)",
]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        for sql in _EXTRA_TABLES_SQL:
            conn.execute(text(sql))
        conn.commit()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as s:
        yield s


def _create_user(session, email="trigger@example.com") -> User:
    user = User(email=email, password_hash="x")
    session.add(user)
    session.commit()
    return user


def _create_job(session) -> Job:
    job = Job(
        source="test",
        source_job_id="test-1",
        url="https://example.com/job/1",
        title="Software Engineer",
        company="TestCorp",
        location="Remote",
        description_text="A test job.",
        content_hash="abc123",
    )
    session.add(job)
    session.commit()
    return job


# ---------------------------------------------------------------------------
# Profile completeness trigger
# ---------------------------------------------------------------------------


def test_profile_completeness_trigger_fires(session) -> None:
    """User + candidate with 5/11 fields → trigger fires."""
    user = _create_user(session)
    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        phone="555-1234",
        desired_job_types=["Engineer"],
        desired_locations=[],  # empty = not counted
        # Missing: location_city, years_experience, desired_salary_min,
        # desired_salary_max, remote_preference, CandidateProfile
    )
    session.add(candidate)
    session.commit()

    trigger = compute_profile_completeness_trigger(user, session)
    assert trigger is not None
    assert trigger.id == "profile_incomplete_critical"
    assert trigger.priority == 1
    # 4 filled (first_name, last_name, phone, desired_job_types) out of 11 = 36%
    assert "36%" in trigger.message


def test_profile_completeness_trigger_suppressed(session) -> None:
    """User + candidate with 9/11 fields → no trigger (81% >= 70%)."""
    user = _create_user(session)
    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        phone="555-1234",
        location_city="Austin",
        years_experience=5,
        desired_job_types=["Engineer"],
        desired_locations=["Remote"],
        desired_salary_min=80000,
        remote_preference="remote",
        # Missing: desired_salary_max (1 missing from Candidate fields)
    )
    session.add(candidate)
    session.flush()

    # Add a CandidateProfile (resume uploaded) → 9/11 filled = 81%
    profile = CandidateProfile(
        user_id=user.id,
        version=1,
        profile_json={"skills": ["Python"]},
    )
    session.add(profile)
    session.commit()

    trigger = compute_profile_completeness_trigger(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# New matches trigger
# ---------------------------------------------------------------------------


def test_new_matches_trigger_fires(session) -> None:
    """Matches created in last 24h → trigger fires with count."""
    user = _create_user(session)
    job = _create_job(session)

    now = datetime.now(UTC)
    for i in range(3):
        match = Match(
            user_id=user.id,
            job_id=job.id,
            profile_version=1,
            match_score=80,
            interview_readiness_score=70,
            offer_probability=60,
            reasons={},
            created_at=now - timedelta(hours=i + 1),
        )
        session.add(match)
    session.commit()

    trigger = compute_new_matches_trigger(user, session)
    assert trigger is not None
    assert trigger.id == "new_matches_batch"
    assert trigger.priority == 2
    assert "3" in trigger.message


def test_new_matches_trigger_no_recent(session) -> None:
    """All matches older than 24h → no trigger."""
    user = _create_user(session)
    job = _create_job(session)

    old = datetime.now(UTC) - timedelta(hours=48)
    match = Match(
        user_id=user.id,
        job_id=job.id,
        profile_version=1,
        match_score=80,
        interview_readiness_score=70,
        offer_probability=60,
        reasons={},
        created_at=old,
    )
    session.add(match)
    session.commit()

    trigger = compute_new_matches_trigger(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Stale application trigger
# ---------------------------------------------------------------------------


def test_stale_application_trigger_fires(session) -> None:
    """Match with 'saved' status, created 5 days ago → trigger fires."""
    user = _create_user(session)
    job = _create_job(session)

    old = datetime.now(UTC) - timedelta(days=6)
    match = Match(
        user_id=user.id,
        job_id=job.id,
        profile_version=1,
        match_score=80,
        interview_readiness_score=70,
        offer_probability=60,
        reasons={},
        created_at=old,
        application_status="saved",
    )
    session.add(match)
    session.commit()

    trigger = compute_stale_application_trigger(user, session)
    assert trigger is not None
    assert trigger.id == "stale_saved_jobs"
    assert trigger.priority == 3
    assert "1" in trigger.message


def test_stale_application_trigger_recently_saved(session) -> None:
    """Match with 'saved' status, created 1 day ago → no trigger."""
    user = _create_user(session)
    job = _create_job(session)

    recent = datetime.now(UTC) - timedelta(days=1)
    match = Match(
        user_id=user.id,
        job_id=job.id,
        profile_version=1,
        match_score=80,
        interview_readiness_score=70,
        offer_probability=60,
        reasons={},
        created_at=recent,
        application_status="saved",
    )
    session.add(match)
    session.commit()

    trigger = compute_stale_application_trigger(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# compute_all_triggers
# ---------------------------------------------------------------------------


def test_compute_all_triggers_sorting(session) -> None:
    """Mix of triggers → sorted high > medium > low."""
    user = _create_user(session)
    job = _create_job(session)

    # Incomplete profile (will produce high-priority trigger)
    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        desired_job_types=[],
        desired_locations=[],
    )
    session.add(candidate)
    session.flush()

    now = datetime.now(UTC)

    # Recent match (medium-priority trigger)
    session.add(
        Match(
            user_id=user.id,
            job_id=job.id,
            profile_version=1,
            match_score=80,
            interview_readiness_score=70,
            offer_probability=60,
            reasons={},
            created_at=now - timedelta(hours=2),
        )
    )

    # Stale saved match (priority=3 trigger)
    session.add(
        Match(
            user_id=user.id,
            job_id=job.id,
            profile_version=1,
            match_score=75,
            interview_readiness_score=65,
            offer_probability=55,
            reasons={},
            created_at=now - timedelta(days=6),
            application_status="saved",
        )
    )
    session.commit()

    triggers = compute_all_triggers(user, session)
    assert len(triggers) == 3
    # Sorted by numeric priority (1 = highest)
    priorities = [t.priority for t in triggers]
    assert priorities == sorted(priorities)


def test_compute_all_triggers_empty(session) -> None:
    """Complete profile, old matches, no stale apps → empty list."""
    user = _create_user(session)
    job = _create_job(session)

    # Full profile (>=70% completeness → no profile trigger)
    candidate = Candidate(
        user_id=user.id,
        first_name="Jane",
        last_name="Doe",
        phone="555-1234",
        location_city="Austin",
        years_experience=5,
        desired_job_types=["Engineer"],
        desired_locations=["Remote"],
        desired_salary_min=80000,
        desired_salary_max=120000,
        remote_preference="remote",
    )
    session.add(candidate)
    session.flush()

    profile = CandidateProfile(
        user_id=user.id,
        version=1,
        profile_json={"skills": ["Python"]},
    )
    session.add(profile)
    session.flush()

    # Old match (>24h ago, not 'saved', with status) → suppresses multiple triggers
    old = datetime.now(UTC) - timedelta(hours=48)
    match = Match(
        user_id=user.id,
        job_id=job.id,
        profile_version=1,
        match_score=70,
        interview_readiness_score=70,
        offer_probability=60,
        reasons={},
        created_at=old,
        application_status="applied",
    )
    session.add(match)

    # Add a tailored resume so no_tailored_resumes trigger is suppressed
    tailored = TailoredResume(
        user_id=user.id,
        job_id=job.id,
        profile_version=1,
        docx_url="https://storage.example.com/test.docx",
        cover_letter_url="https://storage.example.com/test_cl.docx",
        change_log={},
    )
    session.add(tailored)
    session.commit()

    triggers = compute_all_triggers(user, session)
    assert triggers == []
