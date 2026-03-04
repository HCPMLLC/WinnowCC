"""Unified Job Parser — single source of truth for all job parsing.

Contains:
  1. JobParserService (regex-based, for bulk ingestion pipeline)
  2. Unified Claude-powered parser with three entry points:
     - parse_job_from_file()  — for .docx/.pdf/.doc/.txt uploads
     - parse_job_from_text()  — for raw text from API feeds
     - estimate_parse_confidence() — quick heuristic check
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_parsed_detail import JobParsedDetail
from app.services.industry_map import infer_industry
from app.services.location_utils import normalize_city, normalize_state
from app.services.salary_reference import estimate_salary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Title abbreviation expansion
# ---------------------------------------------------------------------------
_TITLE_ABBREVIATIONS: dict[str, str] = {
    "sr.": "senior",
    "sr ": "senior ",
    "jr.": "junior",
    "jr ": "junior ",
    "mgr": "manager",
    "mgr.": "manager",
    "eng": "engineer",
    "eng.": "engineer",
    "dev": "developer",
    "dev.": "developer",
    "sw": "software",
    "swe": "software engineer",
    "pm": "project manager",
    "ba": "business analyst",
    "qa": "quality assurance",
    "ux": "user experience",
    "ui": "user interface",
    "vp": "vice president",
    "svp": "senior vice president",
    "avp": "assistant vice president",
    "dir": "director",
    "dir.": "director",
    "assoc": "associate",
    "assoc.": "associate",
    "admin": "administrator",
    "coord": "coordinator",
    "coord.": "coordinator",
    "tech": "technical",
    "ops": "operations",
    "infra": "infrastructure",
}

_SENIORITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:chief|cto|cio|cfo|ceo|c-level)\b", re.I), "executive"),
    (re.compile(r"\b(?:vp|vice president|svp|evp)\b", re.I), "executive"),
    (re.compile(r"\b(?:director|head of)\b", re.I), "director"),
    (re.compile(r"\b(?:principal|staff|distinguished)\b", re.I), "principal"),
    (re.compile(r"\b(?:senior|sr\.?)\b", re.I), "senior"),
    (re.compile(r"\b(?:manager|lead|team lead)\b", re.I), "manager"),
    (
        re.compile(r"\b(?:junior|jr\.?|entry[- ]level|associate|intern)\b", re.I),
        "junior",
    ),
]

# ---------------------------------------------------------------------------
# Employment type patterns
# ---------------------------------------------------------------------------
_EMPLOYMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:full[- ]?time)\b", re.I), "full-time"),
    (re.compile(r"\b(?:part[- ]?time)\b", re.I), "part-time"),
    (re.compile(r"\b(?:contract(?:or)?|c2c|corp[- ]to[- ]corp)\b", re.I), "contract"),
    (re.compile(r"\b(?:freelance|1099)\b", re.I), "freelance"),
    (re.compile(r"\b(?:temporary|temp)\b", re.I), "temporary"),
    (re.compile(r"\b(?:internship|intern)\b", re.I), "internship"),
]

_DURATION_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"(\d+)\s*(?:month|mo)\s*(?:contract|assignment|engagement)", re.I), 0),
    (re.compile(r"(\d+)\s*(?:year|yr)\s*(?:contract|assignment|engagement)", re.I), 0),
]

# ---------------------------------------------------------------------------
# Location / work mode
# ---------------------------------------------------------------------------
_WORK_MODE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:fully\s+remote|100%?\s*remote|remote[- ]only)\b", re.I),
        "remote",
    ),
    (re.compile(r"\b(?:hybrid|flex(?:ible)?)\b", re.I), "hybrid"),
    (re.compile(r"\b(?:on[- ]?site|in[- ]?office|in[- ]?person)\b", re.I), "onsite"),
    (re.compile(r"\bremote\b", re.I), "remote"),
]

_US_STATES: dict[str, str] = {
    "al": "Alabama",
    "ak": "Alaska",
    "az": "Arizona",
    "ar": "Arkansas",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ia": "Iowa",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "me": "Maine",
    "md": "Maryland",
    "ma": "Massachusetts",
    "mi": "Michigan",
    "mn": "Minnesota",
    "ms": "Mississippi",
    "mo": "Missouri",
    "mt": "Montana",
    "ne": "Nebraska",
    "nv": "Nevada",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "ny": "New York",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "vt": "Vermont",
    "va": "Virginia",
    "wa": "Washington",
    "wv": "West Virginia",
    "wi": "Wisconsin",
    "wy": "Wyoming",
    "dc": "District of Columbia",
}
_STATE_ABBREVS = {v.lower(): v for v in _US_STATES.values()}
_STATE_ABBREVS.update({k: _US_STATES[k] for k in _US_STATES})

# ---------------------------------------------------------------------------
# Salary extraction patterns
# ---------------------------------------------------------------------------
_SALARY_PATTERNS: list[re.Pattern[str]] = [
    # "$120k - $150k"
    re.compile(
        r"\$\s*([\d,.]+)\s*k?\s*[-–to]+\s*\$?\s*([\d,.]+)\s*k",
        re.I,
    ),
    # "$120,000 - $150,000" (also matches decimals)
    re.compile(
        r"\$\s*([\d,.]+)\s*[-–to]+\s*\$?\s*([\d,.]+)(?:\s*(?:per\s+)?(?:year|yr|annual|annum))?",
        re.I,
    ),
    # "$26.37 - $42.25/hr" or "$26.37/hr - $42.25/hr"
    re.compile(
        r"\$\s*([\d,.]+)\s*(?:/\s*(?:hr|hour))?\s*[-–to]+\s*"
        r"\$?\s*([\d,.]+)\s*(?:/|per\s*)\s*(?:hr|hour)",
        re.I,
    ),
    # "$65/hr" or "$65 per hour"
    re.compile(
        r"\$\s*([\d,.]+)\s*(?:/|per\s*)\s*(?:hr|hour)",
        re.I,
    ),
    # "up to $90/hr"
    re.compile(
        r"up\s+to\s+\$\s*([\d,.]+)\s*(?:/|per\s*)\s*(?:hr|hour)",
        re.I,
    ),
    # "$120,000/year"
    re.compile(
        r"\$\s*([\d,]+)\s*(?:/|per\s*)\s*(?:year|yr|annual|annum)",
        re.I,
    ),
]

# ---------------------------------------------------------------------------
# Section header patterns for requirements extraction
# ---------------------------------------------------------------------------
_REQUIREMENT_HEADERS = [
    "required qualifications",
    "requirements",
    "qualifications",
    "what we're looking for",
    "what we are looking for",
    "what you'll bring",
    "what you will bring",
    "must have",
    "must-have",
    "essential skills",
    "required skills",
    "minimum qualifications",
    "basic qualifications",
    "key requirements",
]

_PREFERRED_HEADERS = [
    "preferred qualifications",
    "nice to have",
    "nice-to-have",
    "preferred skills",
    "bonus qualifications",
    "desired skills",
    "preferred",
    "bonus",
]

_END_SECTION_HEADERS = [
    "responsibilities",
    "what you'll do",
    "what you will do",
    "about us",
    "about the company",
    "about the role",
    "benefits",
    "what we offer",
    "perks",
    "compensation",
    "how to apply",
]

# ---------------------------------------------------------------------------
# Certification patterns
# ---------------------------------------------------------------------------
_CERT_PATTERNS: list[str] = [
    "pmp",
    "prince2",
    "csm",
    "psm",
    "pmi-acp",
    "safe",
    "itil",
    "aws certified",
    "azure certified",
    "gcp certified",
    "cissp",
    "cism",
    "ceh",
    "comptia",
    "ccna",
    "ccnp",
    "cpa",
    "cfa",
    "frm",
    "six sigma",
    "lean six sigma",
    "scrum master",
    "product owner",
]

# ---------------------------------------------------------------------------
# Education patterns
# ---------------------------------------------------------------------------
_EDUCATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:ph\.?d|doctorate|doctoral)\b", re.I), "PhD"),
    (re.compile(r"\b(?:master'?s?|mba|m\.?s\.?|m\.?a\.?)\b", re.I), "Master's"),
    (
        re.compile(r"\b(?:bachelor'?s?|b\.?s\.?|b\.?a\.?|undergraduate)\b", re.I),
        "Bachelor's",
    ),
    (re.compile(r"\b(?:associate'?s?|a\.?s\.?|a\.?a\.?)\b", re.I), "Associate's"),
]

# ---------------------------------------------------------------------------
# Benefits keywords
# ---------------------------------------------------------------------------
_BENEFITS_KEYWORDS: list[str] = [
    "401k",
    "401(k)",
    "health insurance",
    "dental",
    "vision",
    "pto",
    "paid time off",
    "vacation",
    "parental leave",
    "stock options",
    "equity",
    "rsu",
    "bonus",
    "commission",
    "remote work",
    "flexible hours",
    "gym",
    "wellness",
    "tuition reimbursement",
    "professional development",
    "life insurance",
    "disability",
    "hsa",
    "fsa",
]

# ---------------------------------------------------------------------------
# Company size signals
# ---------------------------------------------------------------------------
_SIZE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:startup|early[- ]stage|seed)\b", re.I), "startup"),
    (re.compile(r"\b(?:small\s+(?:company|team|business)|smb)\b", re.I), "small"),
    (
        re.compile(r"\b(?:mid[- ]?size|growth[- ]stage|series\s+[b-d])\b", re.I),
        "mid-size",
    ),
    (
        re.compile(
            r"\b(?:enterprise|fortune\s+\d+|large[- ]?scale|global\s+company)\b", re.I
        ),
        "enterprise",
    ),
]

# ---------------------------------------------------------------------------
# Red flag keywords for quality scoring
# ---------------------------------------------------------------------------
_QUALITY_DEDUCTIONS: list[tuple[str, int, str]] = [
    # (check_description, deduction_points, red_flag_code)
    # These are evaluated in _compute_quality_score
]


class JobParserService:
    PARSE_VERSION = 1

    def parse(self, session: Session, job: Job) -> JobParsedDetail:
        """Parse a job posting and create/update a JobParsedDetail record."""
        text = job.description_text or ""
        title = job.title or ""
        location = job.location or ""
        company = job.company or ""

        # Title normalization
        normalized_title, seniority = self._normalize_title(title)

        # Employment type
        employment_type, duration = self._extract_employment_type(text)

        # Location
        city, state, country, work_mode, travel_pct, relocation = self._parse_location(
            title, location, text
        )

        # If job has remote_flag, override work_mode
        if job.remote_flag and work_mode != "hybrid":
            work_mode = "remote"

        # Compensation
        (sal_min, sal_max, sal_currency, sal_type, sal_confidence) = (
            self._extract_compensation(text, title, seniority, city)
        )

        # Use job's existing salary if parser couldn't find one
        if sal_min is None and job.salary_min is not None:
            sal_min = job.salary_min
            sal_max = job.salary_max
            sal_currency = job.currency or "USD"
            sal_type = "annual"
            sal_confidence = "source"

        # Requirements
        (
            required_skills,
            preferred_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibilities,
            qualifications,
        ) = self._extract_requirements(text)

        # Company intelligence
        industry = infer_industry(text, company)
        size_signal = self._detect_company_size(text)
        department, reports_to, team_size = self._extract_company_structure(text)

        # Benefits
        benefits = self._extract_benefits(text)

        # Look for existing parsed detail
        existing = session.execute(
            select(JobParsedDetail).where(JobParsedDetail.job_id == job.id)
        ).scalar_one_or_none()

        if existing:
            parsed = existing
        else:
            parsed = JobParsedDetail(job_id=job.id)

        # Populate all fields
        parsed.normalized_title = normalized_title
        parsed.seniority_level = seniority
        parsed.employment_type = employment_type
        parsed.estimated_duration_months = duration
        parsed.parsed_city = city
        parsed.parsed_state = state
        parsed.parsed_country = country
        parsed.work_mode = work_mode
        parsed.travel_percent = travel_pct
        parsed.relocation_offered = relocation
        parsed.parsed_salary_min = sal_min
        parsed.parsed_salary_max = sal_max
        parsed.parsed_salary_currency = sal_currency
        parsed.parsed_salary_type = sal_type
        parsed.salary_confidence = sal_confidence
        parsed.benefits_mentioned = benefits
        parsed.required_skills = required_skills
        parsed.preferred_skills = preferred_skills
        parsed.required_certifications = certs
        parsed.required_education = education
        parsed.years_experience_min = years_min
        parsed.years_experience_max = years_max
        parsed.tools_and_technologies = tools
        parsed.raw_responsibilities = responsibilities
        parsed.raw_qualifications = qualifications
        parsed.inferred_industry = industry
        parsed.company_size_signal = size_signal
        parsed.department = department
        parsed.reports_to = reports_to
        parsed.team_size = team_size
        parsed.parse_version = self.PARSE_VERSION
        parsed.parsed_at = datetime.now(UTC)

        # Quality score
        parsed.posting_quality_score = self._compute_quality_score(job, parsed)

        if not existing:
            session.add(parsed)
        session.flush()

        return parsed

    # -----------------------------------------------------------------
    # Sub-methods
    # -----------------------------------------------------------------

    def _normalize_title(self, title: str) -> tuple[str, str]:
        """Normalize title and detect seniority level.

        Returns (normalized_title, seniority_level).
        """
        normalized = title.strip()

        # Remove parenthetical content like "(Remote)" or "(Contract)"
        normalized = re.sub(r"\s*\([^)]*\)\s*", " ", normalized).strip()

        # Expand abbreviations (handle dotted abbreviations like "sr.", "eng.")
        lower = normalized.lower()
        for abbr, expansion in sorted(
            _TITLE_ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if abbr in lower:
                if abbr.endswith("."):
                    # For dotted abbreviations, match the literal string
                    pattern = re.compile(r"(?<!\w)" + re.escape(abbr) + r"(?!\w)", re.I)
                elif abbr.endswith(" "):
                    # For space-suffixed, simple replace
                    pattern = re.compile(r"\b" + re.escape(abbr.rstrip()), re.I)
                else:
                    pattern = re.compile(r"\b" + re.escape(abbr) + r"\b", re.I)
                normalized = pattern.sub(expansion, normalized)
                lower = normalized.lower()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Detect seniority
        seniority = "mid"
        for pattern, level in _SENIORITY_PATTERNS:
            if pattern.search(title):
                seniority = level
                break

        return normalized, seniority

    def _extract_employment_type(self, text: str) -> tuple[str | None, int | None]:
        """Extract employment type and estimated duration."""
        employment_type = None
        for pattern, emp_type in _EMPLOYMENT_PATTERNS:
            if pattern.search(text):
                employment_type = emp_type
                break

        duration = None
        for pattern, _ in _DURATION_PATTERNS:
            m = pattern.search(text)
            if m:
                val = int(m.group(1))
                # Check if it's years
                if "year" in m.group(0).lower() or "yr" in m.group(0).lower():
                    duration = val * 12
                else:
                    duration = val
                break

        return employment_type, duration

    def _parse_location(
        self, title: str, location: str, text: str
    ) -> tuple[str | None, str | None, str | None, str | None, int | None, bool | None]:
        """Parse location details.

        Returns (city, state, country, work_mode, travel_percent, relocation_offered).
        """
        # Work mode
        work_mode = None
        combined_text = f"{title} {location} {text}"
        for pattern, mode in _WORK_MODE_PATTERNS:
            if pattern.search(combined_text):
                work_mode = mode
                break

        # Parse city/state from location string (e.g., "San Francisco, CA")
        city, state, country = None, None, None
        if location:
            loc_clean = location.strip()
            # Try "City, ST" or "City, State" pattern
            m = re.match(r"^([^,]+),\s*([A-Za-z]{2,})\s*(?:,\s*(.+))?$", loc_clean)
            if m:
                city = m.group(1).strip()
                state_part = m.group(2).strip()
                # Check if it's a US state abbreviation
                if state_part.lower() in _US_STATES:
                    state = _US_STATES[state_part.lower()]
                    country = "US"
                elif state_part.lower() in _STATE_ABBREVS:
                    state = _STATE_ABBREVS[state_part.lower()]
                    country = "US"
                else:
                    state = state_part
                if m.group(3):
                    country = m.group(3).strip()
            elif "remote" in loc_clean.lower():
                work_mode = work_mode or "remote"
            else:
                city = loc_clean

        # Travel percent
        travel_pct = None
        travel_match = re.search(r"(\d{1,3})\s*%\s*travel", text, re.I)
        if travel_match:
            travel_pct = min(100, int(travel_match.group(1)))

        # Relocation
        relocation = None
        if re.search(
            r"\brelocation\s+(?:assist(?:ance)?|package|offered|provided|available)\b",
            text,
            re.I,
        ):
            relocation = True

        # Normalize city/state for consistent storage
        city = normalize_city(city) or None
        state = normalize_state(state) or state  # preserve non-US states as-is

        return city, state, country, work_mode, travel_pct, relocation

    def _extract_compensation(
        self, text: str, title: str, seniority: str, city: str | None
    ) -> tuple[int | None, int | None, str | None, str | None, str | None]:
        """Extract salary information from text.

        Returns (min, max, currency, salary_type, confidence).
        """
        # Try each salary pattern
        for pattern in _SALARY_PATTERNS:
            m = pattern.search(text)
            if m:
                groups = m.groups()
                if len(groups) == 1:
                    # Single value (e.g., "$65/hr" or "up to $90/hr")
                    val = self._parse_salary_value(groups[0])
                    if val is None:
                        continue
                    if "/hr" in m.group(0).lower() or "per hour" in m.group(0).lower():
                        # Hourly → annualize
                        annual = int(val * 2080)
                        if "up to" in m.group(0).lower():
                            return None, annual, "USD", "hourly", "parsed"
                        return annual, annual, "USD", "hourly", "parsed"
                    if "up to" in m.group(0).lower():
                        return None, int(val), "USD", "annual", "parsed"
                    return int(val), int(val), "USD", "annual", "parsed"
                elif len(groups) >= 2:
                    val1 = self._parse_salary_value(groups[0])
                    val2 = self._parse_salary_value(groups[1])
                    if val1 is None or val2 is None:
                        continue

                    sal_type = "annual"
                    match_text = m.group(0).lower()

                    # Check if hourly range
                    if "/hr" in match_text or "per hour" in match_text:
                        sal_type = "hourly"
                        val1 = val1 * 2080
                        val2 = val2 * 2080

                    # Check if "k" suffix
                    if "k" in match_text:
                        if val1 < 1000:
                            val1 *= 1000
                        if val2 < 1000:
                            val2 *= 1000

                    return int(val1), int(val2), "USD", sal_type, "parsed"

        # Fallback: use salary reference data
        ref = estimate_salary(title, seniority, city)
        if ref:
            return ref[0], ref[1], ref[2], ref[3], "estimated"

        return None, None, None, None, None

    def _parse_salary_value(self, raw: str) -> float | None:
        """Parse a salary string like '120,000' or '120' into a number."""
        try:
            cleaned = raw.replace(",", "").replace(" ", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _extract_requirements(
        self, text: str
    ) -> tuple[
        list[str],
        list[str],
        list[str],
        list[str],
        int | None,
        int | None,
        list[str],
        list[str],
        list[str],
    ]:
        """Extract skills, certs, education, years, tools.

        Also extracts responsibilities and qualifications.

        Returns (required_skills, preferred_skills, certs, education,
                 years_min, years_max, tools, responsibilities, qualifications).
        """
        lines = text.split("\n")
        required_section: list[str] = []
        preferred_section: list[str] = []
        responsibility_section: list[str] = []
        current_section = None

        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower:
                continue

            # Detect section headers
            if any(h in line_lower for h in _REQUIREMENT_HEADERS):
                current_section = "required"
                continue
            elif any(h in line_lower for h in _PREFERRED_HEADERS):
                current_section = "preferred"
                continue
            elif any(
                h in line_lower
                for h in [
                    "responsibilities",
                    "what you'll do",
                    "what you will do",
                    "key responsibilities",
                ]
            ):
                current_section = "responsibilities"
                continue
            elif any(h in line_lower for h in _END_SECTION_HEADERS):
                current_section = None
                continue

            if current_section == "required":
                required_section.append(line.strip())
            elif current_section == "preferred":
                preferred_section.append(line.strip())
            elif current_section == "responsibilities":
                responsibility_section.append(line.strip())

        # Extract certifications
        text_lower = text.lower()
        certs = []
        for cert in _CERT_PATTERNS:
            if cert in text_lower:
                certs.append(cert.upper() if len(cert) <= 5 else cert.title())

        # Extract education
        education = []
        for pattern, degree in _EDUCATION_PATTERNS:
            if pattern.search(text):
                education.append(degree)

        # Extract years of experience
        years_min, years_max = None, None
        year_patterns = [
            re.compile(
                r"(\d+)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)", re.I
            ),
            re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*(?:years?|yrs?)", re.I),
        ]
        for yp in year_patterns:
            ym = yp.search(text)
            if ym:
                if ym.lastindex and ym.lastindex >= 2:
                    years_min = int(ym.group(1))
                    years_max = int(ym.group(2))
                else:
                    years_min = int(ym.group(1))
                break

        # Extract tools & technologies from the full text
        # We look for common tool mentions not already covered by skills
        tools: list[str] = []
        tool_keywords = [
            "jira",
            "confluence",
            "slack",
            "github",
            "gitlab",
            "bitbucket",
            "jenkins",
            "circleci",
            "travis",
            "docker",
            "kubernetes",
            "terraform",
            "ansible",
            "puppet",
            "chef",
            "figma",
            "sketch",
            "adobe xd",
            "invision",
            "salesforce",
            "hubspot",
            "zendesk",
            "servicenow",
            "tableau",
            "power bi",
            "looker",
            "grafana",
            "datadog",
            "splunk",
            "elasticsearch",
            "kibana",
            "prometheus",
            "postman",
            "swagger",
            "sentry",
            "new relic",
        ]
        for tool in tool_keywords:
            if tool in text_lower:
                tools.append(tool.title() if len(tool) > 3 else tool.upper())

        # Extract skills from required/preferred sections
        from app.services.matching import _extract_skills_from_text

        req_text = " ".join(required_section)
        pref_text = " ".join(preferred_section)

        required_skills = (
            _extract_skills_from_text(req_text)
            if req_text
            else _extract_skills_from_text(text)
        )
        preferred_skills = _extract_skills_from_text(pref_text) if pref_text else []

        return (
            required_skills,
            preferred_skills,
            certs,
            education,
            years_min,
            years_max,
            tools,
            responsibility_section[:20],  # Cap at 20 items
            (required_section + preferred_section)[:20],
        )

    def _detect_company_size(self, text: str) -> str | None:
        """Detect company size signal from text."""
        for pattern, size in _SIZE_PATTERNS:
            if pattern.search(text):
                return size
        return None

    def _extract_company_structure(
        self, text: str
    ) -> tuple[str | None, str | None, str | None]:
        """Extract department, reports_to, team_size from text."""
        department = None
        reports_to = None
        team_size = None

        # Department
        dept_match = re.search(
            r"(?:department|team|division|group)[:\s]+([A-Za-z &/]+?)(?:\.|,|\n|$)",
            text,
            re.I,
        )
        if dept_match:
            department = dept_match.group(1).strip()[:100]

        # Reports to
        reports_match = re.search(
            r"report(?:s|ing)\s+(?:to|directly\s+to)\s+"
            r"(?:the\s+)?([A-Za-z ]+?)(?:\.|,|\n|$)",
            text,
            re.I,
        )
        if reports_match:
            reports_to = reports_match.group(1).strip()[:100]

        # Team size
        team_match = re.search(
            r"team\s+of\s+(\d+[-–]?\d*)\s*(?:people|members|engineers|developers)?",
            text,
            re.I,
        )
        if team_match:
            team_size = team_match.group(1).strip()

        return department, reports_to, team_size

    def _extract_benefits(self, text: str) -> list[str]:
        """Extract mentioned benefits from text."""
        text_lower = text.lower()
        found: list[str] = []
        for benefit in _BENEFITS_KEYWORDS:
            if benefit in text_lower:
                found.append(benefit)
        return found

    def _compute_quality_score(self, job: Job, parsed: JobParsedDetail) -> int:
        """Compute posting quality score (0-100).

        Higher = better quality posting with more information.
        """
        score = 50  # Base score

        # Title quality
        if parsed.normalized_title and len(parsed.normalized_title) > 10:
            score += 5
        if parsed.seniority_level and parsed.seniority_level != "mid":
            score += 3  # Explicit seniority is a good sign

        # Salary transparency
        if (
            parsed.parsed_salary_min is not None
            and parsed.salary_confidence == "parsed"
        ):
            score += 10
        elif (
            parsed.parsed_salary_min is not None
            and parsed.salary_confidence == "source"
        ):
            score += 5

        # Requirements clarity
        if parsed.required_skills and len(parsed.required_skills) >= 3:
            score += 8
        if parsed.required_education:
            score += 3
        if parsed.years_experience_min is not None:
            score += 3

        # Description length
        desc_len = len(job.description_text or "")
        if desc_len > 2000:
            score += 5
        elif desc_len > 1000:
            score += 3
        elif desc_len < 200:
            score -= 15  # Very short description is suspicious

        # Company details
        if parsed.inferred_industry:
            score += 3
        if parsed.department:
            score += 2
        if parsed.benefits_mentioned and len(parsed.benefits_mentioned) >= 3:
            score += 5

        # Employment type specified
        if parsed.employment_type:
            score += 3

        # Work mode clarity
        if parsed.work_mode:
            score += 2

        return max(0, min(100, score))


# ===========================================================================
# UNIFIED CLAUDE-POWERED PARSER (PROMPT77)
# ===========================================================================
# Everything below is the unified parser that consolidates PROMPT10, 14, and
# 43 into one service.  Three public entry points, one Claude prompt, one
# fraud/quality scorer.
# ===========================================================================

import anthropic  # noqa: E402 — intentional late import

_claude_client: anthropic.Anthropic | None = None

UNIFIED_PARSE_VERSION = 2


def _get_claude_client() -> anthropic.Anthropic:
    """Lazy-init singleton for the Anthropic API client."""
    global _claude_client
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_retries=3,
        )
    return _claude_client


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _detect_file_type(file_path: str) -> str:
    """Return 'docx', 'pdf', 'doc', 'txt', or 'unknown' based on extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".docx": "docx",
        ".pdf": "pdf",
        ".doc": "doc",
        ".txt": "txt",
    }.get(ext, "unknown")


def _extract_text_from_docx(file_path: str) -> str:
    """Extract text from .docx file including table content."""
    from docx import Document

    doc = Document(file_path)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts: list[str] = []

    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            t_elems = child.findall(".//w:t", ns)
            text = "".join(t.text or "" for t in t_elems).strip()
            if text:
                parts.append(text)
        elif tag == "tbl":
            for tr in child.findall(".//w:tr", ns):
                cells: list[str] = []
                for tc in tr.findall("w:tc", ns):
                    cell_texts = tc.findall(".//w:t", ns)
                    cell_text = "".join(t.text or "" for t in cell_texts).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    parts.append(" | ".join(cells))

    if not parts:
        parts = [p.text for p in doc.paragraphs if p.text.strip()]

    return "\n".join(parts)


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text from .pdf file using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text.strip())
        return "\n".join(parts)
    except Exception as e:
        logger.error("PDF text extraction failed: %s", e)
        return ""


def _extract_text_from_doc(file_path: str) -> str:
    """Extract text from .doc via LibreOffice conversion or olefile fallback."""
    from pathlib import Path as _Path

    from app.services.doc_converter import extract_text_from_doc

    try:
        return extract_text_from_doc(_Path(file_path))
    except Exception as e:
        logger.error(".doc extraction failed: %s", e)
        return ""


