"""Tests for LLM parser post-processing validation."""

from app.services.llm_parser import (
    _split_school_degree_field,
    map_llm_to_profile_json,
)


# ---------- Skill splitting ----------


def test_concatenated_skills_are_split() -> None:
    """When LLM returns skills concatenated in one string, they get split."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "skills": {
            "technical_skills": [
                {"name": "Python, Java, React, SQL"},
            ],
        },
    }
    profile = map_llm_to_profile_json(llm_output)
    skills = profile["skills"]
    assert "Python" in skills
    assert "Java" in skills
    assert "React" in skills
    assert "SQL" in skills
    # Should NOT have the concatenated form
    assert "Python, Java, React, SQL" not in skills


def test_semicolon_separated_skills_are_split() -> None:
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "skills": {
            "technical_skills": [
                {"name": "Docker; Kubernetes; Terraform"},
            ],
        },
    }
    profile = map_llm_to_profile_json(llm_output)
    skills = profile["skills"]
    assert "Docker" in skills
    assert "Kubernetes" in skills
    assert "Terraform" in skills


def test_single_skill_not_split() -> None:
    """A single skill name should remain as-is."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "skills": {
            "technical_skills": [
                {"name": "Python"},
                {"name": "React"},
            ],
        },
    }
    profile = map_llm_to_profile_json(llm_output)
    assert "Python" in profile["skills"]
    assert "React" in profile["skills"]


# ---------- Education field separation ----------


def test_merged_education_school_degree_split() -> None:
    """When LLM puts degree info in the institution field, it gets separated."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "education": [
            {
                "institution": "MIT, Bachelor of Science in Computer Science",
                "degree_type": None,
                "field_of_study": None,
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    edu = profile["education"][0]
    assert edu["school"] == "MIT"
    assert edu["degree"] == "Bachelor of Science"
    assert edu["field"] == "Computer Science"


def test_reversed_education_fields_split() -> None:
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "education": [
            {
                "institution": "Bachelor of Arts in Psychology, UCLA",
                "degree_type": None,
                "field_of_study": None,
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    edu = profile["education"][0]
    assert edu["school"] == "UCLA"
    assert edu["degree"] == "Bachelor of Arts"
    assert edu["field"] == "Psychology"


def test_education_already_separated() -> None:
    """When LLM correctly separates fields, they pass through unchanged."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "education": [
            {
                "institution": "Stanford University",
                "degree_type": "Master of Science",
                "field_of_study": "Machine Learning",
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    edu = profile["education"][0]
    assert edu["school"] == "Stanford University"
    assert edu["degree"] == "Master of Science"
    assert edu["field"] == "Machine Learning"


def test_education_degree_in_degree_type_split() -> None:
    """Combined degree+field in degree_type gets split."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "education": [
            {
                "institution": "Harvard",
                "degree_type": "Bachelor of Arts in Economics",
                "field_of_study": None,
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    edu = profile["education"][0]
    assert edu["school"] == "Harvard"
    assert edu["degree"] == "Bachelor of Arts"
    assert edu["field"] == "Economics"


# ---------- Experience validation ----------


def test_empty_experience_entry_filtered() -> None:
    """Entries with no company, title, or duties are dropped."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "work_experience": [
            {
                "company_name": "Acme Corp",
                "job_title": "Engineer",
                "duties": ["Built APIs"],
            },
            {
                "company_name": None,
                "job_title": None,
                "duties": [],
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    assert len(profile["experience"]) == 1
    assert profile["experience"][0]["company"] == "Acme Corp"


def test_experience_string_duties_normalized() -> None:
    """If duties come as a string, they get normalized to a list."""
    llm_output = {
        "contact_information": {"full_name": "Jane Doe"},
        "work_experience": [
            {
                "company_name": "Acme Corp",
                "job_title": "Engineer",
                "duties": "Built APIs and managed deployments",
            },
        ],
    }
    profile = map_llm_to_profile_json(llm_output)
    duties = profile["experience"][0]["duties"]
    assert isinstance(duties, list)
    assert len(duties) == 1
    assert "Built APIs" in duties[0]


# ---------- _split_school_degree_field helper ----------


def test_split_school_degree_field_dash() -> None:
    school, degree, field = _split_school_degree_field(
        "MIT - Bachelor of Science in CS", None, None
    )
    assert school == "MIT"
    assert degree == "Bachelor of Science"
    assert field == "CS"


def test_split_school_degree_field_no_degree() -> None:
    school, degree, field = _split_school_degree_field(
        "Stanford University", None, None
    )
    assert school == "Stanford University"
    assert degree is None
    assert field is None


def test_split_school_degree_field_pipe() -> None:
    school, degree, field = _split_school_degree_field(
        "UCLA | Master of Arts in English", None, None
    )
    assert school == "UCLA"
    assert degree == "Master of Arts"
    assert field == "English"
