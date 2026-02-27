"""Integration tests for strategic gap exploitation features.

Tests the key workflows without requiring live external services.
"""

from app.services.gs_mapper import format_gs_posting, map_salary_to_gs_grade
from app.services.job_bias_scanner import scan_job_for_bias
from app.services.job_deduplicator import _text_similarity
from app.services.posting_validator import validate_posting

# ---------------------------------------------------------------------------
# P46: Bias Scanner
# ---------------------------------------------------------------------------


class TestBiasScanner:
    """Test job bias detection."""

    def _make_job(self, **kwargs):
        """Create a mock EmployerJob-like object."""

        class MockJob:
            title = kwargs.get("title", "Software Engineer")
            description = kwargs.get("description", "")
            requirements = kwargs.get("requirements", "")

        return MockJob()

    def test_clean_posting(self):
        job = self._make_job(description="We are seeking a software engineer.")
        result = scan_job_for_bias(job)
        assert result["bias_score"] == 0
        assert len(result["flags"]) == 0

    def test_gendered_language(self):
        job = self._make_job(description="Looking for a rockstar ninja developer.")
        result = scan_job_for_bias(job)
        assert result["bias_score"] > 0
        assert any(f["type"] == "gendered" for f in result["flags"])

    def test_age_coded_language(self):
        job = self._make_job(description="We need a digital native for this role.")
        result = scan_job_for_bias(job)
        assert any(f["type"] == "age_coded" for f in result["flags"])

    def test_inclusive_alternatives_provided(self):
        job = self._make_job(description="Our manpower team is growing.")
        result = scan_job_for_bias(job)
        assert "manpower" in result["inclusive_alternatives"]
        assert result["inclusive_alternatives"]["manpower"] == "workforce"


# ---------------------------------------------------------------------------
# P46: Posting Validator
# ---------------------------------------------------------------------------


class TestPostingValidator:
    """Test posting validation checks."""

    def _make_job(self, **kwargs):
        class MockJob:
            title = kwargs.get("title", "Engineer")
            description = kwargs.get("description", "A" * 200)
            requirements = kwargs.get("requirements", "Python")
            location = kwargs.get("location", "Austin, TX")
            salary_min = kwargs.get("salary_min", 100000)
            salary_max = kwargs.get("salary_max", 150000)
            application_url = kwargs.get("application_url", "https://example.com")
            salary_currency = kwargs.get("salary_currency", "USD")

        return MockJob()

    def test_valid_posting(self):
        job = self._make_job(description="Equal opportunity employer. " + "A" * 200)
        result = validate_posting(job, "indeed")
        assert result["valid"] is True

    def test_missing_eeo(self):
        job = self._make_job()
        result = validate_posting(job)
        eeo = next(c for c in result["checks"] if c["name"] == "eeo_statement")
        assert eeo["status"] == "warn"

    def test_salary_required_in_california(self):
        job = self._make_job(
            location="San Francisco, California",
            salary_min=None,
            salary_max=None,
        )
        result = validate_posting(job)
        sal = next(c for c in result["checks"] if c["name"] == "salary_transparency")
        assert sal["status"] == "fail"

    def test_empty_description(self):
        job = self._make_job(description="")
        result = validate_posting(job)
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# P51: GS Grade Mapper
# ---------------------------------------------------------------------------


class TestGSMapper:
    """Test GS grade salary mapping."""

    def test_mid_range_salary(self):
        result = map_salary_to_gs_grade(80000, 120000)
        assert result["gs_low"] is not None
        assert result["gs_high"] is not None
        assert result["pay_plan"] == "GS"

    def test_locality_adjustment(self):
        dc = map_salary_to_gs_grade(80000, 120000, "Washington, DC")
        rest = map_salary_to_gs_grade(80000, 120000, "Rural Iowa")
        assert dc["locality_factor"] > rest["locality_factor"]

    def test_no_salary(self):
        result = map_salary_to_gs_grade(0, 0)
        assert result["gs_low"] is None

    def test_format_gs_posting(self):
        gs_info = map_salary_to_gs_grade(90000, 130000, "DC")
        result = format_gs_posting("IT Specialist", gs_info, "Duties", "Quals")
        assert result["position_title"] == "IT Specialist"
        assert result["pay_plan"] == "GS"
        assert "grade_low" in result


# ---------------------------------------------------------------------------
# P48: Job Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Test content hashing and similarity."""

    def test_text_similarity_identical(self):
        assert _text_similarity("hello", "hello") == 1.0

    def test_text_similarity_different(self):
        sim = _text_similarity("apple", "orange")
        assert sim < 0.5

    def test_text_similarity_empty(self):
        assert _text_similarity("", "") == 1.0
        assert _text_similarity("hello", "") == 0.0