def _extract_text_from_file(file_path: str) -> str:
    """Dispatch to the appropriate text extractor based on file type."""
    ftype = _detect_file_type(file_path)
    if ftype == "txt":
        from pathlib import Path as _Path

        return _Path(file_path).read_text(encoding="utf-8", errors="replace")
    elif ftype == "pdf":
        return _extract_text_from_pdf(file_path)
    elif ftype == "doc":
        return _extract_text_from_doc(file_path)
    elif ftype == "docx":
        return _extract_text_from_docx(file_path)
    else:
        logger.warning("Unknown file type for %s, trying as docx", file_path)
        try:
            return _extract_text_from_docx(file_path)
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Claude parsing — THE SINGLE SOURCE OF TRUTH
# ---------------------------------------------------------------------------

_CLAUDE_PARSE_PROMPT = """\
You are an expert recruiter-grade job posting parser. Extract structured \
information from this job description with maximum precision.

Job Description:
{text}

Extract the following fields and return ONLY valid JSON:

{{
  "title": "Exact job title",
  "normalized_title": "Title with abbreviations expanded (Sr. -> Senior, etc.)",
  "seniority_level": "executive|director|principal|senior|manager|mid|junior or null",
  "department": "Department or team if mentioned, null otherwise",
  "job_category": "The EXACT category/labor category/functional area as written in \
the document. Do NOT map to a standard list. null if not mentioned",
  "job_id_external": "Job ID, requisition number, solicitation number, posting \
number, or vacancy number if mentioned, null otherwise",
  "company_name": "Company name if mentioned, null otherwise",
  "client_company_name": "The client, customer, end-client, hiring agency, or \
organization the work is performed for. For government contracts this is the agency \
name. null if not mentioned",

  "location": "Full location string if mentioned, null otherwise",
  "city": "City if mentioned, null otherwise",
  "state": "State/province if mentioned, null otherwise",
  "country": "Country if mentioned, null otherwise",
  "remote_policy": "on-site|hybrid|remote if mentioned, null otherwise",
  "travel_requirements": "Travel percentage or description \
if mentioned, null otherwise",
  "relocation_offered": true or false or null,

  "employment_type": "full-time|part-time|contract|internship|freelance|temporary \
if mentioned, null otherwise",
  "job_type": "permanent|contract|temporary|seasonal if mentioned, null otherwise",
  "duration_months": null or integer (for contracts),

  "start_date": "YYYY-MM-DD format if mentioned, null otherwise",
  "close_date": "YYYY-MM-DD format if mentioned, null otherwise",

  "salary_min": null or integer,
  "salary_max": null or integer,
  "salary_currency": "USD or other currency code, null if no salary",
  "salary_type": "annual|hourly|monthly, null if no salary",
  "equity_offered": true or false,
  "benefits_mentioned": ["list", "of", "benefits"] or [],

  "required_skills": [
    {{"skill": "Python", "years_needed": 3, "is_must_have": true}},
    {{"skill": "AWS", "years_needed": null, "is_must_have": true}}
  ],
  "preferred_skills": [
    {{"skill": "Kubernetes", "years_needed": null}}
  ],
  "certifications_required": ["PMP", "AWS Certified"] or [],
  "certifications_preferred": [] or null,
  "education_minimum": "Bachelor's in CS or equivalent, null if not mentioned",
  "years_experience_minimum": null or integer,
  "years_experience_preferred": null or integer,
  "clearance_required": "Secret|Top Secret|Public Trust or null",

  "description": "COMPLETE job description with ALL duties and scope. No truncation.",
  "requirements": "ALL required qualifications/skills. Include table content. \
null if not separable",
  "nice_to_haves": "ALL preferred qualifications. null if not distinguishable",
  "responsibilities": "Key responsibilities if a separate \
section exists, null otherwise",
  "benefits_text": "Benefits section text if exists, null otherwise",

  "application_email": "email if mentioned, null otherwise",
  "application_url": "URL to apply if mentioned, null otherwise",
  "company_industry": "Inferred industry \
(e.g. 'Technology', 'Finance'), null if unclear",
  "is_likely_recruiter_posting": true or false,
  "posting_quality_score": 0-100,

  "vague_language_score": 0-10,
  "excessive_urgency": true or false,
  "unrealistic_salary": true or false,
  "missing_company_details": true or false,
  "suspicious_contact_info": true or false
}}

Rules:
1. Extract ONLY information explicitly stated in the text
2. Do not infer or fabricate information
3. Use null for missing fields, [] for empty lists
4. Parse dates carefully - look for all date-related labels
5. Return ONLY the JSON object, no other text
6. For description and requirements, include ALL content - do NOT summarize or truncate
7. Content from tables is separated by " | " - include it in the appropriate field
8. For job_id_external: use any identifying number for the position
9. For title: use the actual position title, NOT the labor category
10. For required_skills: extract as structured objects with skill name and years
11. READ THE ENTIRE DOCUMENT before deciding on salary. For government contracts: \
use the official agency MAX NTE rate, NOT the vendor proposed rate
12. For certifications_required: extract ALL certifications mentioned as required
13. For posting_quality_score: rate 0-100 based on completeness, clarity, and detail
14. For client_company_name: in government contracts this is the agency name
"""


