"""
Profile completeness detection and scoring.

Analyzes candidate profiles to identify missing fields required
for accurate IPS calculation and job matching.
"""

import logging
from typing import Any

from app.models.job import Job

logger = logging.getLogger(__name__)


# Fields required for different levels of matching
REQUIRED_FIELDS = [
    {
        "field": "full_name",
        "label": "Full Name",
        "importance": "required",
    },
    {"field": "email", "label": "Email", "importance": "required"},
    {
        "field": "phone",
        "label": "Phone Number",
        "importance": "recommended",
    },
    {
        "field": "location",
        "label": "Location",
        "importance": "recommended",
    },
    {
        "field": "years_experience",
        "label": "Years of Experience",
        "importance": "required",
    },
    {
        "field": "current_title",
        "label": "Current/Most Recent Title",
        "importance": "required",
    },
    {
        "field": "skills",
        "label": "Key Skills",
        "importance": "required",
    },
    {
        "field": "work_history",
        "label": "Work History",
        "importance": "required",
    },
    {
        "field": "education",
        "label": "Education",
        "importance": "recommended",
    },
    {
        "field": "summary",
        "label": "Professional Summary",
        "importance": "optional",
    },
    {
        "field": "certifications",
        "label": "Certifications",
        "importance": "optional",
    },
    {
        "field": "desired_salary",
        "label": "Desired Salary Range",
        "importance": "optional",
    },
    {
        "field": "work_authorization",
        "label": "Work Authorization",
        "importance": "recommended",
    },
    {
        "field": "willing_to_relocate",
        "label": "Willing to Relocate",
        "importance": "optional",
    },
]


def calculate_completeness_score(profile_data: dict[str, Any]) -> int:
    """
    Calculate profile completeness percentage.

    Weights:
    - Required fields: 15 points each (max 75)
    - Recommended fields: 5 points each (max 20)
    - Optional fields: 1 point each (max 5)
    """
    score = 0
    max_score = 0

    for field_def in REQUIRED_FIELDS:
        field = field_def["field"]
        importance = field_def["importance"]

        if importance == "required":
            weight = 15
        elif importance == "recommended":
            weight = 5
        else:
            weight = 1

        max_score += weight

        value = profile_data.get(field)
        if _has_value(value):
            score += weight

    return min(100, int((score / max_score) * 100))


def _has_value(value: Any) -> bool:
    """Check if a field has a meaningful value."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def get_missing_fields(
    profile_data: dict[str, Any],
    include_optional: bool = False,
) -> list[dict[str, Any]]:
    """Get list of missing fields with importance levels."""
    missing = []

    for field_def in REQUIRED_FIELDS:
        field = field_def["field"]
        importance = field_def["importance"]

        if importance == "optional" and not include_optional:
            continue

        value = profile_data.get(field)
        if not _has_value(value):
            missing.append(
                {
                    "field": field,
                    "label": field_def["label"],
                    "importance": importance,
                    "asked": False,
                    "answered": False,
                }
            )

    # Sort by importance (required first)
    importance_order = {"required": 0, "recommended": 1, "optional": 2}
    missing.sort(key=lambda x: importance_order.get(x["importance"], 2))

    return missing


def get_job_specific_requirements(
    job: Job,
) -> list[dict[str, Any]]:
    """
    Get additional fields required for a specific job.

    Analyzes job description to determine what extra info is needed.
    """
    extra_fields: list[dict[str, Any]] = []

    # Use description_text since Job model has no 'requirements' field
    desc = job.description_text or ""
    desc_lower = desc.lower()

    if "clearance" in desc_lower or "secret" in desc_lower:
        extra_fields.append(
            {
                "field": "security_clearance",
                "label": "Security Clearance Level",
                "importance": "required",
                "asked": False,
                "answered": False,
            }
        )

    if "certified" in desc_lower or "certification" in desc_lower:
        extra_fields.append(
            {
                "field": "certifications",
                "label": "Relevant Certifications",
                "importance": "required",
                "asked": False,
                "answered": False,
            }
        )

    if "travel" in desc_lower:
        extra_fields.append(
            {
                "field": "willing_to_travel",
                "label": "Willingness to Travel",
                "importance": "recommended",
                "asked": False,
                "answered": False,
            }
        )

    return extra_fields


async def get_profile_data_from_parsed_resume(
    parsed_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract structured profile data from parsed resume."""
    profile: dict[str, Any] = {}

    # Direct mappings
    direct_fields = [
        ("name", "full_name"),
        ("email", "email"),
        ("phone", "phone"),
        ("location", "location"),
        ("summary", "summary"),
    ]

    for source, target in direct_fields:
        if source in parsed_data:
            profile[target] = parsed_data[source]

    # Skills
    if "skills" in parsed_data:
        skills = parsed_data["skills"]
        if isinstance(skills, list):
            profile["skills"] = skills
        elif isinstance(skills, str):
            profile["skills"] = [s.strip() for s in skills.split(",")]

    # Work history
    if "experience" in parsed_data:
        profile["work_history"] = parsed_data["experience"]

        if (
            isinstance(parsed_data["experience"], list)
            and len(parsed_data["experience"]) > 0
        ):
            profile["years_experience"] = _estimate_years_experience(
                parsed_data["experience"]
            )

            most_recent = parsed_data["experience"][0]
            if isinstance(most_recent, dict):
                profile["current_title"] = most_recent.get("title", "")

    # Education
    if "education" in parsed_data:
        profile["education"] = parsed_data["education"]

    # Certifications
    if "certifications" in parsed_data:
        profile["certifications"] = parsed_data["certifications"]

    return profile


def _estimate_years_experience(work_history: list) -> int:
    """Estimate total years of experience from work history."""
    return len(work_history) * 2  # Rough estimate


def generate_completeness_prompt(
    missing_fields: list[dict[str, Any]],
    custom_questions: list[dict[str, Any]],
    profile_data: dict[str, Any],
) -> str:
    """Generate a prompt for Sieve to collect missing information."""
    required_missing = [
        f for f in missing_fields if f["importance"] == "required" and not f["answered"]
    ]
    recommended_missing = [
        f
        for f in missing_fields
        if f["importance"] == "recommended" and not f["answered"]
    ]
    unanswered_questions = [q for q in custom_questions if not q.get("answered")]

    prompt_parts = []

    if required_missing:
        fields_str = ", ".join([f["label"] for f in required_missing[:3]])
        prompt_parts.append(f"Required information still needed: {fields_str}")

    if recommended_missing and len(required_missing) < 2:
        fields_str = ", ".join([f["label"] for f in recommended_missing[:2]])
        prompt_parts.append(f"Helpful to have: {fields_str}")

    if unanswered_questions:
        prompt_parts.append(
            f"Custom screening questions to ask: {len(unanswered_questions)}"
        )
        for q in unanswered_questions[:2]:
            hint = q.get("sieve_prompt_hint", "")
            prompt_parts.append(
                f"  - {q['question_text']}" + (f" (hint: {hint})" if hint else "")
            )

    if profile_data.get("current_title"):
        prompt_parts.append(
            f"Candidate's current role: {profile_data['current_title']}"
        )

    return "\n".join(prompt_parts)
