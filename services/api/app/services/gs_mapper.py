"""GS grade mapper — maps salary ranges to government GS grades."""

import logging

logger = logging.getLogger(__name__)

# 2025 GS base pay table (national, before locality adjustment)
# Source: OPM.gov general schedule pay tables
GS_BASE_PAY: dict[str, tuple[int, int]] = {
    "GS-1": (21_986, 27_485),
    "GS-2": (24_722, 31_165),
    "GS-3": (26_972, 35_064),
    "GS-4": (30_276, 39_360),
    "GS-5": (33_878, 44_043),
    "GS-6": (37_767, 49_106),
    "GS-7": (41_966, 54_554),
    "GS-8": (46_466, 60_405),
    "GS-9": (51_332, 66_731),
    "GS-10": (56_528, 73_485),
    "GS-11": (62_107, 80_737),
    "GS-12": (74_441, 96_770),
    "GS-13": (88_520, 115_079),
    "GS-14": (104_604, 135_987),
    "GS-15": (123_041, 159_950),
}

# Locality pay adjustment factors (approximate)
LOCALITY_ADJUSTMENTS: dict[str, float] = {
    "washington": 1.33,
    "dc": 1.33,
    "san francisco": 1.44,
    "new york": 1.37,
    "los angeles": 1.35,
    "chicago": 1.30,
    "houston": 1.35,
    "seattle": 1.34,
    "boston": 1.32,
    "denver": 1.31,
    "atlanta": 1.28,
    "dallas": 1.28,
    "rest of us": 1.17,
}


def map_salary_to_gs_grade(
    salary_min: int,
    salary_max: int,
    location: str | None = None,
) -> dict:
    """Map a salary range to the appropriate GS grade range.

    Accounts for locality pay tables when location is provided.

    Returns:
        dict with gs_low, gs_high, pay_plan, and locality_factor.
    """
    if not salary_min and not salary_max:
        return {
            "gs_low": None,
            "gs_high": None,
            "pay_plan": "GS",
            "locality_factor": 1.0,
            "message": "No salary data provided.",
        }

    # Determine locality factor
    locality_factor = _get_locality_factor(location)

    # Adjust GS ranges for locality
    adjusted_ranges: dict[str, tuple[int, int]] = {}
    for grade, (base_low, base_high) in GS_BASE_PAY.items():
        adjusted_ranges[grade] = (
            int(base_low * locality_factor),
            int(base_high * locality_factor),
        )

    # Find matching grades
    sal_min = salary_min or salary_max or 0
    sal_max = salary_max or salary_min or 0

    gs_low = None
    gs_high = None

    for grade, (low, high) in sorted(
        adjusted_ranges.items(),
        key=lambda x: x[1][0],
    ):
        if low <= sal_max and high >= sal_min:
            if gs_low is None:
                gs_low = grade
            gs_high = grade

    # If no match, find closest
    if gs_low is None:
        grades = sorted(adjusted_ranges.items(), key=lambda x: x[1][0])
        if sal_min < grades[0][1][0]:
            gs_low = gs_high = grades[0][0]
        else:
            gs_low = gs_high = grades[-1][0]

    return {
        "gs_low": gs_low,
        "gs_high": gs_high,
        "pay_plan": "GS",
        "locality_factor": round(locality_factor, 2),
        "salary_range_adjusted": {
            "min": sal_min,
            "max": sal_max,
        },
    }


def _get_locality_factor(location: str | None) -> float:
    """Get locality pay adjustment factor for a location."""
    if not location:
        return LOCALITY_ADJUSTMENTS["rest of us"]

    loc_lower = location.lower()
    for city, factor in LOCALITY_ADJUSTMENTS.items():
        if city in loc_lower:
            return factor

    return LOCALITY_ADJUSTMENTS["rest of us"]


def format_gs_posting(
    title: str,
    gs_grade_info: dict,
    description: str,
    requirements: str | None,
) -> dict:
    """Format a job posting for USAJobs submission.

    Converts standard job fields into USAJobs-compatible format.
    """
    gs_low = gs_grade_info.get("gs_low", "GS-9")
    gs_high = gs_grade_info.get("gs_high", gs_low)

    return {
        "position_title": title,
        "pay_plan": gs_grade_info.get("pay_plan", "GS"),
        "grade_low": gs_low.replace("GS-", "") if gs_low else "9",
        "grade_high": gs_high.replace("GS-", "") if gs_high else "15",
        "promotion_potential": (gs_high.replace("GS-", "") if gs_high else None),
        "major_duties": description,
        "qualifications": requirements or "",
        "who_may_apply": "United States Citizens",
        "hiring_path": "competitive",
        "security_clearance": "Not Required",
    }