def _parse_with_claude(text: str) -> dict[str, Any]:
    """THE unified Claude prompt. All entry points call this same function."""
    # Truncate very long text to avoid token limits
    if len(text) > 100_000:
        text = text[:100_000] + "\n\n[Document truncated at 100,000 characters]"

    prompt = _CLAUDE_PARSE_PROMPT.format(text=text)

    try:
        client = _get_claude_client()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text.strip()

        # Strip markdown code fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return json.loads(response_text.strip())

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude JSON response: %s", e)
        return {}
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit balance" in msg or "billing" in msg.lower():
            raise RuntimeError(
                "AI service temporarily unavailable (billing). Please try again later."
            ) from e
        logger.error("Claude API call failed: %s", e)
        raise RuntimeError(f"AI parsing failed: {msg}") from e
    except anthropic.APIError as e:
        logger.error("Claude API call failed: %s", e)
        raise RuntimeError(
            "AI service temporarily unavailable. Please try again later."
        ) from e
    except Exception as e:
        logger.error("Claude API call failed unexpectedly: %s", e)
        return {}


def _regex_fallback_parse(text: str) -> dict[str, Any]:
    """Fallback parser when Claude API is unavailable.

    Uses the regex patterns from this module to extract basic fields.
    Returns a dict with confidence=0.1 so the job enters as a draft.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    title = lines[0][:200] if lines else "Untitled"

    # Detect seniority from title
    seniority = "mid"
    for pattern, level in _SENIORITY_PATTERNS:
        if pattern.search(title):
            seniority = level
            break

    # Employment type
    employment_type = None
    for pattern, emp_type in _EMPLOYMENT_PATTERNS:
        if pattern.search(text):
            employment_type = emp_type
            break

    # Work mode
    remote_policy = None
    for pattern, mode in _WORK_MODE_PATTERNS:
        if pattern.search(text):
            remote_policy = mode
            break

    return {
        "title": title,
        "normalized_title": title,
        "seniority_level": seniority,
        "description": text[:10000],
        "employment_type": employment_type,
        "remote_policy": remote_policy,
        "parsing_confidence": 0.1,
        "_fallback": True,
    }


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _post_process(parsed: dict[str, Any]) -> dict[str, Any]:
    """Clean and validate Claude output."""
    if not parsed:
        return parsed

    # Normalize title abbreviations
    title = parsed.get("title") or ""
    if title and not parsed.get("normalized_title"):
        normalized = title
        lower = normalized.lower()
        for abbr, expansion in sorted(
            _TITLE_ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if abbr in lower:
                if abbr.endswith("."):
                    pat = re.compile(r"(?<!\w)" + re.escape(abbr) + r"(?!\w)", re.I)
                elif abbr.endswith(" "):
                    pat = re.compile(r"\b" + re.escape(abbr.rstrip()), re.I)
                else:
                    pat = re.compile(r"\b" + re.escape(abbr) + r"\b", re.I)
                normalized = pat.sub(expansion, normalized)
                lower = normalized.lower()
        parsed["normalized_title"] = re.sub(r"\s+", " ", normalized).strip()

    # Detect seniority if not already set
    if not parsed.get("seniority_level") and title:
        for pattern, level in _SENIORITY_PATTERNS:
            if pattern.search(title):
                parsed["seniority_level"] = level
                break

    # Parse date strings to date objects
    for field in ("start_date", "close_date"):
        val = parsed.get(field)
        if val and isinstance(val, str):
            try:
                parsed[field] = datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                parsed[field] = None

    # Ensure list fields are lists
    for field in (
        "certifications_required",
        "certifications_preferred",
        "required_skills",
        "preferred_skills",
        "benefits_mentioned",
    ):
        val = parsed.get(field)
        if val and not isinstance(val, list):
            parsed[field] = [val]
        elif val is None:
            parsed[field] = []

    # Validate salary ranges
    sal_min = parsed.get("salary_min")
    sal_max = parsed.get("salary_max")
    if sal_min is not None and sal_max is not None:
        if isinstance(sal_min, (int, float)) and isinstance(sal_max, (int, float)):
            if sal_min > sal_max:
                parsed["salary_min"], parsed["salary_max"] = sal_max, sal_min

    # Calculate confidence score per PROMPT77 formula
    description = parsed.get("description") or ""
    required_skills = parsed.get("required_skills") or []
    location = parsed.get("location")
    confidence = (
        0.25 * (1.0 if title else 0.0)
        + 0.20
        * (
            1.0
            if description and len(description) > 100
            else 0.5
            if description
            else 0.0
        )
        + 0.20 * (1.0 if required_skills and len(required_skills) > 0 else 0.0)
        + 0.15 * (1.0 if location else 0.0)
        + 0.10 * (1.0 if sal_min or sal_max else 0.0)
        + 0.10 * (1.0 if parsed.get("employment_type") else 0.0)
    )
    parsed["parsing_confidence"] = round(confidence, 2)

    return parsed


# ---------------------------------------------------------------------------
# Fraud & quality scoring (dict-based)
# ---------------------------------------------------------------------------


def _score_quality_and_fraud(parsed: dict[str, Any], raw_text: str) -> dict[str, Any]:
    """Run fraud detection and quality scoring on a parsed dict.

    Imports phrase lists from job_fraud_detector.py to avoid duplication.
    Operates on raw dicts — no DB session needed.
    """
    from app.services.job_fraud_detector import (
        _CRYPTO_PHRASES,
        _FEE_PHRASES,
        _FREE_EMAIL_DOMAINS,
        _PERSONAL_INFO_PHRASES,
        _SCAM_PHRASES,
        _URGENCY_PHRASES,
        _VAGUE_TITLES,
        FRAUD_THRESHOLD,
    )

    red_flags: list[dict] = []
    total_score = 0
    text_lower = raw_text.lower()
    title_lower = (parsed.get("title") or "").lower()

    # 1. Scam phrases
    for phrase in _SCAM_PHRASES:
        if phrase in text_lower:
            total_score += 20
            red_flags.append(
                {
                    "code": "SCAM_PHRASE",
                    "severity": "high",
                    "description": f"Contains scam phrase: '{phrase}'",
                    "points": 20,
                }
            )
            break

    # 2. No company
    company = (
        parsed.get("company_name") or parsed.get("client_company_name") or ""
    ).strip()
    if not company or company.lower() in ("n/a", "unknown", "confidential", "company"):
        total_score += 15
        red_flags.append(
            {
                "code": "NO_COMPANY",
                "severity": "high",
                "description": "Company name is missing or generic",
                "points": 15,
            }
        )

    # 3. Short description
    if len(text_lower) < 100:
        total_score += 15
        red_flags.append(
            {
                "code": "SHORT_DESCRIPTION",
                "severity": "medium",
                "description": f"Description is only {len(text_lower)} characters",
                "points": 15,
            }
        )

    # 4. Salary anomaly
    sal_min = parsed.get("salary_min")
    sal_max = parsed.get("salary_max")
    if sal_min is not None and isinstance(sal_min, (int, float)):
        if sal_min > 500_000:
            total_score += 10
            red_flags.append(
                {
                    "code": "SALARY_ANOMALY",
                    "severity": "medium",
                    "description": f"Salary min ${sal_min:,.0f} is suspiciously high",
                    "points": 10,
                }
            )
    if sal_max is not None and isinstance(sal_max, (int, float)):
        if 0 < sal_max < 15_000:
            total_score += 10
            red_flags.append(
                {
                    "code": "SALARY_ANOMALY",
                    "severity": "medium",
                    "description": f"Salary max ${sal_max:,.0f} is suspiciously low",
                    "points": 10,
                }
            )

    # 5. No requirements
    req_skills = parsed.get("required_skills") or []
    certs = parsed.get("certifications_required") or []
    years_min = parsed.get("years_experience_minimum")
    if not req_skills and not certs and years_min is None:
        total_score += 10
        red_flags.append(
            {
                "code": "NO_REQUIREMENTS",
                "severity": "medium",
                "description": "No skills, certifications, or experience requirements",
                "points": 10,
            }
        )

    # 6. Urgency language
    for phrase in _URGENCY_PHRASES:
        if phrase in text_lower:
            total_score += 8
            red_flags.append(
                {
                    "code": "URGENCY_LANGUAGE",
                    "severity": "low",
                    "description": f"Urgency phrase: '{phrase}'",
                    "points": 8,
                }
            )
            break

    # 7. Personal info request
    for phrase in _PERSONAL_INFO_PHRASES:
        if phrase in text_lower:
            total_score += 20
            red_flags.append(
                {
                    "code": "PERSONAL_INFO_REQUEST",
                    "severity": "high",
                    "description": f"Requests personal information: '{phrase}'",
                    "points": 20,
                }
            )
            break

    # 8. Fee required
    for phrase in _FEE_PHRASES:
        if phrase in text_lower:
            total_score += 25
            red_flags.append(
                {
                    "code": "FEE_REQUIRED",
                    "severity": "high",
                    "description": f"Requires fee: '{phrase}'",
                    "points": 25,
                }
            )
            break

    # 9. Vague title
    if any(vt in title_lower for vt in _VAGUE_TITLES):
        total_score += 8
        red_flags.append(
            {
                "code": "VAGUE_TITLE",
                "severity": "low",
                "description": "Job title is vague or generic",
                "points": 8,
            }
        )

    # 10. Excessive caps
    title = parsed.get("title") or ""
    if title and sum(1 for c in title if c.isupper()) > len(title) * 0.6:
        total_score += 5
        red_flags.append(
            {
                "code": "EXCESSIVE_CAPS",
                "severity": "low",
                "description": "Excessive use of ALL CAPS in title",
                "points": 5,
            }
        )

    # 11. No location
    location = parsed.get("location") or ""
    remote = parsed.get("remote_policy") or ""
    if not location.strip() or location.strip().lower() in (
        "n/a",
        "unknown",
        "anywhere",
    ):
        if remote.lower() != "remote":
            total_score += 5
            red_flags.append(
                {
                    "code": "NO_LOCATION",
                    "severity": "low",
                    "description": "No meaningful location provided",
                    "points": 5,
                }
            )

    # 12. Crypto scam
    for phrase in _CRYPTO_PHRASES:
        if phrase in text_lower:
            total_score += 15
            red_flags.append(
                {
                    "code": "CRYPTO_SCAM",
                    "severity": "high",
                    "description": f"Crypto/forex signal: '{phrase}'",
                    "points": 15,
                }
            )
            break

    # 13. Free email for business
    app_email = (parsed.get("application_email") or "").lower()
    if app_email:
        for domain in _FREE_EMAIL_DOMAINS:
            if domain in app_email:
                total_score += 8
                red_flags.append(
                    {
                        "code": "GMAIL_CONTACT",
                        "severity": "medium",
                        "description": f"Business contact uses free email: {domain}",
                        "points": 8,
                    }
                )
                break

    # Combine Claude-reported fraud signals
    if parsed.get("excessive_urgency"):
        if not any(f["code"] == "URGENCY_LANGUAGE" for f in red_flags):
            total_score += 8
            red_flags.append(
                {
                    "code": "URGENCY_LANGUAGE",
                    "severity": "low",
                    "description": "Claude detected excessive urgency",
                    "points": 8,
                }
            )
    if parsed.get("unrealistic_salary"):
        if not any(f["code"] == "SALARY_ANOMALY" for f in red_flags):
            total_score += 10
            red_flags.append(
                {
                    "code": "SALARY_ANOMALY",
                    "severity": "medium",
                    "description": "Claude flagged salary as unrealistic",
                    "points": 10,
                }
            )

    parsed["fraud_score"] = total_score
    parsed["red_flags"] = red_flags
    parsed["is_likely_fraudulent"] = total_score >= FRAUD_THRESHOLD

    # Quality score
    quality = 50
    if parsed.get("normalized_title") and len(parsed["normalized_title"]) > 10:
        quality += 5
    if parsed.get("seniority_level") and parsed["seniority_level"] != "mid":
        quality += 3
    if sal_min is not None:
        quality += 10
    if req_skills and len(req_skills) >= 3:
        quality += 8
    if parsed.get("education_minimum"):
        quality += 3
    if parsed.get("years_experience_minimum") is not None:
        quality += 3
    desc = parsed.get("description") or ""
    if len(desc) > 2000:
        quality += 5
    elif len(desc) > 1000:
        quality += 3
    elif len(desc) < 200:
        quality -= 15
    if parsed.get("company_industry"):
        quality += 3
    if parsed.get("department"):
        quality += 2
    benefits = parsed.get("benefits_mentioned") or []
    if len(benefits) >= 3:
        quality += 5
    if parsed.get("employment_type"):
        quality += 3
    if parsed.get("remote_policy"):
        quality += 2
    parsed["quality_score"] = max(0, min(100, quality))

    return parsed


# ---------------------------------------------------------------------------
# Public Entry Points
# ---------------------------------------------------------------------------


def parse_job_from_file(
    file_path: str,
    source: str = "web_upload",
    employer_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Parse a .docx/.pdf/.doc/.txt job description file into structured data.

    Used by:
      - Employer web upload (POST /api/employer/jobs/upload-document)
      - Recruiter email ingest (email_ingest.py)
    """
    ftype = _detect_file_type(file_path)
    if ftype == "unknown":
        logger.warning("Unknown file type for %s", file_path)

    raw_text = _extract_text_from_file(file_path)
    if not raw_text.strip():
        return {}

    # Parse with Claude, fall back to regex if unavailable
    try:
        parsed = _parse_with_claude(raw_text)
    except RuntimeError:
        raise  # Billing errors should propagate
    except Exception:
        parsed = {}

    if not parsed:
        parsed = _regex_fallback_parse(raw_text)

    # Post-process and score
    parsed = _post_process(parsed)
    parsed = _score_quality_and_fraud(parsed, raw_text)

    # Add metadata
    parsed["source"] = source
    parsed["source_type"] = "file"
    if employer_id:
        parsed["employer_id"] = employer_id
    if user_id:
        parsed["user_id"] = user_id

    return parsed


