"""Tests for proactive Sieve trigger computation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import PropertyMock, patch

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
from app.models.user import User
from app.models.introduction_request import IntroductionRequest
from app.models.recruiter import RecruiterProfile
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.services.sieve_triggers import (
    _recruiter_empty_pipeline,
    _recruiter_jobs_no_candidates,
    _recruiter_stale_intros,
    _recruiter_stale_sourced,
    _recruiter_trial_expiring,
    _recruiter_usage_limit,
    compute_all_triggers,
    compute_new_matches_trigger,
    compute_profile_completeness_trigger,
    compute_recruiter_triggers,
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
    """Complete profile, no recent matches, no stale apps → empty list."""
    user = _create_user(session)

    # Full profile
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
    session.commit()

    triggers = compute_all_triggers(user, session)
    assert triggers == []


# ---------------------------------------------------------------------------
# Recruiter trigger helpers
# ---------------------------------------------------------------------------


def _create_recruiter_profile(
    session, user, *, tier="trial", trial_days_left=14
) -> RecruiterProfile:
    now = datetime.now(UTC)
    profile = RecruiterProfile(
        user_id=user.id,
        company_name="TestStaff Inc",
        subscription_tier=tier,
        subscription_status="trialing" if tier == "trial" else "active",
        trial_started_at=now - timedelta(days=14 - trial_days_left),
        trial_ends_at=now + timedelta(days=trial_days_left) if tier == "trial" else None,
    )
    session.add(profile)
    session.flush()
    return profile


# ---------------------------------------------------------------------------
# Recruiter: trial expiring trigger
# ---------------------------------------------------------------------------


def test_recruiter_trial_expiring_fires(session) -> None:
    """Trial ending in 2 days → trigger fires."""
    user = _create_user(session, email="rec1@example.com")
    _create_recruiter_profile(session, user, trial_days_left=2)
    session.commit()

    # SQLite strips timezone info; mock the model properties to avoid tz mismatch
    with patch.object(
        RecruiterProfile, "is_trial_active", new_callable=PropertyMock, return_value=True
    ), patch.object(
        RecruiterProfile, "trial_days_remaining", new_callable=PropertyMock, return_value=2
    ):
        trigger = _recruiter_trial_expiring(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_trial_expiring"
    assert trigger.priority == 1
    assert "2 days" in trigger.message


def test_recruiter_trial_expiring_suppressed(session) -> None:
    """Trial ending in 10 days → no trigger."""
    user = _create_user(session, email="rec2@example.com")
    _create_recruiter_profile(session, user, trial_days_left=10)
    session.commit()

    with patch.object(
        RecruiterProfile, "is_trial_active", new_callable=PropertyMock, return_value=True
    ), patch.object(
        RecruiterProfile, "trial_days_remaining", new_callable=PropertyMock, return_value=10
    ):
        trigger = _recruiter_trial_expiring(user, session)
    assert trigger is None


def test_recruiter_trial_expiring_not_trial(session) -> None:
    """Paid plan (solo) → no trigger."""
    user = _create_user(session, email="rec3@example.com")
    _create_recruiter_profile(session, user, tier="solo")
    session.commit()

    trigger = _recruiter_trial_expiring(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Recruiter: empty pipeline trigger
# ---------------------------------------------------------------------------


def test_recruiter_empty_pipeline_fires(session) -> None:
    """0 pipeline candidates → trigger fires."""
    user = _create_user(session, email="rec4@example.com")
    _create_recruiter_profile(session, user)
    session.commit()

    trigger = _recruiter_empty_pipeline(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_empty_pipeline"
    assert trigger.priority == 1


def test_recruiter_empty_pipeline_suppressed(session) -> None:
    """1+ pipeline candidates → no trigger."""
    user = _create_user(session, email="rec5@example.com")
    profile = _create_recruiter_profile(session, user)
    session.add(
        RecruiterPipelineCandidate(
            recruiter_profile_id=profile.id,
            stage="sourced",
        )
    )
    session.commit()

    trigger = _recruiter_empty_pipeline(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Recruiter: stale sourced trigger
# ---------------------------------------------------------------------------


def test_recruiter_stale_sourced_fires(session) -> None:
    """3 candidates in sourced/screening for 6 days → trigger fires."""
    user = _create_user(session, email="rec6@example.com")
    profile = _create_recruiter_profile(session, user)
    old = datetime.now(UTC) - timedelta(days=6)
    for i in range(3):
        session.add(
            RecruiterPipelineCandidate(
                recruiter_profile_id=profile.id,
                stage="sourced" if i % 2 == 0 else "screening",
                updated_at=old,
            )
        )
    session.commit()

    trigger = _recruiter_stale_sourced(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_stale_sourced"
    assert trigger.priority == 2
    assert "3" in trigger.message


def test_recruiter_stale_sourced_suppressed_few(session) -> None:
    """Only 2 stale candidates → no trigger (threshold is 3)."""
    user = _create_user(session, email="rec7@example.com")
    profile = _create_recruiter_profile(session, user)
    old = datetime.now(UTC) - timedelta(days=6)
    for _ in range(2):
        session.add(
            RecruiterPipelineCandidate(
                recruiter_profile_id=profile.id,
                stage="sourced",
                updated_at=old,
            )
        )
    session.commit()

    trigger = _recruiter_stale_sourced(user, session)
    assert trigger is None


def test_recruiter_stale_sourced_suppressed_recent(session) -> None:
    """3 candidates in sourced but updated recently → no trigger."""
    user = _create_user(session, email="rec8@example.com")
    profile = _create_recruiter_profile(session, user)
    recent = datetime.now(UTC) - timedelta(days=1)
    for _ in range(3):
        session.add(
            RecruiterPipelineCandidate(
                recruiter_profile_id=profile.id,
                stage="sourced",
                updated_at=recent,
            )
        )
    session.commit()

    trigger = _recruiter_stale_sourced(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Recruiter: jobs with no candidates trigger
# ---------------------------------------------------------------------------


def test_recruiter_jobs_no_candidates_fires(session) -> None:
    """Active job with 0 pipeline candidates → trigger fires."""
    user = _create_user(session, email="rec9@example.com")
    profile = _create_recruiter_profile(session, user)
    session.add(
        RecruiterJob(
            recruiter_profile_id=profile.id,
            title="Senior Engineer",
            description="Build stuff",
            status="active",
        )
    )
    session.commit()

    trigger = _recruiter_jobs_no_candidates(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_jobs_no_candidates"
    assert trigger.priority == 2
    assert "Senior Engineer" in trigger.message


def test_recruiter_jobs_no_candidates_suppressed(session) -> None:
    """Active job with pipeline candidates → no trigger."""
    user = _create_user(session, email="rec10@example.com")
    profile = _create_recruiter_profile(session, user)
    job = RecruiterJob(
        recruiter_profile_id=profile.id,
        title="Senior Engineer",
        description="Build stuff",
        status="active",
    )
    session.add(job)
    session.flush()
    session.add(
        RecruiterPipelineCandidate(
            recruiter_profile_id=profile.id,
            recruiter_job_id=job.id,
            stage="sourced",
        )
    )
    session.commit()

    trigger = _recruiter_jobs_no_candidates(user, session)
    assert trigger is None


def test_recruiter_jobs_no_candidates_draft_ignored(session) -> None:
    """Draft job with 0 candidates → no trigger (only active jobs)."""
    user = _create_user(session, email="rec11@example.com")
    profile = _create_recruiter_profile(session, user)
    session.add(
        RecruiterJob(
            recruiter_profile_id=profile.id,
            title="Draft Role",
            description="Not posted yet",
            status="draft",
        )
    )
    session.commit()

    trigger = _recruiter_jobs_no_candidates(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Recruiter: stale intros trigger
# ---------------------------------------------------------------------------


def test_recruiter_stale_intros_fires(session) -> None:
    """3 pending intros older than 5 days → trigger fires."""
    user = _create_user(session, email="rec12@example.com")
    profile = _create_recruiter_profile(session, user)

    # Need a candidate profile for the FK
    candidate_user = _create_user(session, email="cand_intro@example.com")
    cp = CandidateProfile(
        user_id=candidate_user.id, version=1, profile_json={}
    )
    session.add(cp)
    session.flush()

    old = datetime.now(UTC) - timedelta(days=7)
    for _ in range(3):
        session.add(
            IntroductionRequest(
                recruiter_profile_id=profile.id,
                candidate_profile_id=cp.id,
                message="Hi there",
                status="pending",
                created_at=old,
            )
        )
    session.commit()

    trigger = _recruiter_stale_intros(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_stale_intros"
    assert trigger.priority == 2
    assert "3" in trigger.message


def test_recruiter_stale_intros_suppressed_recent(session) -> None:
    """3 pending intros created 1 day ago → no trigger."""
    user = _create_user(session, email="rec13@example.com")
    profile = _create_recruiter_profile(session, user)

    candidate_user = _create_user(session, email="cand_intro2@example.com")
    cp = CandidateProfile(
        user_id=candidate_user.id, version=1, profile_json={}
    )
    session.add(cp)
    session.flush()

    recent = datetime.now(UTC) - timedelta(days=1)
    for _ in range(3):
        session.add(
            IntroductionRequest(
                recruiter_profile_id=profile.id,
                candidate_profile_id=cp.id,
                message="Hi",
                status="pending",
                created_at=recent,
            )
        )
    session.commit()

    trigger = _recruiter_stale_intros(user, session)
    assert trigger is None


def test_recruiter_stale_intros_suppressed_few(session) -> None:
    """Only 2 stale pending intros → no trigger (threshold is 3)."""
    user = _create_user(session, email="rec14@example.com")
    profile = _create_recruiter_profile(session, user)

    candidate_user = _create_user(session, email="cand_intro3@example.com")
    cp = CandidateProfile(
        user_id=candidate_user.id, version=1, profile_json={}
    )
    session.add(cp)
    session.flush()

    old = datetime.now(UTC) - timedelta(days=7)
    for _ in range(2):
        session.add(
            IntroductionRequest(
                recruiter_profile_id=profile.id,
                candidate_profile_id=cp.id,
                message="Hi",
                status="pending",
                created_at=old,
            )
        )
    session.commit()

    trigger = _recruiter_stale_intros(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# Recruiter: usage limit trigger
# ---------------------------------------------------------------------------


def test_recruiter_usage_limit_fires(session) -> None:
    """Solo tier with 18/20 briefs used (90%) → trigger fires."""
    user = _create_user(session, email="rec15@example.com")
    profile = _create_recruiter_profile(session, user, tier="solo")
    profile.candidate_briefs_used = 18  # limit is 20 for solo
    session.commit()

    trigger = _recruiter_usage_limit(user, session)
    assert trigger is not None
    assert trigger.id == "recruiter_usage_limit"
    assert trigger.priority == 3
    assert "18/20" in trigger.message
    assert "briefs" in trigger.message


def test_recruiter_usage_limit_suppressed_low(session) -> None:
    """Solo tier with 5/20 briefs used (25%) → no trigger."""
    user = _create_user(session, email="rec16@example.com")
    profile = _create_recruiter_profile(session, user, tier="solo")
    profile.candidate_briefs_used = 5
    session.commit()

    trigger = _recruiter_usage_limit(user, session)
    assert trigger is None


def test_recruiter_usage_limit_suppressed_unlimited(session) -> None:
    """Agency tier with all counters at zero → no trigger (most limits are 999)."""
    user = _create_user(session, email="rec17@example.com")
    _create_recruiter_profile(session, user, tier="agency")
    # All usage counters default to 0, well below 80% of any limit
    session.commit()

    trigger = _recruiter_usage_limit(user, session)
    assert trigger is None


# ---------------------------------------------------------------------------
# compute_recruiter_triggers (integration)
# ---------------------------------------------------------------------------


def test_compute_recruiter_triggers_sorting(session) -> None:
    """Multiple triggers fire → sorted by priority, capped at 3."""
    user = _create_user(session, email="rec18@example.com")
    profile = _create_recruiter_profile(session, user, tier="solo")
    # Empty pipeline → priority 1
    # Active job with no candidates → priority 2
    # Usage at 80%+ → priority 3
    session.add(
        RecruiterJob(
            recruiter_profile_id=profile.id,
            title="DevOps Lead",
            description="Lead DevOps",
            status="active",
        )
    )
    profile.candidate_briefs_used = 18  # 18/20 = 90% for solo tier
    session.commit()

    triggers = compute_recruiter_triggers(user, session)
    assert len(triggers) == 3
    priorities = [t.priority for t in triggers]
    assert priorities == sorted(priorities)
    trigger_ids = {t.id for t in triggers}
    assert "recruiter_empty_pipeline" in trigger_ids
    assert "recruiter_jobs_no_candidates" in trigger_ids
    assert "recruiter_usage_limit" in trigger_ids


def test_compute_recruiter_triggers_dismissal(session) -> None:
    """Dismissed trigger IDs are excluded from results."""
    user = _create_user(session, email="rec19@example.com")
    _create_recruiter_profile(session, user)
    session.commit()

    # Without dismissal — empty pipeline fires
    triggers = compute_recruiter_triggers(user, session)
    ids = {t.id for t in triggers}
    assert "recruiter_empty_pipeline" in ids

    # With dismissal
    triggers = compute_recruiter_triggers(
        user, session, dismissed_ids=["recruiter_empty_pipeline"]
    )
    ids = {t.id for t in triggers}
    assert "recruiter_empty_pipeline" not in ids


def test_compute_recruiter_triggers_empty(session) -> None:
    """Paid recruiter with candidates and no issues → no triggers."""
    user = _create_user(session, email="rec20@example.com")
    profile = _create_recruiter_profile(session, user, tier="agency")
    # Add a pipeline candidate so empty_pipeline doesn't fire
    session.add(
        RecruiterPipelineCandidate(
            recruiter_profile_id=profile.id,
            stage="interview",
        )
    )
    session.commit()

    triggers = compute_recruiter_triggers(user, session)
    assert triggers == []
