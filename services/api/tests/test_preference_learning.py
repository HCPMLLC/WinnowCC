"""Tests for preference learning service."""

import pytest

from app.models.candidate_preference_weights import CandidatePreferenceWeights
from app.services.preference_learning import (
    FULL_CONFIDENCE_EVENTS,
    MAX_WEIGHT,
    MIN_EVENTS_FOR_ADJUSTMENT,
    MIN_WEIGHT,
    _clamp,
    extract_preference_signals,
    merge_signals,
    recalculate_weights,
)


class FakeJob:
    def __init__(self, **kwargs):
        self.title = kwargs.get("title", "Software Engineer")
        self.description_text = kwargs.get("description_text", "Build stuff")
        self.remote_flag = kwargs.get("remote_flag", False)
        self.location = kwargs.get("location", "New York, NY")
        self.salary_min = kwargs.get("salary_min", None)
        self.salary_max = kwargs.get("salary_max", None)
        self.source = kwargs.get("source", "board")


class FakeMatch:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.user_id = kwargs.get("user_id", 1)
        self.job_id = kwargs.get("job_id", 1)
        self.application_status = kwargs.get("application_status", "saved")


class FakeParsedDetail:
    def __init__(self, **kwargs):
        self.required_skills = kwargs.get("required_skills", ["Python", "FastAPI"])
        self.preferred_skills = kwargs.get("preferred_skills", ["Docker"])


class FakePrefs:
    """Lightweight stand-in for CandidatePreferenceWeights."""
    def __init__(self):
        self.skill_weight = 1.0
        self.title_weight = 1.0
        self.location_weight = 1.0
        self.salary_weight = 1.0
        self.years_weight = 1.0
        self.learned_signals = {}
        self.positive_events = 0
        self.negative_events = 0
        self.last_recalculated_at = None


# ---------------------------------------------------------------------------
# extract_preference_signals
# ---------------------------------------------------------------------------

def test_extract_signals_saved():
    match = FakeMatch()
    job = FakeJob(salary_min=80000, salary_max=120000, remote_flag=True)
    parsed = FakeParsedDetail()

    signals = extract_preference_signals(match, job, parsed, "saved")
    assert signals["strength"] == 1.0
    assert signals["status"] == "saved"
    assert "python" in signals["skills"]
    assert "fastapi" in signals["skills"]
    assert "docker" in signals["skills"]
    assert signals["is_remote"] is True
    assert signals["salary_min"] == 80000
    assert signals["salary_max"] == 120000


def test_extract_signals_applied():
    signals = extract_preference_signals(
        FakeMatch(), FakeJob(), FakeParsedDetail(), "applied"
    )
    assert signals["strength"] == 2.0


def test_extract_signals_rejected():
    signals = extract_preference_signals(
        FakeMatch(), FakeJob(), FakeParsedDetail(), "rejected"
    )
    assert signals["strength"] == -0.5


def test_extract_signals_unknown_status():
    signals = extract_preference_signals(
        FakeMatch(), FakeJob(), FakeParsedDetail(), "unknown"
    )
    assert signals == {}


def test_extract_signals_no_parsed_detail():
    signals = extract_preference_signals(
        FakeMatch(), FakeJob(), None, "saved"
    )
    assert "skills" not in signals  # no parsed detail → no skills


def test_extract_signals_title_tokens():
    job = FakeJob(title="Senior Data Engineer")
    signals = extract_preference_signals(FakeMatch(), job, None, "saved")
    assert "data" in signals["title_tokens"]
    assert "engineer" in signals["title_tokens"]
    # "senior" is in the stop list
    assert "senior" not in signals["title_tokens"]


# ---------------------------------------------------------------------------
# merge_signals
# ---------------------------------------------------------------------------

def test_merge_signals_accumulates_skills():
    prefs = FakePrefs()
    signals = {"strength": 2.0, "skills": ["python", "fastapi"]}
    merge_signals(prefs, signals, "applied")

    assert prefs.learned_signals["skill_counts"]["python"] == 2.0
    assert prefs.learned_signals["skill_counts"]["fastapi"] == 2.0
    assert prefs.positive_events == 1


def test_merge_signals_multiple_events():
    prefs = FakePrefs()
    merge_signals(prefs, {"strength": 1.0, "skills": ["python"]}, "saved")
    merge_signals(prefs, {"strength": 2.0, "skills": ["python", "go"]}, "applied")

    assert prefs.learned_signals["skill_counts"]["python"] == 3.0
    assert prefs.learned_signals["skill_counts"]["go"] == 2.0
    assert prefs.positive_events == 2