def parse_job_from_text(
    raw_text: str,
    source: str = "api_feed",
    source_url: str | None = None,
    company_name: str | None = None,
) -> dict[str, Any]:
    """Parse raw job description text (already extracted from an API feed).

    Used by:
      - Job ingestion pipeline (job_ingestion.py / job_pipeline.py)
      - Admin re-parse endpoints
    """
    if not raw_text or not raw_text.strip():
        return {}

    # Parse with Claude, fall back to regex if unavailable
    try:
        parsed = _parse_with_claude(raw_text)
    except RuntimeError:
        raise
    except Exception:
        parsed = {}

    if not parsed:
        parsed = _regex_fallback_parse(raw_text)

    # Override company name if provided externally
    if company_name and not parsed.get("company_name"):
        parsed["company_name"] = company_name

    # Post-process and score
    parsed = _post_process(parsed)
    parsed = _score_quality_and_fraud(parsed, raw_text)

    # Add metadata
    parsed["source"] = source
    parsed["source_type"] = "text"
    if source_url:
        parsed["source_url"] = source_url

    return parsed


def estimate_parse_confidence(raw_text: str) -> float:
    """Quick heuristic confidence score without calling Claude.

    Checks text length, presence of key sections, formatting quality.
    Useful for pre-filtering before committing to an API call.
    """
    if not raw_text:
        return 0.0

    score = 0.0
    text_lower = raw_text.lower()

    # Text length (longer = more likely a real job posting)
    length = len(raw_text)
    if length > 2000:
        score += 0.25
    elif length > 500:
        score += 0.15
    elif length > 100:
        score += 0.05

    # Key section headers present
    section_keywords = [
        "requirements",
        "qualifications",
        "responsibilities",
        "about",
        "description",
        "skills",
        "experience",
        "benefits",
        "compensation",
        "salary",
    ]
    found_sections = sum(1 for kw in section_keywords if kw in text_lower)
    score += min(0.30, found_sections * 0.06)

    # Has a title-like first line (not too long, not empty)
    first_line = raw_text.strip().split("\n")[0].strip()
    if 5 < len(first_line) < 150:
        score += 0.15

    # Contains job-related terms
    job_terms = [
        "position",
        "role",
        "hiring",
        "apply",
        "candidate",
        "team",
        "company",
    ]
    found_terms = sum(1 for t in job_terms if t in text_lower)
    score += min(0.20, found_terms * 0.05)

    # Formatting quality (bullet points, structured content)
    bullet_count = raw_text.count("•") + raw_text.count("- ") + raw_text.count("* ")
    if bullet_count > 5:
        score += 0.10
    elif bullet_count > 0:
        score += 0.05

    return min(1.0, round(score, 2))


