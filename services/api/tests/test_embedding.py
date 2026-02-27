"""Tests for embedding service and semantic matching helpers."""

from unittest.mock import MagicMock

from app.services.embedding import prepare_job_text, prepare_profile_text

# ---------------------------------------------------------------------------
# prepare_job_text
# ---------------------------------------------------------------------------


class TestPrepareJobText:
    def test_all_fields(self):
        job = MagicMock()
        job.title = "Senior Engineer"
        job.company = "Acme Corp"
        job.description_text = "Build things"
        job.location = "Remote"
        text = prepare_job_text(job)
        assert "Senior Engineer" in text
        assert "Acme Corp" in text
        assert "Build things" in text
        assert "Remote" in text

    def test_missing_fields(self):
        job = MagicMock()
        job.title = "Analyst"
        job.company = None
        job.description_text = None
        job.location = None
        text = prepare_job_text(job)
        assert "Analyst" in text
        assert "Company" not in text

    def test_long_description_truncated(self):
        job = MagicMock()
        job.title = "Dev"
        job.company = "Co"
        job.description_text = "x" * 5000
        job.location = "NY"
        text = prepare_job_text(job)
        # Description should be truncated to 2000 chars
        desc_line = [
            line for line in text.split("\n") if line.startswith("Description:")
        ][0]
        # The truncated desc part (after "Description: ") should be <= 2000
        assert len(desc_line) <= 2000 + len("Description: ")


# ---------------------------------------------------------------------------
# prepare_profile_text
# ---------------------------------------------------------------------------


class TestPrepareProfileText:
    def test_full_profile(self):
        profile = {
            "professional_summary": "Experienced PM with 10 years",
            "experience": [
                {
                    "title": "Project Manager",
                    "company": "BigCo",
                    "duties": ["Managed team of 10", "Delivered on time"],
                }
            ],
            "skills": ["Python", "AWS", "Docker"],
            "preferences": {"target_titles": ["Senior PM"]},
        }
        text = prepare_profile_text(profile)
        assert "Experienced PM" in text
        assert "Project Manager" in text
        assert "BigCo" in text
        assert "Managed team" in text
        assert "Python" in text
        assert "Senior PM" in text

    def test_empty_profile(self):
        text = prepare_profile_text({})
        assert text == ""

    def test_only_skills(self):
        profile = {"skills": ["React", "TypeScript"]}
        text = prepare_profile_text(profile)
        assert "React" in text
        assert "TypeScript" in text

    def test_accomplishments_preferred_over_duties(self):
        profile = {
            "experience": [
                {
                    "title": "Dev",
                    "company": "Co",
                    "accomplishments": ["Reduced latency by 50%"],
                    "duties": ["Wrote code"],
                }
            ]
        }
        text = prepare_profile_text(profile)
        assert "Reduced latency" in text
        assert "Wrote code" not in text

    def test_max_three_experiences(self):
        profile = {
            "experience": [
                {"title": f"Role {i}", "company": f"Co {i}"} for i in range(5)
            ]
        }
        text = prepare_profile_text(profile)
        assert "Role 0" in text
        assert "Role 2" in text
        assert "Role 3" not in text
