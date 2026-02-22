"""Senior Recruiter Job Parser — structured extraction from job postings."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

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
