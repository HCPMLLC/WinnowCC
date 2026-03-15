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


def get_profile_data_from_parsed_resume(
    parsed_data: dict[str, Any],
) -> dict[str, Any]:
    """Extract structured profile data from parsed resume.

    Handles two formats:
    - Flat keys: name, email, phone, experience, skills (legacy / form-merged)
    - PROMPT9 raw output: contact_information, work_experience, skills.technical_skills
    """
    profile: dict[str, Any] = {}

    # Detect PROMPT9 format by presence of contact_information key
    is_prompt9 = "contact_information" in parsed_data

    if is_prompt9:
        _extract_prompt9(parsed_data, profile)
    else:
        _extract_flat(parsed_data, profile)

    return profile


def _extract_prompt9(parsed_data: dict[str, Any], profile: dict[str, Any]) -> None:
    """Extract profile fields from raw PROMPT9 LLM output."""
    contact = parsed_data.get("contact_information") or {}

    if contact.get("full_name"):
        profile["full_name"] = contact["full_name"]
    if contact.get("email"):
        profile["email"] = contact["email"]
    if contact.get("phone"):
        profile["phone"] = contact["phone"]

    # Location from contact_information.location (dict with city/state_province)
    loc = contact.get("location") or {}
    if isinstance(loc, dict):
        parts = [loc.get("city", ""), loc.get("state_province", "")]
        loc_str = ", ".join(p for p in parts if p)
        if loc_str:
            profile["location"] = loc_str
    elif isinstance(loc, str) and loc.strip():
        profile["location"] = loc.strip()

    if parsed_data.get("professional_summary"):
        profile["summary"] = parsed_data["professional_summary"]

    # Years of experience
    yoe = parsed_data.get("years_of_experience")
    if yoe is not None:
        try:
            profile["years_experience"] = int(float(yoe))
        except (ValueError, TypeError):
            pass

    # Work experience → work_history
    work_exp = parsed_data.get("work_experience") or []
    if isinstance(work_exp, list) and len(work_exp) > 0:
        profile["work_history"] = work_exp
        # Current title from most recent job
        most_recent = work_exp[0]
        if isinstance(most_recent, dict) and most_recent.get("job_title"):
            profile["current_title"] = most_recent["job_title"]
        # Estimate years if not explicitly provided
        if "years_experience" not in profile:
            profile["years_experience"] = _estimate_years_experience(work_exp)

    # Education
    education = parsed_data.get("education") or []
    if isinstance(education, list) and len(education) > 0:
        profile["education"] = education

    # Skills — PROMPT9 nests under skills.technical_skills, skills.methodologies, etc.
    skills_block = parsed_data.get("skills") or {}
    if isinstance(skills_block, dict):
        skill_names: list[str] = []
        for key in ("technical_skills", "methodologies", "soft_skills",
                     "tools", "frameworks", "languages"):
            for item in skills_block.get(key) or []:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    if name:
                        skill_names.append(name)
                elif isinstance(item, str) and item.strip():
                    skill_names.append(item.strip())
        # Also check certifications under skills
        certs = skills_block.get("certifications") or []
        if isinstance(certs, list) and len(certs) > 0:
            profile["certifications"] = certs
        if skill_names:
            profile["skills"] = skill_names
    elif isinstance(skills_block, list) and len(skills_block) > 0:
        # Fallback: skills is a flat list
        profile["skills"] = skills_block


def _extract_flat(parsed_data: dict[str, Any], profile: dict[str, Any]) -> None:
    """Extract profile fields from flat-key format (legacy / form-merged)."""
    # Direct mappings
    direct_fields = [
        ("name", "full_name"),
        ("full_name", "full_name"),
        ("email", "email"),
        ("phone", "phone"),
        ("location", "location"),
        ("summary", "summary"),
    ]

    for source, target in direct_fields:
        if source in parsed_data and parsed_data[source]:
            profile[target] = parsed_data[source]

    # Skills
    if "skills" in parsed_data:
        skills = parsed_data["skills"]
        if isinstance(skills, list):
            profile["skills"] = skills
        elif isinstance(skills, str):
            profile["skills"] = [s.strip() for s in skills.split(",")]

    # Work history (check both "experience" and "work_experience" keys)
    experience = parsed_data.get("experience") or parsed_data.get("work_experience")
    if experience:
        profile["work_history"] = experience

        if isinstance(experience, list) and len(experience) > 0:
            profile["years_experience"] = _estimate_years_experience(experience)

            most_recent = experience[0]
            if isinstance(most_recent, dict):
                title = most_recent.get("title") or most_recent.get("job_title", "")
                if title:
                    profile["current_title"] = title

    # Education
    if "education" in parsed_data:
        profile["education"] = parsed_data["education"]

    # Certifications
    if "certifications" in parsed_data:
        profile["certifications"] = parsed_data["certifications"]


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
