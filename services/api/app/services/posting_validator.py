"""Posting validator — pre-distribution quality checks."""

import logging
import re

from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)

# US states requiring salary range disclosure (as of 2025)
SALARY_TRANSPARENCY_STATES = {
    "CO",
    "CA",
    "NY",
    "WA",
    "CT",
    "MD",
    "NV",
    "RI",
    "HI",
    "colorado",
    "california",
    "new york",
    "washington",
    "connecticut",
    "maryland",
    "nevada",
    "rhode island",
    "hawaii",
}

# Minimum description lengths by board
BOARD_MIN_LENGTHS: dict[str, int] = {
    "indeed": 150,
    "linkedin": 200,
    "google_jobs": 100,
    "ziprecruiter": 150,
    "usajobs": 200,
}

# PII patterns to detect
PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN detected"),
    (
        r"\b\d{3}[.\-]?\d{3}[.\-]?\d{4}\b",
        "Personal phone number detected",
    ),
]


def validate_posting(job: EmployerJob, board_type: str | None = None) -> dict:
    """Validate a job posting before distribution.

    Returns dict with:
      - valid: bool
      - checks: list of {name, status, message}
      - warnings: count
      - errors: count
    """
    checks: list[dict] = []

    # 1. EEO statement check
    desc = (job.description or "").lower()
    has_eeo = any(
        phrase in desc
        for phrase in [
            "equal opportunity",
            "eeo",
            "equal employment",
            "affirmative action",
        ]
    )
    checks.append(
        {
            "name": "eeo_statement",
            "status": "pass" if has_eeo else "warn",
            "message": "EEO statement present"
            if has_eeo
            else "No EEO statement found. Consider adding one.",
        }
    )

    # 2. Salary range check (state compliance)
    location = (job.location or "").lower()
    needs_salary = any(
        state.lower() in location for state in SALARY_TRANSPARENCY_STATES
    )
    has_salary = bool(job.salary_min or job.salary_max)

    if needs_salary and not has_salary:
        checks.append(
            {
                "name": "salary_transparency",
                "status": "fail",
                "message": "Salary range required for this location.",
            }
        )
    elif has_salary:
        checks.append(
            {
                "name": "salary_transparency",
                "status": "pass",
                "message": "Salary range included.",
            }
        )
    else:
        checks.append(
            {
                "name": "salary_transparency",
                "status": "warn",
                "message": "No salary range. Adding one improves "
                "application rates by 30%.",
            }
        )

    # 3. Apply URL check
    url = job.application_url or ""
    if url:
        checks.append(
            {
                "name": "apply_url",
                "status": "pass",
                "message": "Application URL provided.",
            }
        )
    else:
        checks.append(
            {
                "name": "apply_url",
                "status": "warn",
                "message": "No application URL. Candidates may not know how to apply.",
            }
        )

    # 4. Description length
    desc_len = len(job.description or "")
    min_len = BOARD_MIN_LENGTHS.get(board_type or "", 100)
    if desc_len >= min_len:
        checks.append(
            {
                "name": "description_length",
                "status": "pass",
                "message": f"Description length ({desc_len} chars) "
                f"meets minimum ({min_len}).",
            }
        )
    elif desc_len > 0:
        checks.append(
            {
                "name": "description_length",
                "status": "warn",
                "message": f"Description ({desc_len} chars) below "
                f"recommended minimum ({min_len}).",
            }
        )
    else:
        checks.append(
            {
                "name": "description_length",
                "status": "fail",
                "message": "Job description is empty.",
            }
        )

    # 5. PII check
    full_text = " ".join(filter(None, [job.title, job.description, job.requirements]))
    pii_found = False
    for pattern, label in PII_PATTERNS:
        if re.search(pattern, full_text):
            pii_found = True
            checks.append(
                {
                    "name": "pii_check",
                    "status": "fail",
                    "message": f"Potential PII found: {label}",
                }
            )
    if not pii_found:
        checks.append(
            {
                "name": "pii_check",
                "status": "pass",
                "message": "No PII detected.",
            }
        )

    # 6. Formatting check
    if job.description and "<script" in (job.description or "").lower():
        checks.append(
            {
                "name": "formatting",
                "status": "fail",
                "message": "Script tags detected in description.",
            }
        )
    else:
        checks.append(
            {
                "name": "formatting",
                "status": "pass",
                "message": "No formatting issues.",
            }
        )

    warnings = sum(1 for c in checks if c["status"] == "warn")
    errors = sum(1 for c in checks if c["status"] == "fail")

    return {
        "valid": errors == 0,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }
