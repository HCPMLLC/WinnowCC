"""Salary reference data for parsed job compensation estimation."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# (title_keyword, seniority) → (min, max, currency, salary_type)
_SALARY_TABLE: dict[tuple[str, str], tuple[int, int, str, str]] = {
    # Software Engineering
    ("software engineer", "junior"): (65_000, 95_000, "USD", "annual"),
    ("software engineer", "mid"): (95_000, 140_000, "USD", "annual"),
    ("software engineer", "senior"): (130_000, 180_000, "USD", "annual"),
    ("software engineer", "staff"): (160_000, 220_000, "USD", "annual"),
    ("software engineer", "principal"): (180_000, 260_000, "USD", "annual"),
    # Frontend / Full-Stack
    ("frontend engineer", "mid"): (90_000, 135_000, "USD", "annual"),
    ("frontend engineer", "senior"): (125_000, 175_000, "USD", "annual"),
    ("full stack", "mid"): (95_000, 140_000, "USD", "annual"),
    ("full stack", "senior"): (130_000, 180_000, "USD", "annual"),
    # Backend
    ("backend engineer", "mid"): (100_000, 145_000, "USD", "annual"),
    ("backend engineer", "senior"): (135_000, 185_000, "USD", "annual"),
    # Mobile
    ("mobile developer", "mid"): (95_000, 140_000, "USD", "annual"),
    ("mobile developer", "senior"): (130_000, 180_000, "USD", "annual"),
    ("ios developer", "mid"): (95_000, 140_000, "USD", "annual"),
    ("android developer", "mid"): (95_000, 140_000, "USD", "annual"),
    # Data Science
    ("data scientist", "junior"): (70_000, 100_000, "USD", "annual"),
    ("data scientist", "mid"): (100_000, 140_000, "USD", "annual"),
    ("data scientist", "senior"): (140_000, 190_000, "USD", "annual"),
    # Data Engineering
    ("data engineer", "mid"): (100_000, 145_000, "USD", "annual"),
    ("data engineer", "senior"): (135_000, 185_000, "USD", "annual"),
    # Data / BI Analyst
    ("data analyst", "junior"): (55_000, 75_000, "USD", "annual"),
    ("data analyst", "mid"): (72_000, 100_000, "USD", "annual"),
    ("data analyst", "senior"): (95_000, 130_000, "USD", "annual"),
    ("business intelligence", "mid"): (80_000, 115_000, "USD", "annual"),
    ("business intelligence", "senior"): (110_000, 150_000, "USD", "annual"),
    # Machine Learning / AI
    ("machine learning", "mid"): (110_000, 155_000, "USD", "annual"),
    ("machine learning", "senior"): (150_000, 210_000, "USD", "annual"),
    ("ai engineer", "mid"): (115_000, 160_000, "USD", "annual"),
    ("ai engineer", "senior"): (155_000, 220_000, "USD", "annual"),
    # DevOps / SRE / Platform
    ("devops engineer", "mid"): (100_000, 145_000, "USD", "annual"),
    ("devops engineer", "senior"): (135_000, 185_000, "USD", "annual"),
    ("sre", "mid"): (110_000, 155_000, "USD", "annual"),
    ("sre", "senior"): (145_000, 195_000, "USD", "annual"),
    ("platform engineer", "mid"): (105_000, 150_000, "USD", "annual"),
    ("platform engineer", "senior"): (140_000, 190_000, "USD", "annual"),
    # Cloud
    ("cloud engineer", "mid"): (105_000, 150_000, "USD", "annual"),
    ("cloud engineer", "senior"): (140_000, 190_000, "USD", "annual"),
    ("cloud architect", "senior"): (155_000, 215_000, "USD", "annual"),
    # Cybersecurity / Information Security
    ("cybersecurity", "junior"): (65_000, 90_000, "USD", "annual"),
    ("cybersecurity", "mid"): (90_000, 130_000, "USD", "annual"),
    ("cybersecurity", "senior"): (125_000, 175_000, "USD", "annual"),
    ("security engineer", "mid"): (105_000, 150_000, "USD", "annual"),
    ("security engineer", "senior"): (140_000, 195_000, "USD", "annual"),
    ("security analyst", "junior"): (60_000, 85_000, "USD", "annual"),
    ("security analyst", "mid"): (85_000, 120_000, "USD", "annual"),
    ("security analyst", "senior"): (115_000, 160_000, "USD", "annual"),
    ("information security", "mid"): (95_000, 135_000, "USD", "annual"),
    ("information security", "senior"): (130_000, 180_000, "USD", "annual"),
    ("penetration tester", "mid"): (90_000, 130_000, "USD", "annual"),
    ("penetration tester", "senior"): (125_000, 175_000, "USD", "annual"),
    # Network / Systems / Infrastructure
    ("network engineer", "mid"): (80_000, 115_000, "USD", "annual"),
    ("network engineer", "senior"): (110_000, 155_000, "USD", "annual"),
    ("systems administrator", "mid"): (70_000, 100_000, "USD", "annual"),
    ("systems administrator", "senior"): (95_000, 135_000, "USD", "annual"),
    ("systems engineer", "mid"): (85_000, 120_000, "USD", "annual"),
    ("systems engineer", "senior"): (115_000, 160_000, "USD", "annual"),
    ("infrastructure", "mid"): (90_000, 130_000, "USD", "annual"),
    ("infrastructure", "senior"): (125_000, 175_000, "USD", "annual"),
    # Database
    ("database administrator", "mid"): (80_000, 115_000, "USD", "annual"),
    ("database administrator", "senior"): (110_000, 155_000, "USD", "annual"),
    ("database engineer", "mid"): (90_000, 130_000, "USD", "annual"),
    ("database engineer", "senior"): (125_000, 170_000, "USD", "annual"),
    # Solutions / Enterprise Architect
    ("solutions architect", "mid"): (120_000, 165_000, "USD", "annual"),
    ("solutions architect", "senior"): (155_000, 215_000, "USD", "annual"),
    ("enterprise architect", "senior"): (160_000, 230_000, "USD", "annual"),
    # IT Support / Help Desk
    ("help desk", "junior"): (35_000, 50_000, "USD", "annual"),
    ("help desk", "mid"): (45_000, 65_000, "USD", "annual"),
    ("it support", "junior"): (38_000, 55_000, "USD", "annual"),
    ("it support", "mid"): (50_000, 72_000, "USD", "annual"),
    ("desktop support", "mid"): (48_000, 68_000, "USD", "annual"),
    # Project Management
    ("project manager", "mid"): (80_000, 115_000, "USD", "annual"),
    ("project manager", "senior"): (110_000, 150_000, "USD", "annual"),
    ("program manager", "mid"): (95_000, 135_000, "USD", "annual"),
    ("program manager", "senior"): (130_000, 175_000, "USD", "annual"),
    ("scrum master", "mid"): (85_000, 120_000, "USD", "annual"),
    ("scrum master", "senior"): (115_000, 155_000, "USD", "annual"),
    # Product Management
    ("product manager", "mid"): (100_000, 145_000, "USD", "annual"),
    ("product manager", "senior"): (140_000, 190_000, "USD", "annual"),
    ("product owner", "mid"): (90_000, 130_000, "USD", "annual"),
    ("product owner", "senior"): (125_000, 170_000, "USD", "annual"),
    # QA / Testing
    ("qa engineer", "mid"): (75_000, 110_000, "USD", "annual"),
    ("qa engineer", "senior"): (105_000, 145_000, "USD", "annual"),
    ("test engineer", "mid"): (75_000, 110_000, "USD", "annual"),
    ("sdet", "mid"): (90_000, 130_000, "USD", "annual"),
    ("sdet", "senior"): (125_000, 170_000, "USD", "annual"),
    # Design
    ("ux designer", "mid"): (80_000, 120_000, "USD", "annual"),
    ("ux designer", "senior"): (115_000, 160_000, "USD", "annual"),
    ("ui designer", "mid"): (75_000, 110_000, "USD", "annual"),
    ("product designer", "mid"): (90_000, 130_000, "USD", "annual"),
    ("product designer", "senior"): (125_000, 175_000, "USD", "annual"),
    ("graphic designer", "mid"): (55_000, 80_000, "USD", "annual"),
    # Business Analyst
    ("business analyst", "mid"): (70_000, 100_000, "USD", "annual"),
    ("business analyst", "senior"): (95_000, 135_000, "USD", "annual"),
    # Marketing
    ("marketing manager", "mid"): (70_000, 105_000, "USD", "annual"),
    ("marketing manager", "senior"): (100_000, 145_000, "USD", "annual"),
    ("digital marketing", "mid"): (60_000, 90_000, "USD", "annual"),
    ("seo", "mid"): (55_000, 85_000, "USD", "annual"),
    ("content strategist", "mid"): (60_000, 90_000, "USD", "annual"),
    # Sales
    ("sales engineer", "mid"): (90_000, 140_000, "USD", "annual"),
    ("sales engineer", "senior"): (130_000, 190_000, "USD", "annual"),
    ("account executive", "mid"): (65_000, 100_000, "USD", "annual"),
    ("account manager", "mid"): (60_000, 90_000, "USD", "annual"),
    # Finance / Accounting
    ("financial analyst", "mid"): (65_000, 95_000, "USD", "annual"),
    ("financial analyst", "senior"): (90_000, 130_000, "USD", "annual"),
    ("accountant", "mid"): (55_000, 80_000, "USD", "annual"),
    ("accountant", "senior"): (75_000, 110_000, "USD", "annual"),
    ("controller", "senior"): (100_000, 155_000, "USD", "annual"),
    # Human Resources
    ("hr manager", "mid"): (70_000, 100_000, "USD", "annual"),
    ("hr manager", "senior"): (95_000, 140_000, "USD", "annual"),
    ("recruiter", "mid"): (55_000, 80_000, "USD", "annual"),
    ("recruiter", "senior"): (75_000, 110_000, "USD", "annual"),
    ("talent acquisition", "mid"): (65_000, 95_000, "USD", "annual"),
    # Healthcare
    ("nurse", "mid"): (65_000, 90_000, "USD", "annual"),
    ("nurse practitioner", "mid"): (95_000, 130_000, "USD", "annual"),
    ("clinical", "mid"): (60_000, 90_000, "USD", "annual"),
    ("healthcare administrator", "mid"): (70_000, 105_000, "USD", "annual"),
    ("medical", "mid"): (65_000, 95_000, "USD", "annual"),
    # Legal
    ("paralegal", "mid"): (50_000, 75_000, "USD", "annual"),
    ("compliance", "mid"): (70_000, 105_000, "USD", "annual"),
    ("compliance", "senior"): (100_000, 150_000, "USD", "annual"),
    # Operations / Supply Chain
    ("operations manager", "mid"): (70_000, 105_000, "USD", "annual"),
    ("operations manager", "senior"): (100_000, 145_000, "USD", "annual"),
    ("supply chain", "mid"): (65_000, 95_000, "USD", "annual"),
    ("logistics", "mid"): (55_000, 80_000, "USD", "annual"),
    # Technical Writing / Documentation
    ("technical writer", "mid"): (70_000, 100_000, "USD", "annual"),
    ("technical writer", "senior"): (95_000, 135_000, "USD", "annual"),
    # Manager / Director / VP / C-Suite
    ("engineering manager", "manager"): (150_000, 210_000, "USD", "annual"),
    ("director", "executive"): (160_000, 250_000, "USD", "annual"),
    ("vp", "executive"): (180_000, 300_000, "USD", "annual"),
    ("cto", "executive"): (200_000, 350_000, "USD", "annual"),
    ("ciso", "executive"): (190_000, 320_000, "USD", "annual"),
    ("cfo", "executive"): (180_000, 300_000, "USD", "annual"),
}

# Keywords to match title against reference table keys (order matters — more
# specific keywords first to avoid partial matches on generic terms)
_TITLE_KEYWORDS = [
    # Engineering specialties (specific before generic)
    "frontend engineer",
    "backend engineer",
    "platform engineer",
    "security engineer",
    "network engineer",
    "systems engineer",
    "database engineer",
    "cloud engineer",
    "ai engineer",
    "sales engineer",
    "test engineer",
    "software engineer",
    # Cybersecurity / InfoSec
    "cybersecurity",
    "information security",
    "security analyst",
    "penetration tester",
    # Cloud / Architecture
    "cloud architect",
    "solutions architect",
    "enterprise architect",
    # Data
    "data scientist",
    "data engineer",
    "data analyst",
    "business intelligence",
    "machine learning",
    # DevOps / SRE / Infrastructure
    "devops engineer",
    "sre",
    "infrastructure",
    # Developer / Mobile
    "full stack",
    "mobile developer",
    "ios developer",
    "android developer",
    "sdet",
    # Systems / Network / DBA
    "systems administrator",
    "database administrator",
    "desktop support",
    "it support",
    "help desk",
    # Management
    "engineering manager",
    "program manager",
    "project manager",
    "product manager",
    "product owner",
    "scrum master",
    "operations manager",
    "marketing manager",
    "hr manager",
    "healthcare administrator",
    # Design
    "product designer",
    "ux designer",
    "ui designer",
    "graphic designer",
    # Analyst / Business
    "financial analyst",
    "business analyst",
    # Profession-specific
    "nurse practitioner",
    "nurse",
    "clinical",
    "medical",
    "accountant",
    "controller",
    "recruiter",
    "talent acquisition",
    "account executive",
    "account manager",
    "paralegal",
    "compliance",
    "supply chain",
    "logistics",
    "technical writer",
    "content strategist",
    "digital marketing",
    "seo",
    # Executive
    "ciso",
    "cto",
    "cfo",
    "director",
    "vp",
]


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens, expanding common compounds."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    # Expand known compound words so "cybersecurity" also produces {"cyber", "security"}
    _compounds = {
        "cybersecurity": {"cyber", "security"},
        "devops": {"dev", "ops"},
        "fullstack": {"full", "stack"},
        "frontend": {"front", "end"},
        "backend": {"back", "end"},
    }
    expanded = set()
    for w in words:
        expanded.add(w)
        if w in _compounds:
            expanded.update(_compounds[w])
    return expanded


def _token_overlap(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute overlap ratio between two token sets.

    Jaccard-like, biased to smaller set.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    smaller = min(len(tokens_a), len(tokens_b))
    return len(intersection) / smaller if smaller else 0.0


def get_supported_roles() -> list[str]:
    """Return the list of supported role title keywords for autocomplete."""
    return list(_TITLE_KEYWORDS)


def estimate_salary(
    title: str,
    seniority: str,
    city: str | None = None,
    industry: str | None = None,
) -> tuple[int, int, str, str] | None:
    """Estimate salary range for a job based on title and seniority.

    Uses a 3-pass approach:
      1. Exact substring match (fast)
      2. Token overlap (handles compound words like "cyber security" vs "cybersecurity")
      3. difflib.SequenceMatcher (handles typos and slight variations)

    Returns (min, max, currency, salary_type) or None if no match.
    """
    title_lower = title.lower()
    seniority_lower = seniority.lower() if seniority else "mid"

    # --- Pass 1: Exact substring (current behavior, fastest) ---
    matched_keyword = None
    for kw in _TITLE_KEYWORDS:
        if kw in title_lower:
            matched_keyword = kw
            break

    # --- Pass 2: Token overlap (handles compound words) ---
    if not matched_keyword:
        title_tokens = _tokenize(title_lower)
        best_overlap = 0.0
        best_kw = None
        for kw in _TITLE_KEYWORDS:
            kw_tokens = _tokenize(kw)
            overlap = _token_overlap(title_tokens, kw_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_kw = kw
        if best_overlap >= 0.6 and best_kw:
            matched_keyword = best_kw

    # --- Pass 3: SequenceMatcher (handles typos / slight variations) ---
    if not matched_keyword:
        best_ratio = 0.0
        best_kw = None
        for kw in _TITLE_KEYWORDS:
            ratio = SequenceMatcher(None, title_lower, kw).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_kw = kw
        if best_ratio >= 0.75 and best_kw:
            matched_keyword = best_kw

    if not matched_keyword:
        return None

    # Try exact seniority match
    result = _SALARY_TABLE.get((matched_keyword, seniority_lower))
    if result:
        return result

    # Fallback: try "mid" seniority
    result = _SALARY_TABLE.get((matched_keyword, "mid"))
    if result:
        return result

    return None
