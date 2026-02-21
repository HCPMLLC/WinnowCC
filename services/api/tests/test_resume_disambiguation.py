"""Tests for resume disambiguation engine and enhanced parser pipeline."""

from app.services.profile_parser import (
    classify_bullet,
    is_xyz_bullet,
    parse_profile_from_text,
    split_bullets,
)
from app.services.resume_disambiguation import (
    categorize_technology,
    classify_term,
    detect_primary_industry,
    detect_role_category,
    infer_company_industry,
)

# ---------------------------------------------------------------------------
# detect_primary_industry
# ---------------------------------------------------------------------------


class TestDetectPrimaryIndustry:
    def test_it_resume(self):
        text = (
            "Software Engineer at Google. Built microservices in Python and "
            "deployed to AWS using Docker and Kubernetes. Managed CI/CD pipelines."
        )
        result = detect_primary_industry(text, ["Google"], ["Software Engineer"])
        assert result == "Information Technology"

    def test_construction_resume(self):
        text = (
            "Project Manager overseeing construction of 120-unit residential "
            "complex. OSHA certified superintendent managing subcontractors "
            "on jobsite. Used Procore for scheduling."
        )
        result = detect_primary_industry(
            text, ["Turner Construction"], ["Project Manager"]
        )
        assert result == "Construction"

    def test_healthcare_resume(self):
        text = (
            "Registered Nurse with 5 years of patient care experience at "
            "Mayo Clinic hospital. HIPAA compliant. Managed clinical triage "
            "and medication administration."
        )
        result = detect_primary_industry(text, ["Mayo Clinic"], ["Registered Nurse"])
        assert result == "Healthcare"

    def test_finance_resume(self):
        text = (
            "Financial Analyst at JPMorgan Chase. Performed risk management, "
            "portfolio analysis, and compliance auditing under SOX and GAAP "
            "regulations."
        )
        result = detect_primary_industry(
            text, ["JPMorgan Chase"], ["Financial Analyst"]
        )
        assert result == "Finance"

    def test_ambiguous_falls_back_to_other(self):
        result = detect_primary_industry("I work at a company.", [], [])
        assert result == "Other"

    def test_empty_text(self):
        result = detect_primary_industry("", [], [])
        assert result == "Other"


# ---------------------------------------------------------------------------
# detect_role_category
# ---------------------------------------------------------------------------


class TestDetectRoleCategory:
    def test_project_manager(self):
        result = detect_role_category(["Senior Project Manager", "PMO Director"])
        assert result == "Project Management"

    def test_software_engineer(self):
        result = detect_role_category(
            ["Software Engineer", "Senior Software Developer"]
        )
        assert result == "Software Engineering"

    def test_data_analyst(self):
        result = detect_role_category(["Data Analyst", "Business Analyst"])
        assert result == "Data/Analytics"

    def test_empty_titles(self):
        assert detect_role_category([]) == "General"

    def test_no_matching_pattern(self):
        assert detect_role_category(["Underwater Basket Weaver"]) == "General"


# ---------------------------------------------------------------------------
# classify_term
# ---------------------------------------------------------------------------


