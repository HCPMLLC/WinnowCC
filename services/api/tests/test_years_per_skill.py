"""Tests for the _compute_skill_years function in profile_parser."""

from app.services.profile_parser import _compute_skill_years


def test_basic_skill_years():
    skills = ["Python", "AWS"]
    experience = [
        {
            "start_date": "Jan-2020",
            "end_date": "Jan-2023",
            "skills_used": ["Python"],
            "technologies_used": ["AWS"],
            "duties": ["Developed APIs using Python and AWS Lambda"],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert "Python" in result
    assert result["Python"]["years_experience"] == 3
    assert result["Python"]["years_experience_source"] == "parsed"
    assert "AWS" in result
    assert result["AWS"]["years_experience"] == 3


def test_overlapping_dates():
    """Two overlapping roles should not double-count."""
    skills = ["Python"]
    experience = [
        {
            "start_date": "Jan-2020",
            "end_date": "Dec-2022",
            "skills_used": ["Python"],
            "technologies_used": [],
            "duties": [],
        },
        {
            "start_date": "Jun-2021",
            "end_date": "Jun-2023",
            "skills_used": ["Python"],
            "technologies_used": [],
            "duties": [],
        },
    ]
    result = _compute_skill_years(skills, experience)
    # Should merge: Jan 2020 - Jun 2023 = ~3.5 years, rounded to 4
    years = result["Python"]["years_experience"]
    assert 3 <= years <= 4


def test_present_end_date():
    """'Present' end date should count up to today."""
    skills = ["Docker"]
    experience = [
        {
            "start_date": "Jan-2022",
            "end_date": "Present",
            "skills_used": ["Docker"],
            "technologies_used": [],
            "duties": [],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert "Docker" in result
    # Should be at least 3 years (2022 to 2025+)
    assert result["Docker"]["years_experience"] >= 3


def test_skill_found_in_duties():
    """Skills mentioned in duties text should be detected."""
    skills = ["Kubernetes"]
    experience = [
        {
            "start_date": "Mar-2021",
            "end_date": "Mar-2024",
            "skills_used": [],
            "technologies_used": [],
            "duties": [
                "Managed Kubernetes clusters for production workloads"
            ],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert "Kubernetes" in result
    assert result["Kubernetes"]["years_experience"] == 3


def test_skill_not_found():
    """Skills not mentioned in any experience should not appear."""
    skills = ["Haskell"]
    experience = [
        {
            "start_date": "Jan-2020",
            "end_date": "Dec-2023",
            "skills_used": ["Python"],
            "technologies_used": ["AWS"],
            "duties": ["Built APIs"],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert "Haskell" not in result


def test_empty_inputs():
    assert _compute_skill_years([], []) == {}
    assert _compute_skill_years(["Python"], []) == {}
    assert _compute_skill_years([], [{"start_date": "Jan-2020"}]) == {}


def test_missing_start_date():
    """Entries without start dates should be skipped."""
    skills = ["Python"]
    experience = [
        {
            "start_date": "",
            "end_date": "Dec-2023",
            "skills_used": ["Python"],
            "technologies_used": [],
            "duties": [],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert "Python" not in result


def test_concurrent_roles():
    """Two concurrent roles with different skills should track independently."""
    skills = ["Python", "Java"]
    experience = [
        {
            "start_date": "Jan-2020",
            "end_date": "Dec-2022",
            "skills_used": ["Python"],
            "technologies_used": [],
            "duties": [],
        },
        {
            "start_date": "Jan-2020",
            "end_date": "Dec-2022",
            "skills_used": ["Java"],
            "technologies_used": [],
            "duties": [],
        },
    ]
    result = _compute_skill_years(skills, experience)
    assert result["Python"]["years_experience"] == 3
    assert result["Java"]["years_experience"] == 3