def test_merge_signals_rejected_is_negative():
    prefs = FakePrefs()
    merge_signals(prefs, {"strength": -0.5, "skills": ["cobol"]}, "rejected")

    assert prefs.negative_events == 1
    assert prefs.positive_events == 0
    assert prefs.learned_signals["skill_counts"]["cobol"] == -0.5


def test_merge_signals_remote_counts():
    prefs = FakePrefs()
    merge_signals(prefs, {"strength": 1.0, "is_remote": True}, "saved")
    merge_signals(prefs, {"strength": 2.0, "is_remote": False}, "applied")

    assert prefs.learned_signals["remote_counts"]["remote"] == 1.0
    assert prefs.learned_signals["remote_counts"]["onsite"] == 2.0


def test_merge_signals_salary():
    prefs = FakePrefs()
    merge_signals(
        prefs,
        {"strength": 1.0, "salary_min": 80000, "salary_max": 120000},
        "saved",
    )
    assert len(prefs.learned_signals["salary_signals"]) == 1
    assert prefs.learned_signals["salary_signals"][0]["min"] == 80000


def test_merge_empty_signals():
    prefs = FakePrefs()
    merge_signals(prefs, {}, "saved")
    assert prefs.positive_events == 0  # empty signals → no increment


# ---------------------------------------------------------------------------
# recalculate_weights
# ---------------------------------------------------------------------------

def test_cold_start_no_adjustment():
    """Weights stay at 1.0 with fewer than MIN_EVENTS_FOR_ADJUSTMENT events."""
    prefs = FakePrefs()
    prefs.positive_events = MIN_EVENTS_FOR_ADJUSTMENT - 1
    prefs.learned_signals = {"skill_counts": {"python": 5.0}}
    recalculate_weights(prefs)
    assert prefs.skill_weight == 1.0


def test_weights_adjust_after_enough_events():
    """After MIN_EVENTS, weights should shift from 1.0."""
    prefs = FakePrefs()
    prefs.positive_events = FULL_CONFIDENCE_EVENTS
    prefs.negative_events = 0
    prefs.learned_signals = {
        "skill_counts": {"python": 20.0, "fastapi": 15.0},
        "title_counts": {"engineer": 10.0, "data": 5.0},
        "remote_counts": {"remote": 12.0, "onsite": 1.0},
        "salary_signals": [
            {"min": 80000, "max": 120000, "strength": 2.0},
            {"min": 90000, "max": 130000, "strength": 3.0},
        ],
    }
    recalculate_weights(prefs)

    # Weights should be > 1.0 given strong positive signals
    assert prefs.skill_weight > 1.0
    assert prefs.title_weight > 1.0
    assert prefs.location_weight > 1.0
    assert prefs.salary_weight > 1.0
    # Years always stays 1.0
    assert prefs.years_weight == 1.0


def test_weights_clamped():
    """All weights must stay within [MIN_WEIGHT, MAX_WEIGHT]."""
    prefs = FakePrefs()
    prefs.positive_events = 100
    prefs.negative_events = 0
    prefs.learned_signals = {
        "skill_counts": {"python": 9999.0},
        "title_counts": {"engineer": 9999.0},
        "remote_counts": {"remote": 9999.0, "onsite": 0.0},
        "salary_signals": [{"min": 100000, "max": 200000, "strength": 100.0}] * 20,
    }
    recalculate_weights(prefs)

    assert MIN_WEIGHT <= prefs.skill_weight <= MAX_WEIGHT
    assert MIN_WEIGHT <= prefs.title_weight <= MAX_WEIGHT
    assert MIN_WEIGHT <= prefs.location_weight <= MAX_WEIGHT
    assert MIN_WEIGHT <= prefs.salary_weight <= MAX_WEIGHT
    assert prefs.years_weight == 1.0


def test_recalculate_sets_timestamp():
    prefs = FakePrefs()
    prefs.positive_events = MIN_EVENTS_FOR_ADJUSTMENT
    prefs.learned_signals = {"skill_counts": {"python": 3.0}}
    recalculate_weights(prefs)
    assert prefs.last_recalculated_at is not None


# ---------------------------------------------------------------------------
# _clamp
# ---------------------------------------------------------------------------

def test_clamp_within_bounds():
    assert _clamp(1.0) == 1.0
    assert _clamp(1.15) == 1.15


def test_clamp_below_min():
    assert _clamp(0.5) == MIN_WEIGHT


def test_clamp_above_max():
    assert _clamp(1.5) == MAX_WEIGHT
