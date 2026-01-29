from app.services.profile_parser import parse_profile_from_text


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
