"""Job bias scanner — detects gendered, age-coded, and exclusionary language."""

import logging
import re

from app.models.employer import EmployerJob

logger = logging.getLogger(__name__)

# Gendered terms and inclusive alternatives
GENDERED_TERMS: dict[str, dict] = {
    "rockstar": {
        "suggestion": "top performer",
        "severity": "medium",
    },
    "ninja": {
        "suggestion": "expert",
        "severity": "medium",
    },
    "guru": {
        "suggestion": "specialist",
        "severity": "low",
    },
    "manpower": {
        "suggestion": "workforce",
        "severity": "high",
    },
    "chairman": {
        "suggestion": "chairperson",
        "severity": "high",
    },
    "hacker": {
        "suggestion": "developer",
        "severity": "low",
    },
    "he/she": {
        "suggestion": "they",
        "severity": "medium",
    },
    "his/her": {
        "suggestion": "their",
        "severity": "medium",
    },
    "salesman": {
        "suggestion": "salesperson",
        "severity": "high",
    },
    "craftsman": {
        "suggestion": "craftsperson",
        "severity": "high",
    },
    "man-hours": {
        "suggestion": "person-hours",
        "severity": "medium",
    },
    "guys": {
        "suggestion": "team",
        "severity": "low",
    },
    "aggressive": {
        "suggestion": "ambitious",
        "severity": "medium",
    },
    "dominant": {
        "suggestion": "leading",
        "severity": "medium",
    },
}

# Age-coded terms
AGE_CODED_TERMS: dict[str, dict] = {
    "digital native": {
        "suggestion": "tech-savvy",
        "severity": "high",
    },
    "energetic": {
        "suggestion": "motivated",
        "severity": "medium",
    },
    "young": {
        "suggestion": "early-career",
        "severity": "high",
    },
    "fresh graduate": {
        "suggestion": "recent graduate",
        "severity": "low",
    },
    "mature": {
        "suggestion": "experienced",
        "severity": "medium",
    },
    "youthful": {
        "suggestion": "dynamic",
        "severity": "high",
    },
}

# Exclusionary patterns (regex)
EXCLUSIONARY_PATTERNS: list[dict] = [
    {
        "pattern": r"must have (\d{2,})\+?\s*years",
        "type": "excessive_experience",
        "suggestion": "Consider whether this experience level is truly required.",
        "severity": "medium",
    },
    {
        "pattern": r"native (english|speaker)",
        "type": "language_discrimination",
        "suggestion": "Use 'fluent in English' or 'English proficiency required'.",
        "severity": "high",
    },
    {
        "pattern": r"culture fit",
        "type": "vague_exclusionary",
        "suggestion": "Use 'values alignment' with specific values listed.",
        "severity": "medium",
    },
    {
        "pattern": r"no felons|criminal background",
        "type": "ban_the_box",
        "suggestion": "Check local ban-the-box laws. "
        "Delay background check to post-offer.",
        "severity": "high",
    },
]


def scan_job_for_bias(job: EmployerJob) -> dict:
    """Scan a job posting for biased or exclusionary language.

    Returns:
        dict with bias_score (0-100), flags list, and
        inclusive_alternatives dict.
    """
    text = " ".join(
        filter(None, [job.title, job.description, job.requirements])
    ).lower()

    flags: list[dict] = []

    # Check gendered terms
    for term, info in GENDERED_TERMS.items():
        if term.lower() in text:
            flags.append(
                {
                    "type": "gendered",
                    "text": term,
                    "suggestion": info["suggestion"],
                    "severity": info["severity"],
                }
            )

    # Check age-coded terms
    for term, info in AGE_CODED_TERMS.items():
        if term.lower() in text:
            flags.append(
                {
                    "type": "age_coded",
                    "text": term,
                    "suggestion": info["suggestion"],
                    "severity": info["severity"],
                }
            )

    # Check exclusionary patterns
    for pattern_info in EXCLUSIONARY_PATTERNS:
        matches = re.findall(pattern_info["pattern"], text, re.IGNORECASE)
        if matches:
            flags.append(
                {
                    "type": pattern_info["type"],
                    "text": matches[0]
                    if isinstance(matches[0], str)
                    else " ".join(matches[0]),
                    "suggestion": pattern_info["suggestion"],
                    "severity": pattern_info["severity"],
                }
            )

    # Compute bias score
    severity_weights = {"low": 5, "medium": 15, "high": 25}
    raw_score = sum(severity_weights.get(f["severity"], 10) for f in flags)
    bias_score = min(100, raw_score)

    # Build inclusive alternatives map
    inclusive_alternatives = {}
    for f in flags:
        if f.get("suggestion"):
            inclusive_alternatives[f["text"]] = f["suggestion"]

    return {
        "bias_score": bias_score,
        "flags": flags,
        "inclusive_alternatives": inclusive_alternatives,
    }