# ---------------------------------------------------------------------------
# DB storage helper
# ---------------------------------------------------------------------------


def store_parsed_details(
    job_id: int, parsed_data: dict[str, Any], session: Session
) -> JobParsedDetail:
    """Store unified parser output in the job_parsed_details table."""
    existing = session.execute(
        select(JobParsedDetail).where(JobParsedDetail.job_id == job_id)
    ).scalar_one_or_none()

    if existing:
        detail = existing
    else:
        detail = JobParsedDetail(job_id=job_id)

    # Map unified dict keys to JobParsedDetail columns
    field_map = {
        "normalized_title": "normalized_title",
        "seniority_level": "seniority_level",
        "employment_type": "employment_type",
        "duration_months": "estimated_duration_months",
        "city": "parsed_city",
        "state": "parsed_state",
        "country": "parsed_country",
        "remote_policy": "work_mode",
        "salary_min": "parsed_salary_min",
        "salary_max": "parsed_salary_max",
        "salary_currency": "parsed_salary_currency",
        "salary_type": "parsed_salary_type",
        "benefits_mentioned": "benefits_mentioned",
        "required_skills": "required_skills",
        "preferred_skills": "preferred_skills",
        "certifications_required": "required_certifications",
        "education_minimum": "required_education",
        "years_experience_minimum": "years_experience_min",
        "years_experience_preferred": "years_experience_max",
        "company_industry": "inferred_industry",
        "department": "department",
        "quality_score": "posting_quality_score",
        "fraud_score": "fraud_score",
        "is_likely_fraudulent": "is_likely_fraudulent",
        "red_flags": "red_flags",
    }

    for src_key, dst_attr in field_map.items():
        val = parsed_data.get(src_key)
        if val is not None and hasattr(detail, dst_attr):
            # Wrap scalar education in a list for JSONB column
            if dst_attr == "required_education" and isinstance(val, str):
                val = [val]
            setattr(detail, dst_attr, val)

    detail.parse_version = UNIFIED_PARSE_VERSION
    detail.parsed_at = datetime.now(UTC)

    if not existing:
        session.add(detail)
    session.flush()

    return detail


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def parse_job_document(file_path: str) -> dict[str, Any]:
    """Legacy alias for parse_job_from_file().

    Maintains backward compatibility with PROMPT43 callers.
    """
    return parse_job_from_file(file_path, source="web_upload")
