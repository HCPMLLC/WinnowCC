"""
Profile completeness scoring service.

Scoring weights (100 points total):
- Basics (20 pts): first_name(3), last_name(2), email(3),
  phone(2), location(3), years_exp(4), work_auth(3)
- Experience (40 pts): has entries(15), company/title/dates/details per entry
- Education (15 pts): has entries(8), degree(4), field(3)
- Skills (15 pts): has skills(10), 5+ skills bonus(5)
- Preferences (10 pts): target_titles(5), locations(3), salary(2)
"""

from app.schemas.profile import ProfileCompletenessResponse, ProfileDeficiency


def compute_profile_completeness(profile_json: dict) -> ProfileCompletenessResponse:
    """Compute completeness score, deficiencies, and recommendations for a profile."""
    score = 0
    deficiencies: list[ProfileDeficiency] = []
    recommendations: list[str] = []

    basics = profile_json.get("basics") or {}
    experience = profile_json.get("experience") or []
    education = profile_json.get("education") or []
    skills = profile_json.get("skills") or []
    preferences = profile_json.get("preferences") or {}

    # --- Basics (20 pts) ---
    # First name (3 pts) and last name (2 pts) = 5 pts total
    if basics.get("first_name"):
        score += 3
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.first_name", message="First name is required", weight=3
            )
        )

    if basics.get("last_name"):
        score += 2
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.last_name", message="Last name is required", weight=2
            )
        )

    if basics.get("email"):
        score += 3
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.email", message="Email is missing", weight=3
            )
        )

    if basics.get("phone"):
        score += 2
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.phone", message="Phone number is missing", weight=2
            )
        )

    if basics.get("location"):
        score += 3
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.location", message="Location is missing", weight=3
            )
        )

    if basics.get("total_years_experience") is not None:
        score += 4
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.total_years_experience",
                message="Total years of experience is missing",
                weight=4,
            )
        )

    if basics.get("work_authorization"):
        score += 3
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="basics.work_authorization",
                message="Work authorization status is missing",
                weight=3,
            )
        )

    # --- Experience (40 pts) ---
    if len(experience) > 0:
        score += 15  # Has entries

        # Score each entry (up to 25 additional points distributed across entries)
        entry_points_total = 0
        max_entry_points = 25
        points_per_entry = max_entry_points / max(len(experience), 1)

        has_any_duties = False
        has_any_skills_used = False
        has_any_technologies = False
        has_any_accomplishments = False

        for entry in experience:
            entry_score = 0
            max_per_entry = points_per_entry
            # Company (20%)
            if entry.get("company"):
                entry_score += max_per_entry * 0.2
            # Title (20%)
            if entry.get("title"):
                entry_score += max_per_entry * 0.2
            # Dates (15%)
            if entry.get("start_date"):
                entry_score += max_per_entry * 0.1
            if entry.get("end_date") or entry.get("start_date"):
                entry_score += max_per_entry * 0.05
            # Content (45%)
            bullets = entry.get("bullets") or []
            duties = entry.get("duties") or []
            skills_used = entry.get("skills_used") or []
            technologies = entry.get("technologies_used") or []
            accomplishments = entry.get("quantified_accomplishments") or []

            content_items = len(bullets) + len(duties) + len(accomplishments)
            if content_items > 0:
                entry_score += max_per_entry * 0.25
            if len(skills_used) > 0:
                entry_score += max_per_entry * 0.1
                has_any_skills_used = True
            if len(technologies) > 0:
                entry_score += max_per_entry * 0.1
                has_any_technologies = True
            if len(duties) > 0:
                has_any_duties = True
            if len(accomplishments) > 0:
                has_any_accomplishments = True

            entry_points_total += entry_score

        score += int(min(entry_points_total, max_entry_points))

        # Recommendations for missing rich metadata
        if not has_any_duties:
            recommendations.append(
                "Add specific duties to your experience entries for better job matching"
            )
        if not has_any_skills_used:
            deficiencies.append(
                ProfileDeficiency(
                    field="experience.skills_used",
                    message="No skills listed in experience entries",
                    weight=3,
                )
            )
            recommendations.append(
                "List skills used in each role to highlight your expertise"
            )
        if not has_any_technologies:
            recommendations.append(
                "Add technologies used in each role for technical positions"
            )
        if not has_any_accomplishments:
            recommendations.append(
                "Include quantified accomplishments "
                "(e.g., 'Increased sales by 20%') "
                "to stand out"
            )
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="experience",
                message="No work experience entries",
                weight=40,
            )
        )
        recommendations.append("Add your work experience to enable job matching")

    # --- Education (15 pts) ---
    if len(education) > 0:
        score += 8  # Has entries

        has_degree = any(e.get("degree") for e in education)
        has_field = any(e.get("field") for e in education)

        if has_degree:
            score += 4
        else:
            deficiencies.append(
                ProfileDeficiency(
                    field="education.degree",
                    message="No degree specified in education",
                    weight=4,
                )
            )

        if has_field:
            score += 3
        else:
            deficiencies.append(
                ProfileDeficiency(
                    field="education.field",
                    message="No field of study specified",
                    weight=3,
                )
            )
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="education",
                message="No education entries",
                weight=15,
            )
        )

    # --- Skills (15 pts) ---
    if len(skills) > 0:
        score += 10  # Has skills
        if len(skills) >= 5:
            score += 5  # Bonus for 5+ skills
        else:
            deficiencies.append(
                ProfileDeficiency(
                    field="skills",
                    message=f"Only {len(skills)} skill(s) listed (5+ recommended)",
                    weight=5,
                )
            )
            recommendations.append("Add more skills to improve your match quality")
    else:
        deficiencies.append(
            ProfileDeficiency(field="skills", message="No skills listed", weight=15)
        )
        recommendations.append("Add your skills to enable accurate job matching")

    # --- Preferences (10 pts) ---
    target_titles = preferences.get("target_titles") or []
    locations = preferences.get("locations") or []
    salary_min = preferences.get("salary_min")
    salary_max = preferences.get("salary_max")

    if len(target_titles) > 0:
        score += 5
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="preferences.target_titles",
                message="No target job titles specified",
                weight=5,
            )
        )
        recommendations.append("Add target job titles to receive relevant matches")

    if len(locations) > 0 or preferences.get("remote_ok"):
        score += 3
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="preferences.locations",
                message="No preferred locations specified",
                weight=3,
            )
        )

    if salary_min is not None or salary_max is not None:
        score += 2
    else:
        deficiencies.append(
            ProfileDeficiency(
                field="preferences.salary",
                message="No salary preferences set",
                weight=2,
            )
        )

    # Sort deficiencies by weight (highest first)
    deficiencies.sort(key=lambda d: d.weight, reverse=True)

    # Generate priority recommendations based on critical deficiencies
    critical_fields = {"experience", "skills", "basics.first_name", "basics.last_name"}
    for d in deficiencies:
        if d.field in critical_fields and d.weight >= 10:
            if d.field == "experience":
                if "Upload your resume" not in recommendations:
                    recommendations.insert(
                        0, "Upload your resume to populate your profile"
                    )
            break

    return ProfileCompletenessResponse(
        score=min(score, 100),
        deficiencies=deficiencies,
        recommendations=recommendations,
    )