class TestClassifyTerm:
    def test_always_technology(self):
        result = classify_term(
            "Tableau",
            [],
            "Information Technology",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Technology"

    def test_always_methodology(self):
        result = classify_term(
            "Scrum",
            [],
            "Information Technology",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Methodology"

    def test_always_compliance(self):
        result = classify_term(
            "HIPAA",
            [],
            "Healthcare",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Compliance"

    def test_always_certification(self):
        result = classify_term(
            "PMP",
            [],
            "Management",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Certification"

    def test_term_in_title_is_role(self):
        result = classify_term(
            "Oracle",
            [],
            "Information Technology",
            is_in_title=True,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Role"

    def test_term_after_employer_is_company(self):
        result = classify_term(
            "Oracle",
            [],
            "Information Technology",
            is_in_title=False,
            is_after_employer_signal=True,
            is_in_tech_line=False,
        )
        assert result == "Company"

    def test_term_in_tech_line(self):
        result = classify_term(
            "SomeRandomTool",
            [],
            "Information Technology",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=True,
        )
        assert result == "Technology"

    def test_known_tech_in_categories(self):
        result = classify_term(
            "Python",
            [],
            "Information Technology",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Technology"

    def test_ambiguous_term(self):
        result = classify_term(
            "SomethingUnknown",
            [],
            "Other",
            is_in_title=False,
            is_after_employer_signal=False,
            is_in_tech_line=False,
        )
        assert result == "Ambiguous"


# ---------------------------------------------------------------------------
# categorize_technology
# ---------------------------------------------------------------------------


class TestCategorizeTechnology:
    def test_programming_language(self):
        assert categorize_technology("Python") == "Programming Language"
        assert categorize_technology("javascript") == "Programming Language"

    def test_framework(self):
        assert categorize_technology("React") == "Framework"
        assert categorize_technology("Django") == "Framework"

    def test_database(self):
        assert categorize_technology("PostgreSQL") == "Database"
        assert categorize_technology("Redis") == "Database"

    def test_containerization(self):
        assert categorize_technology("Docker") == "Containerization"

    def test_orchestration(self):
        assert categorize_technology("Kubernetes") == "Orchestration"

    def test_unknown(self):
        assert categorize_technology("SomeUnknownTool") == "Other"


# ---------------------------------------------------------------------------
# infer_company_industry
# ---------------------------------------------------------------------------


class TestInferCompanyIndustry:
    def test_tech_company(self):
        result = infer_company_industry(
            "Google",
            ["Built microservices", "Deployed to cloud using Kubernetes"],
        )
        assert result == "Information Technology"

    def test_construction_company(self):
        result = infer_company_industry(
            "Turner Construction",
            ["Oversaw construction of building", "Managed subcontractor on jobsite"],
        )
        assert result == "Construction"

    def test_insufficient_signal(self):
        result = infer_company_industry("Acme Corp", ["Did things"])
        assert result is None


# ---------------------------------------------------------------------------
# classify_bullet / split_bullets
# ---------------------------------------------------------------------------


class TestBulletClassification:
    def test_duty_bullet(self):
        assert (
            classify_bullet("Maintained CI/CD pipelines for production deployments")
            == "duty"
        )

    def test_accomplishment_with_percentage(self):
        assert classify_bullet("Reduced deployment time by 60%") == "accomplishment"

    def test_accomplishment_with_dollar(self):
        assert (
            classify_bullet("Generated $4.2M in revenue through new platform")
            == "accomplishment"
        )

    def test_accomplishment_with_action_verb(self):
        assert (
            classify_bullet("Achieved zero downtime during migration")
            == "accomplishment"
        )

    def test_split_bullets(self):
        bullets = [
            "Maintained documentation for internal processes",
            "Reduced costs by 40% through automation",
            "Coordinated daily standups and sprint ceremonies",
            "Delivered $2M project ahead of schedule",
        ]
        duties, accomplishments = split_bullets(bullets)
        assert len(duties) == 2
        assert len(accomplishments) == 2
        assert "Reduced costs by 40% through automation" in accomplishments
        assert "Delivered $2M project ahead of schedule" in accomplishments


# ---------------------------------------------------------------------------
# is_xyz_bullet
# ---------------------------------------------------------------------------


class TestXyzBullet:
    def test_full_xyz(self):
        bullet = (
            "Led migration of 3 services to microservices, reducing deploy "
            "time by 60% by implementing Docker containers"
        )
        assert is_xyz_bullet(bullet) is True

    def test_partial_xyz_action_plus_metric(self):
        assert is_xyz_bullet("Reduced costs by 40% for infrastructure") is True

    def test_not_xyz_no_metric(self):
        assert is_xyz_bullet("Maintained documentation for internal processes") is False

    def test_not_xyz_metric_only(self):
        # Has metric but no action verb from the list
        assert is_xyz_bullet("The team had 15 engineers") is False


# ---------------------------------------------------------------------------
# Enhanced parser output
# ---------------------------------------------------------------------------


class TestEnhancedParserOutput:
    SAMPLE_RESUME = "\n".join(
        [
            "Jane Doe",
            "jane.doe@example.com",
            "(555) 123-4567",
            "https://linkedin.com/in/janedoe",
            "https://github.com/janedoe",
            "San Francisco, CA",
            "",
            "Summary",
            "Experienced software engineer with 10 years building cloud apps.",
            "",
            "Experience",
            "Senior Software Engineer",
            "Google - Mountain View, CA",
            "Jan 2020 - Present",
            "- Led migration of monolith to microservices, reducing deploy time by 60%",
            "- Managed team of 5 engineers building internal tools",
            "- Maintained CI/CD pipelines using GitHub Actions",
            "",
            "Software Engineer",
            "Startup Inc - San Francisco, CA",
            "Jun 2015 - Dec 2019",
            "- Built REST APIs in Python and Django",
            "- Improved test coverage from 40% to 90%",
            "",
            "Skills",
            "Python, AWS, Docker, Kubernetes, React, Django, PostgreSQL",
            "",
            "Education",
            "Stanford University",
            "B.S. Computer Science",
            "2015",
            "",
            "Certifications",
            "AWS Solutions Architect - Amazon, 2021",
        ]
    )

    def test_backward_compatibility(self):
        """All original top-level keys must still exist."""
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert "basics" in profile
        assert "experience" in profile
        assert "education" in profile
        assert "certifications" in profile
        assert "skills" in profile
        assert "preferences" in profile
        assert isinstance(profile["skills"], list)

    def test_new_enhanced_fields_exist(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert "primary_industry" in profile
        assert "primary_role_category" in profile
        assert "contact_information" in profile
        assert "professional_summary" in profile
        assert "skills_structured" in profile
        assert "additional_sections" in profile
        assert "disambiguation_notes" in profile

    def test_primary_industry_detected(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert profile["primary_industry"] == "Information Technology"

    def test_role_category_detected(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert profile["primary_role_category"] == "Software Engineering"

    def test_contact_information_urls(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        ci = profile["contact_information"]
        assert ci["full_name"] == "Jane Doe"
        assert ci["email"] == "jane.doe@example.com"
        assert ci["linkedin_url"] is not None
        assert "linkedin.com" in ci["linkedin_url"]
        assert ci["github_url"] is not None
        assert "github.com" in ci["github_url"]

    def test_professional_summary_extracted(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert "cloud apps" in profile["professional_summary"]

    def test_experience_has_accomplishments(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        # Find the entry that has duties (parser may chunk differently)
        entries_with_duties = [e for e in profile["experience"] if e.get("duties")]
        assert len(entries_with_duties) >= 1
        exp = entries_with_duties[0]
        assert "accomplishments" in exp
        assert len(exp["accomplishments"]) >= 1  # "reducing deploy time by 60%"

    def test_experience_has_xyz_counts(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        entries_with_duties = [e for e in profile["experience"] if e.get("duties")]
        assert len(entries_with_duties) >= 1
        exp = entries_with_duties[0]
        assert "xyz_bullet_count" in exp
        assert "total_bullet_count" in exp
        assert exp["total_bullet_count"] >= 2

    def test_experience_has_technologies_categorized(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        exp = profile["experience"][0]
        assert "technologies_categorized" in exp
        # Each item should have name and category
        for tech in exp["technologies_categorized"]:
            assert "name" in tech
            assert "category" in tech

    def test_skills_structured_exists(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        ss = profile["skills_structured"]
        assert "technical_skills" in ss
        assert "methodologies" in ss
        assert "soft_skills" in ss
        assert isinstance(ss["technical_skills"], list)

    def test_skills_structured_has_categories(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        tech_skills = profile["skills_structured"]["technical_skills"]
        if tech_skills:
            assert "name" in tech_skills[0]
            assert "category" in tech_skills[0]

    def test_disambiguation_notes_is_list(self):
        profile = parse_profile_from_text(self.SAMPLE_RESUME)
        assert isinstance(profile["disambiguation_notes"], list)
