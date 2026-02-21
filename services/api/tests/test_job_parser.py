"""Unit tests for JobParserService."""

import pytest

from app.services.job_parser import JobParserService


@pytest.fixture
def parser():
    return JobParserService()


class TestTitleNormalization:
    def test_abbreviation_expansion(self, parser):
        title, seniority = parser._normalize_title("Sr. Software Eng.")
        assert "senior" in title.lower()
        assert "engineer" in title.lower()

    def test_seniority_detection_senior(self, parser):
        _, seniority = parser._normalize_title("Senior Project Manager")
        assert seniority == "senior"

    def test_seniority_detection_junior(self, parser):
        _, seniority = parser._normalize_title("Junior Software Developer")
        assert seniority == "junior"

    def test_seniority_detection_executive(self, parser):
        _, seniority = parser._normalize_title("VP of Engineering")
        assert seniority == "executive"

    def test_seniority_detection_director(self, parser):
        _, seniority = parser._normalize_title("Director of Product")
        assert seniority == "director"

    def test_seniority_default_mid(self, parser):
        _, seniority = parser._normalize_title("Software Engineer")
        assert seniority == "mid"

    def test_removes_parenthetical(self, parser):
        title, _ = parser._normalize_title("Software Engineer (Remote)")
        assert "(Remote)" not in title
        assert "Remote" not in title

    def test_strips_whitespace(self, parser):
        title, _ = parser._normalize_title("  Software  Engineer  ")
        assert "  " not in title
        assert title.strip() == title


class TestSalaryExtraction:
    def test_range_with_k(self, parser):
        text = "Salary: $120k - $150k per year"
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Engineer", "senior", None
        )
        assert sal_min == 120000
        assert sal_max == 150000
        assert confidence == "parsed"

    def test_range_with_commas(self, parser):
        text = "The salary range is $120,000 - $150,000 annually"
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Engineer", "senior", None
        )
        assert sal_min == 120000
        assert sal_max == 150000

    def test_hourly_rate(self, parser):
        text = "Pay rate: $65/hr"
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Developer", "mid", None
        )
        assert sal_min is not None
        assert sal_type == "hourly"
        assert confidence == "parsed"

    def test_up_to_hourly(self, parser):
        text = "up to $90/hr"
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Consultant", "senior", None
        )
        assert sal_max is not None
        assert confidence == "parsed"

    def test_no_salary_falls_back_to_reference(self, parser):
        text = "We are looking for a software engineer to join our team."
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Software Engineer", "senior", None
        )
        # Should fall back to salary reference data
        if sal_min is not None:
            assert confidence == "estimated"

    def test_no_salary_no_reference(self, parser):
        text = "Join our team as a widget polisher."
        sal_min, sal_max, currency, sal_type, confidence = parser._extract_compensation(
            text, "Widget Polisher", "mid", None
        )
        # May return None if no reference match
        assert confidence is None or confidence == "estimated"


class TestLocationParsing:
    def test_city_state_format(self, parser):
        city, state, country, work_mode, travel, relocation = parser._parse_location(
            "Software Engineer", "San Francisco, CA", ""
        )
        assert city == "San Francisco"
        assert state == "California"
        assert country == "US"

    def test_remote_detection(self, parser):
        city, state, country, work_mode, travel, relocation = parser._parse_location(
            "Software Engineer (Remote)", "Remote", "This is a fully remote position."
        )
        assert work_mode == "remote"

    def test_hybrid_detection(self, parser):
        city, state, country, work_mode, travel, relocation = parser._parse_location(
            "Engineer",
            "New York, NY",
            "This is a hybrid role requiring 3 days in office.",
        )
        assert work_mode == "hybrid"

    def test_travel_percent(self, parser):
        city, state, country, work_mode, travel, relocation = parser._parse_location(
            "Consultant", "Chicago, IL", "This role requires 25% travel domestically."
        )
        assert travel == 25

    def test_relocation_offered(self, parser):
        city, state, country, work_mode, travel, relocation = parser._parse_location(
            "Engineer",
            "Austin, TX",
            "Relocation assistance provided for the right candidate.",
        )
        assert relocation is True


class TestRequirementsExtraction:
    def test_extracts_years_experience(self, parser):
        text = """
        Requirements:
        - 5+ years of experience in software development
        - Proficiency in Python
        """
        (
            req_skills,
            pref_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibilities,
            qualifications,
        ) = parser._extract_requirements(text)
        assert years_min == 5

    def test_extracts_certifications(self, parser):
        text = "Must have PMP certification and AWS Certified Solutions Architect"
        (
            req_skills,
            pref_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibilities,
            qualifications,
        ) = parser._extract_requirements(text)
        assert any("PMP" in c for c in certs)

    def test_extracts_education(self, parser):
        text = "Bachelor's degree in Computer Science required. Master's preferred."
        (
            req_skills,
            pref_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibilities,
            qualifications,
        ) = parser._extract_requirements(text)
        assert "Bachelor's" in education
        assert "Master's" in education

    def test_extracts_tools(self, parser):
        text = "Experience with Jira, Confluence, and Slack required."
        (
            req_skills,
            pref_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibilities,
            qualifications,
        ) = parser._extract_requirements(text)
        assert any("Jira" in t for t in tools)


class TestQualityScore:
    def test_high_quality_posting(self, parser):
        """A well-written posting should score high."""

        class MockJob:
            description_text = """
            We are looking for a Senior Software Engineer to join our cloud platform team.

            Requirements:
            - 5+ years of experience in Python and Go
            - Experience with AWS, Docker, Kubernetes
            - Bachelor's degree in Computer Science

            Nice to have:
            - PMP certification
            - Experience with Terraform

            Benefits:
            - Health insurance, dental, vision
            - 401k with match
            - Remote work flexibility
            - Professional development budget

            Salary: $150,000 - $200,000

            About Us:
            We are a mid-size SaaS company in the healthcare technology space.
            """

        class MockParsed:
            normalized_title = "Senior Software Engineer"
            seniority_level = "senior"
            parsed_salary_min = 150000
            salary_confidence = "parsed"
            required_skills = ["python", "go", "aws", "docker", "kubernetes"]
            required_education = ["Bachelor's"]
            years_experience_min = 5
            inferred_industry = "technology"
            department = "Cloud Platform"
            benefits_mentioned = [
                "health insurance",
                "dental",
                "vision",
                "401k",
                "remote work",
                "professional development",
            ]
            employment_type = "full-time"
            work_mode = "remote"

        score = parser._compute_quality_score(MockJob(), MockParsed())
        assert score >= 70  # Should be high quality

    def test_low_quality_posting(self, parser):
        """A bare-bones posting should score low."""

        class MockJob:
            description_text = "Looking for someone. Apply now!"

        class MockParsed:
            normalized_title = ""
            seniority_level = None
            parsed_salary_min = None
            salary_confidence = None
            required_skills = []
            required_education = []
            years_experience_min = None
            inferred_industry = None
            department = None
            benefits_mentioned = []
            employment_type = None
            work_mode = None

        score = parser._compute_quality_score(MockJob(), MockParsed())
        assert score < 50  # Should be low quality
