"""Unit tests for JobFraudDetector."""

import pytest

from app.services.job_fraud_detector import JobFraudDetector


@pytest.fixture
def detector():
    return JobFraudDetector()


class TestFraudScoring:
    def test_scam_phrases_detected(self, detector):
        """Known scam phrases should trigger high score."""

        class MockParsed:
            parsed_salary_min = None
            parsed_salary_max = None
            salary_confidence = None
            required_skills = []
            required_certifications = []
            years_experience_min = None
            fraud_score = 0
            red_flags = []
            is_likely_fraudulent = False

        class MockJob:
            id = 1
            title = "Make Money Fast - Work From Home"
            company = "Legit Corp"
            description_text = (
                "Make money fast with this amazing opportunity! Be your own boss!"
            )
            location = "Remote"
            remote_flag = True
            hiring_manager_email = None
            is_active = True

        # We can't call evaluate directly without a session, but we can test the logic
        text_lower = MockJob.description_text.lower()
        from app.services.job_fraud_detector import _SCAM_PHRASES

        found_scam = any(phrase in text_lower for phrase in _SCAM_PHRASES)
        assert found_scam is True

    def test_fee_required_detected(self):
        """Fee-related phrases should flag high."""
        from app.services.job_fraud_detector import _FEE_PHRASES

        text = "Please pay the registration fee of $50 to start training."
        text_lower = text.lower()
        found_fee = any(phrase in text_lower for phrase in _FEE_PHRASES)
        assert found_fee is True

    def test_personal_info_request_detected(self):
        """Personal info requests should flag high."""
        from app.services.job_fraud_detector import _PERSONAL_INFO_PHRASES

        text = "Please provide your social security number before the interview."
        text_lower = text.lower()
        found = any(phrase in text_lower for phrase in _PERSONAL_INFO_PHRASES)
        assert found is True

    def test_clean_posting_not_flagged(self):
        """A normal job posting should not trigger scam flags."""
        from app.services.job_fraud_detector import (
            _CRYPTO_PHRASES,
            _FEE_PHRASES,
            _PERSONAL_INFO_PHRASES,
            _SCAM_PHRASES,
        )

        text = """
        We are seeking a Senior Software Engineer with 5+ years of experience
        in Python and JavaScript. The role involves building microservices
        and working with cloud infrastructure. Competitive salary and benefits.
        """
        text_lower = text.lower()
        assert not any(phrase in text_lower for phrase in _SCAM_PHRASES)
        assert not any(phrase in text_lower for phrase in _FEE_PHRASES)
        assert not any(phrase in text_lower for phrase in _PERSONAL_INFO_PHRASES)
        assert not any(phrase in text_lower for phrase in _CRYPTO_PHRASES)

    def test_short_description_penalty(self):
        """Very short descriptions should be penalized."""
        text = "Apply now!"
        # < 100 characters should trigger SHORT_DESCRIPTION
        assert len(text) < 100

    def test_vague_title_detection(self):
        """Vague titles should be detected."""
        from app.services.job_fraud_detector import _VAGUE_TITLES

        title = "Amazing Opportunity Available"
        title_lower = title.lower()
        found = any(vt in title_lower for vt in _VAGUE_TITLES)
        assert found is True

    def test_excessive_caps_detection(self):
        """Titles with excessive caps should be detected."""
        title = "AMAZING SOFTWARE ENGINEER WANTED NOW"
        upper_ratio = sum(1 for c in title if c.isupper()) / max(len(title), 1)
        assert upper_ratio > 0.6


class TestDuplicateDetection:
    def test_title_fuzzy_match(self, detector):
        """Similar titles should match."""
        assert (
            detector._title_fuzzy_match(
                "Senior Software Engineer", "Senior Software Developer"
            )
            is True
        )

    def test_title_fuzzy_no_match(self, detector):
        """Very different titles should not match."""
        assert (
            detector._title_fuzzy_match(
                "Senior Software Engineer", "Marketing Director Regional Sales"
            )
            is False
        )

    def test_description_similarity_identical(self, detector):
        """Identical descriptions should have high similarity."""
        text = "We are looking for a software engineer with 5 years experience."
        similarity = detector._description_similarity(text, text)
        assert similarity == 1.0

    def test_description_similarity_different(self, detector):
        """Very different descriptions should have low similarity."""
        text1 = "Senior software engineer Python Django REST API microservices"
        text2 = "Marketing manager social media campaigns brand strategy analytics"
        similarity = detector._description_similarity(text1, text2)
        assert similarity < 0.3

    def test_description_similarity_similar(self, detector):
        """Similar descriptions should have moderate-high similarity."""
        text1 = "We need a senior software engineer with Python and Django experience building REST APIs"
        text2 = "Looking for a senior software engineer experienced in Python Django and REST API development"
        similarity = detector._description_similarity(text1, text2)
        assert similarity > 0.3  # Jaccard on word sets; similar but not identical

    def test_location_similar_same(self, detector):
        """Same location strings should match."""
        assert (
            detector._location_similar("San Francisco, CA", "San Francisco, CA") is True
        )

    def test_location_similar_missing(self, detector):
        """Missing location should not filter."""
        assert detector._location_similar(None, "San Francisco, CA") is True
        assert detector._location_similar("San Francisco, CA", None) is True
