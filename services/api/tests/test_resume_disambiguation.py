"""Tests for resume disambiguation engine and enhanced parser pipeline."""

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


