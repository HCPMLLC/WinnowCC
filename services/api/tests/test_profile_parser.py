from app.services.profile_parser import (
    _extract_education,
    _extract_skills,
    _looks_like_degree,
    _split_school_degree_field,
    parse_profile_from_text,
)


def test_parse_profile_from_text_extracts_basics_and_skills() -> None:
    text = "\n".join(
        [
            "Jane Doe",
            "jane.doe@example.com",
            "(555) 123-4567",
            "",
            "Skills",
            "Python, SQL, Docker",
        ]
    )
    profile = parse_profile_from_text(text)

    assert profile["basics"]["name"] == "Jane Doe"
    assert profile["basics"]["email"] == "jane.doe@example.com"
    assert "555" in profile["basics"]["phone"]
    assert "Python" in profile["skills"]
    assert "SQL" in profile["skills"]
    assert "Docker" in profile["skills"]


# ---------- Education parsing ----------


def test_looks_like_degree() -> None:
    assert _looks_like_degree("Bachelor of Science")
    assert _looks_like_degree("M.S. in Computer Science")
    assert _looks_like_degree("MBA")
    assert _looks_like_degree("Ph.D in Physics")
    assert not _looks_like_degree("Massachusetts Institute of Technology")
    assert not _looks_like_degree("Google")


def test_split_school_degree_field_comma_separated() -> None:
    school, degree, field = _split_school_degree_field(
        "MIT, Bachelor of Science in Computer Science"
    )
    assert school == "MIT"
    assert degree == "Bachelor of Science"
    assert field == "Computer Science"


def test_split_school_degree_field_reversed_order() -> None:
    school, degree, field = _split_school_degree_field(
        "Bachelor of Arts in Psychology, University of Texas"
    )
    assert school == "University of Texas"
    assert degree == "Bachelor of Arts"
    assert field == "Psychology"


def test_split_school_degree_field_no_degree() -> None:
    school, degree, field = _split_school_degree_field("Stanford University")
    assert school == "Stanford University"
    assert degree is None
    assert field is None


def test_education_comma_separated() -> None:
    lines = [
        "Some Header",
        "",
        "Education",
        "MIT, Bachelor of Science in Computer Science",
    ]
    items = _extract_education(lines)
    assert len(items) == 1
    assert items[0]["school"] == "MIT"
    assert items[0]["degree"] == "Bachelor of Science"
    assert items[0]["field"] == "Computer Science"


def test_education_multiline() -> None:
    lines = [
        "Education",
        "University of California",
        "Master of Science in Data Science",
    ]
    items = _extract_education(lines)
    assert len(items) == 1
    assert items[0]["school"] == "University of California"
    assert items[0]["degree"] == "Master of Science"
    assert items[0]["field"] == "Data Science"


def test_education_dash_format_preserved() -> None:
    """Original dash format still works."""
    lines = [
        "Education",
        "MIT - Bachelor of Science in Computer Science",
    ]
    items = _extract_education(lines)
    assert len(items) == 1
    assert items[0]["school"] == "MIT"
    assert items[0]["degree"] == "Bachelor of Science"
    assert items[0]["field"] == "Computer Science"


# ---------- Skills extraction ----------


def test_skills_from_env_line() -> None:
    lines = [
        "Jane Doe",
        "Experience",
        "Software Engineer at Acme",
        "Technologies: Python, FastAPI, Redis, Docker",
    ]
    text = "\n".join(lines)
    skills = _extract_skills(lines, text)
    assert "Python" in skills or "python" in skills
    assert "FastAPI" in skills or "fastapi" in skills
    assert "Redis" in skills or "redis" in skills


def test_skills_from_parenthetical() -> None:
    lines = [
        "Experience",
        "- Built scalable API (Python, FastAPI, Redis)",
    ]
    text = "\n".join(lines)
    skills = _extract_skills(lines, text)
    skill_lower = [s.lower() for s in skills]
    assert "python" in skill_lower
    assert "fastapi" in skill_lower
    assert "redis" in skill_lower


# ---------- Experience parsing ----------


def test_experience_pipe_format() -> None:
    text = "\n".join(
        [
            "Jane Doe",
            "jane@example.com",
            "(555) 123-4567",
            "",
            "Experience",
            "Senior Engineer | Acme Corp",
            "- Built stuff",
        ]
    )
    profile = parse_profile_from_text(text)
    assert len(profile["experience"]) >= 1
    exp = profile["experience"][0]
    assert exp["title"] == "Senior Engineer"
    assert exp["company"] == "Acme Corp"


def test_experience_parenthetical_format() -> None:
    text = "\n".join(
        [
            "Jane Doe",
            "jane@example.com",
            "(555) 123-4567",
            "",
            "Experience",
            "Senior Engineer (Acme Corp)",
            "- Built stuff",
        ]
    )
    profile = parse_profile_from_text(text)
    assert len(profile["experience"]) >= 1
    exp = profile["experience"][0]
    assert exp["title"] == "Senior Engineer"
    assert exp["company"] == "Acme Corp"
