"""LLM-based resume parser using PROMPT9 system prompt.

Chain: OpenAI (primary) → Anthropic Claude (fallback) → regex (final).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROMPT9_PATH = Path(__file__).resolve().parents[2] / "PROMPT9_Resume_Parser.md"

_prompt9_cache: str | None = None


def _load_prompt9() -> str:
    """Read and cache the PROMPT9 system prompt file."""
    global _prompt9_cache
    if _prompt9_cache is None:
        _prompt9_cache = PROMPT9_PATH.read_text(encoding="utf-8")
    return _prompt9_cache


def is_llm_parser_available() -> bool:
    """Return True if enabled, at least one API key is set, and PROMPT9 exists."""
    enabled = os.getenv("LLM_PARSER_ENABLED", "true").lower() in ("true", "1", "yes")
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    has_prompt = PROMPT9_PATH.exists()
    return enabled and (has_openai or has_anthropic) and has_prompt


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


# ---------------------------------------------------------------------------
# LLM API call
# ---------------------------------------------------------------------------


def parse_resume_with_llm(resume_text: str) -> dict:
    """Call OpenAI API with PROMPT9 to parse resume text into structured JSON."""
    from openai import OpenAI  # lazy import — graceful if not installed

    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("LLM_PARSER_MODEL", "gpt-4o-mini")
    timeout = int(os.getenv("LLM_PARSER_TIMEOUT", "120"))

    system_prompt = _load_prompt9() + "\n\nReturn ONLY valid JSON, no markdown fences."

    client = OpenAI(api_key=api_key, timeout=timeout, max_retries=2)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Parse the following resume:\n\n{resume_text}",
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or ""

    # Defensive: strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("LLM response is not a JSON object")
    return result


# ---------------------------------------------------------------------------
# Anthropic Claude API call (fallback)
# ---------------------------------------------------------------------------


def parse_resume_with_claude(resume_text: str) -> dict:
    """Call Anthropic Claude API with PROMPT9.

    Parses resume text into structured JSON.
    """
    from anthropic import Anthropic  # lazy import

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    timeout = int(os.getenv("LLM_PARSER_TIMEOUT", "120"))

    system_prompt = _load_prompt9() + "\n\nReturn ONLY valid JSON, no markdown fences."

    client = Anthropic(api_key=api_key, timeout=timeout)
    response = client.messages.create(
        model=model,
        max_tokens=16384,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Parse the following resume:\n\n{resume_text}",
            },
        ],
        temperature=0.0,
    )

    raw = response.content[0].text or ""

    # Defensive: strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Claude response is not a JSON object")
    return result


# ---------------------------------------------------------------------------
# Mapper: PROMPT9 output → profile_json
# ---------------------------------------------------------------------------

from app.services.location_utils import normalize_city, normalize_state


def _format_location(city: str | None, state: str | None) -> str:
    """Format city and state into 'City, ST' string."""
    city = normalize_city(city)
    st = normalize_state(state)
    if city and st:
        return f"{city}, {st}"
    return city or st


def _split_name(full_name: str) -> tuple[str, str]:
    """Split full name: last word = last_name, rest = first_name."""
    parts = full_name.strip().split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (" ".join(parts[:-1]), parts[-1])


def _format_phone_number(raw: str | None) -> str:
    """Strip non-digits and format as (NNN) NNN-NNNN for US numbers."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return raw.strip()


def _normalize_date_to_mmm_yyyy(raw: str | None) -> str | None:
    """Convert YYYY-MM, YYYY, or 'Present' to MMM-YYYY format."""
    if not raw:
        return None
    val = raw.strip()
    if val.lower() in ("present", "current", "now", "ongoing"):
        return "Present"

    month_abbrevs = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    # YYYY-MM
    m = re.match(r"^(\d{4})-(\d{2})$", val)
    if m:
        year, month_num = m.groups()
        idx = int(month_num) - 1
        if 0 <= idx < 12:
            return f"{month_abbrevs[idx]}-{year}"
        return val

    # Already MMM-YYYY
    if re.match(r"^[A-Z][a-z]{2}-\d{4}$", val):
        return val

    # Bare year
    if re.match(r"^\d{4}$", val):
        return val

    return val


def _has_quantified_metric(text: str) -> bool:
    """Return True if text contains dollar amounts, percentages, or notable numbers."""
    return bool(re.search(r"\$[\d,]+|[\d,]+%|\b\d{2,}(?:,\d{3})*\b|\b\d+x\b", text))


def _calculate_total_years_from_experience(experience: list[dict]) -> int | None:
    """Sum actual employment durations, merging overlapping date ranges."""
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    # Full month name → number mapping
    full_month_map = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    def _to_date(val: str | None) -> date | None:
        if not val:
            return None
        val = val.strip()
        if val.lower() in ("present", "current", "now", "ongoing"):
            return date.today()
        # MMM-YYYY (e.g. "Jan-2020")
        m = re.match(r"([A-Za-z]{3})-(\d{4})", val)
        if m:
            mon = month_map.get(m.group(1).lower(), 1)
            return date(int(m.group(2)), mon, 1)
        # YYYY-MM (e.g. "2020-01")
        m = re.match(r"^(\d{4})-(\d{2})$", val)
        if m:
            return date(int(m.group(1)), int(m.group(2)), 1)
        # MM/YYYY (e.g. "01/2020")
        m = re.match(r"^(\d{1,2})/(\d{4})$", val)
        if m:
            return date(int(m.group(2)), int(m.group(1)), 1)
        # "Month YYYY" (e.g. "January 2020")
        m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", val)
        if m:
            mon = full_month_map.get(m.group(1).lower())
            if mon:
                return date(int(m.group(2)), mon, 1)
        # Bare year
        if re.match(r"^\d{4}$", val):
            return date(int(val), 1, 1)
        return None

    # Collect (start, end) date ranges for each job
    ranges: list[tuple[date, date]] = []
    for exp in experience:
        start = _to_date(exp.get("start_date"))
        if start is None:
            continue
        end = _to_date(exp.get("end_date"))
        if end is None:
            end = date.today()
        if end < start:
            start, end = end, start
        ranges.append((start, end))

    if not ranges:
        return None

    # Merge overlapping ranges to avoid double-counting
    ranges.sort()
    merged: list[tuple[date, date]] = [ranges[0]]
    for start, end in ranges[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    years = math.ceil(total_days / 365.25)
    return max(1, min(51, years))


_DATE_PATTERN = re.compile(
    r"^(?:"
    r"\d{4}-\d{2}"  # YYYY-MM
    r"|[A-Z][a-z]{2,8}\s+\d{4}"  # Mon YYYY or Month YYYY
    r"|[A-Z][a-z]{2}-\d{4}"  # Mon-YYYY
    r"|\d{1,2}/\d{4}"  # MM/YYYY
    r"|\d{4}"  # bare YYYY
    r")"
    r"(?:\s*[-–—to]+\s*"  # separator
    r"(?:\d{4}-\d{2}|[A-Z][a-z]{2,8}\s+\d{4}|[A-Z][a-z]{2}-\d{4}"
    r"|\d{1,2}/\d{4}|\d{4}|[Pp]resent|[Cc]urrent))?"
    r"$"
)

_LOCATION_PATTERN = re.compile(
    r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2}$"
)


_DEGREE_RE = re.compile(
    r"\b(?:Bachelor|Master|Doctor|Associate|Diploma|Certificate|Ph\.?D|M\.?[ABSF]\.?[A-Z]?"
    r"|B\.?[ABSF]\.?[A-Z]?|A\.?[ABS]\.?|D\.?[A-Z]\.?[A-Z]?|MBA|MFA|JD|MD|LLB|LLM"
    r"|Bachelor's|Master's|Doctorate)\b",
    re.IGNORECASE,
)


def _split_school_degree_field(
    school: str | None, degree: str | None, field: str | None
) -> tuple[str | None, str | None, str | None]:
    """Detect and fix merged education fields.

    E.g. school="MIT, Bachelor of Science in Computer Science" →
         school="MIT", degree="Bachelor of Science", field="Computer Science"
    """
    if not school:
        return school, degree, field

    raw = school.strip()

    # Only attempt splitting if the school field looks like it contains degree info
    if not _DEGREE_RE.search(raw):
        return school, degree, field

    # Try splitting on comma, dash, pipe
    for delim_re in [r"\s*,\s*", r"\s+-\s+", r"\s*\|\s*"]:
        parts = re.split(delim_re, raw, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            if _DEGREE_RE.search(right) and not _DEGREE_RE.search(left):
                new_school = left
                new_degree = right
                new_field = field
                if " in " in new_degree:
                    new_degree, new_field = new_degree.split(" in ", 1)
                    new_degree, new_field = new_degree.strip(), new_field.strip()
                return new_school, new_degree or degree, new_field or field
            elif _DEGREE_RE.search(left) and not _DEGREE_RE.search(right):
                new_school = right
                new_degree = left
                new_field = field
                if " in " in new_degree:
                    new_degree, new_field = new_degree.split(" in ", 1)
                    new_degree, new_field = new_degree.strip(), new_field.strip()
                return new_school, new_degree or degree, new_field or field

    # Whole school field is a degree string (no school name)
    if _DEGREE_RE.search(raw) and " in " in raw:
        new_degree, new_field = raw.split(" in ", 1)
        return None, new_degree.strip() or degree, new_field.strip() or field

    return school, degree, field


def _fix_misplaced_experience_fields(entry: dict) -> None:
    """Detect and fix misplaced data in experience entry fields.

    - If company looks like a date range, clear it
    - If title looks like a location (City, ST), move it to job_location
    - If dates are missing but date-like strings exist in company/title, extract
    """
    company = entry.get("company") or ""
    title = entry.get("title") or ""

    # Company contains a date pattern → misplaced, clear it
    if company and _DATE_PATTERN.match(company.strip()):
        logger.debug("Experience field fix: date in company field: %r", company)
        entry["company"] = None

    # Title looks like a location → move to job_location
    if title and _LOCATION_PATTERN.match(title.strip()):
        logger.debug("Experience field fix: location in title field: %r", title)
        if not entry.get("job_location"):
            entry["job_location"] = title.strip()
        entry["title"] = None


def map_llm_to_profile_json(llm: dict) -> dict:
    """Map PROMPT9 LLM output to the canonical profile_json schema."""
    from app.services.profile_parser import default_profile_json

    profile = default_profile_json()

    # ---- Basics ----
    contact = llm.get("contact_information") or {}
    basics: dict = profile["basics"]

    full_name = contact.get("full_name") or ""
    if full_name:
        basics["name"] = full_name
        first, last = _split_name(full_name)
        if first:
            basics["first_name"] = first
        if last:
            basics["last_name"] = last

    email = contact.get("email")
    if email:
        basics["email"] = email.strip()

    phone = contact.get("phone")
    if phone:
        basics["phone"] = _format_phone_number(phone)

    loc = contact.get("location") or {}
    location_str = _format_location(loc.get("city"), loc.get("state_province"))
    if location_str:
        basics["location"] = location_str

    summary = llm.get("professional_summary")
    if summary:
        basics["summary"] = summary

    # Total years
    yoe = llm.get("years_of_experience")
    if yoe is not None:
        try:
            basics["total_years_experience"] = math.ceil(float(yoe))
        except (ValueError, TypeError):
            pass

    # ---- Experience ----
    experience_out: list[dict] = []
    for job in llm.get("work_experience") or []:
        job_loc = job.get("location") or {}
        job_location_str = _format_location(
            job_loc.get("city"), job_loc.get("state_province")
        )

        duties_raw = job.get("duties") or []
        accomplishments_raw = job.get("accomplishments") or []
        # Normalize string → list before concatenation
        if isinstance(duties_raw, str):
            duties_raw = (
                [duties_raw] if duties_raw.strip() else []
            )
        if isinstance(accomplishments_raw, str):
            accomplishments_raw = (
                [accomplishments_raw]
                if accomplishments_raw.strip()
                else []
            )
        all_bullets = duties_raw + accomplishments_raw

        quantified = [b for b in accomplishments_raw if _has_quantified_metric(b)]

        # Flatten technologies_used: objects with name → list of names
        tech_list_raw = job.get("technologies_used") or []
        tech_names: list[str] = []
        for t in tech_list_raw:
            if isinstance(t, dict):
                name = t.get("name")
                if name:
                    tech_names.append(name)
            elif isinstance(t, str):
                tech_names.append(t)

        # Also pull environments_supported
        envs = job.get("environments_supported") or []
        for e in envs:
            if isinstance(e, str) and e and e not in tech_names:
                tech_names.append(e)

        domain_skills = job.get("domain_skills") or []

        exp_entry = {
            "company": job.get("company_name"),
            "title": job.get("job_title"),
            "job_location": job_location_str or None,
            "start_date": _normalize_date_to_mmm_yyyy(job.get("start_date")),
            "end_date": _normalize_date_to_mmm_yyyy(job.get("end_date")),
            "duties": all_bullets,
            "quantified_accomplishments": quantified,
            "skills_used": domain_skills,
            "technologies_used": tech_names,
        }

        # --- Defensive validation for misplaced field contents ---
        _fix_misplaced_experience_fields(exp_entry)

        # Normalize duties from string to list if needed
        if isinstance(exp_entry["duties"], str):
            raw_d = exp_entry["duties"]
            exp_entry["duties"] = (
                [raw_d] if raw_d.strip() else []
            )

        # Ensure skills_used and technologies_used are lists
        for key in ("skills_used", "technologies_used"):
            val = exp_entry.get(key)
            if isinstance(val, str):
                exp_entry[key] = [
                    s.strip()
                    for s in re.split(r"[,;|]", val)
                    if s.strip()
                ]

        # Filter out entries with no useful content
        has_company = bool(exp_entry.get("company"))
        has_title = bool(exp_entry.get("title"))
        has_duties = bool(exp_entry.get("duties"))
        if has_company or has_title or has_duties:
            experience_out.append(exp_entry)
        else:
            logger.debug("Filtered empty experience entry: %s", exp_entry)

    profile["experience"] = experience_out

    # ---- Education ----
    education_out: list[dict] = []
    for edu in llm.get("education") or []:
        school = edu.get("institution")
        degree = edu.get("degree_type")
        field = edu.get("field_of_study")

        # Split combined degree+field: "Bachelor of Arts in Org Psychology"
        if degree and not field and " in " in degree:
            parts = degree.split(" in ", 1)
            degree = parts[0].strip()
            field = parts[1].strip()

        # Fix merged education fields: school contains degree info
        school, degree, field = _split_school_degree_field(school, degree, field)

        education_out.append(
            {
                "school": school,
                "degree": degree,
                "field": field,
                "start_date": _normalize_date_to_mmm_yyyy(edu.get("start_date")),
                "end_date": _normalize_date_to_mmm_yyyy(edu.get("graduation_date")),
            }
        )
    profile["education"] = education_out

    # ---- Certifications ----
    skills_block = llm.get("skills") or {}
    certs_out: list[dict] = []
    for cert in skills_block.get("certifications") or []:
        certs_out.append(
            {
                "name": cert.get("name"),
                "issuer": cert.get("issuing_body"),
                "date_obtained": _normalize_date_to_mmm_yyyy(cert.get("date_obtained")),
                "expiry_date": _normalize_date_to_mmm_yyyy(cert.get("expiration_date")),
            }
        )
    profile["certifications"] = certs_out

    # ---- Skills (flat, deduped) ----
    seen_lower: set[str] = set()
    skill_names: list[str] = []

    def _add_skill(name: str) -> None:
        cleaned = name.strip()
        if not cleaned:
            return
        # Split concatenated skills: "Python, Java, React" or "Python; Java; React"
        if len(cleaned) > 50 or re.search(r"[,;|]", cleaned):
            parts = re.split(r"\s*[,;|]\s*", cleaned)
            if len(parts) > 1:
                for part in parts:
                    part = part.strip()
                    if part:
                        low = part.lower()
                        if low not in seen_lower:
                            seen_lower.add(low)
                            skill_names.append(part)
                return
        low = cleaned.lower()
        if low and low not in seen_lower:
            seen_lower.add(low)
            skill_names.append(cleaned)

    for ts in skills_block.get("technical_skills") or []:
        if isinstance(ts, dict):
            _add_skill(ts.get("name") or "")
        elif isinstance(ts, str):
            _add_skill(ts)

    for m in skills_block.get("methodologies") or []:
        if isinstance(m, str):
            _add_skill(m)

    for ss in skills_block.get("soft_skills") or []:
        if isinstance(ss, str):
            _add_skill(ss)

    for ik in skills_block.get("industry_knowledge") or []:
        if isinstance(ik, str):
            _add_skill(ik)

    # Collect from all work experience
    for job in llm.get("work_experience") or []:
        for t in job.get("technologies_used") or []:
            if isinstance(t, dict):
                _add_skill(t.get("name") or "")
            elif isinstance(t, str):
                _add_skill(t)
        for ds in job.get("domain_skills") or []:
            if isinstance(ds, str):
                _add_skill(ds)

    profile["skills"] = sorted(skill_names, key=str.lower)

    # ---- LLM Enrichment (extra data not in regex parser) ----
    enrichment: dict = {}

    if llm.get("primary_industry"):
        enrichment["primary_industry"] = llm["primary_industry"]
    if llm.get("primary_role_category"):
        enrichment["primary_role_category"] = llm["primary_role_category"]
    if llm.get("disambiguation_notes"):
        enrichment["disambiguation_notes"] = llm["disambiguation_notes"]

    # Contact URLs
    urls: dict[str, str] = {}
    if contact.get("linkedin_url"):
        urls["linkedin"] = contact["linkedin_url"]
    if contact.get("github_url"):
        urls["github"] = contact["github_url"]
    if contact.get("portfolio_url"):
        urls["portfolio"] = contact["portfolio_url"]
    if urls:
        enrichment["urls"] = urls

    # Management scopes per job
    mgmt_scopes: list[dict] = []
    for job in llm.get("work_experience") or []:
        scope = job.get("management_scope") or {}
        if any(
            scope.get(k) is not None
            for k in ("direct_reports", "budget_managed", "team_size")
        ):
            mgmt_scopes.append(
                {
                    "company": job.get("company_name"),
                    "title": job.get("job_title"),
                    "direct_reports": scope.get("direct_reports"),
                    "budget_managed": scope.get("budget_managed"),
                    "team_size": scope.get("team_size"),
                }
            )
    if mgmt_scopes:
        enrichment["management_scopes"] = mgmt_scopes

    # Additional sections
    additional = llm.get("additional_sections") or {}
    add_out: dict = {}
    for key in (
        "publications",
        "awards",
        "volunteer_work",
        "professional_affiliations",
    ):
        vals = additional.get(key)
        if vals and isinstance(vals, list) and any(v for v in vals):
            add_out[key] = [v for v in vals if v]
    if add_out:
        enrichment["additional_sections"] = add_out

    # Languages spoken
    langs_raw = skills_block.get("languages_spoken") or []
    langs: list[dict] = []
    for lang in langs_raw:
        if isinstance(lang, dict) and lang.get("language"):
            langs.append(lang)
        elif isinstance(lang, str) and lang:
            langs.append({"language": lang, "proficiency": None})
    if langs:
        enrichment["languages_spoken"] = langs

    # Licenses
    licenses_raw = skills_block.get("licenses") or []
    licenses: list[dict] = []
    for lic in licenses_raw:
        if isinstance(lic, dict) and lic.get("name"):
            licenses.append(lic)
    if licenses:
        enrichment["licenses"] = licenses

    # Technology contexts per job
    tech_contexts: list[dict] = []
    for job in llm.get("work_experience") or []:
        job_tech = job.get("technologies_used") or []
        contexts = [t for t in job_tech if isinstance(t, dict) and t.get("context")]
        if contexts:
            tech_contexts.append(
                {
                    "company": job.get("company_name"),
                    "title": job.get("job_title"),
                    "technologies": contexts,
                }
            )
    if tech_contexts:
        enrichment["technology_contexts"] = tech_contexts

    if enrichment:
        profile["llm_enrichment"] = enrichment

    return profile


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def _call_llm(resume_text: str) -> dict:
    """Try OpenAI first, then Claude. Raises on total failure."""
    last_exc: Exception | None = None

    if _has_openai_key():
        try:
            logger.info(
                "Trying OpenAI (%s)", os.getenv("LLM_PARSER_MODEL", "gpt-4o-mini")
            )
            return parse_resume_with_llm(resume_text)
        except Exception as exc:
            last_exc = exc
            logger.warning("OpenAI parse failed: %s", exc)

    if _has_anthropic_key():
        try:
            logger.info(
                "Trying Anthropic Claude (%s)",
                os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            )
            return parse_resume_with_claude(resume_text)
        except Exception as exc:
            last_exc = exc
            logger.warning("Claude parse failed: %s", exc)

    raise last_exc or RuntimeError("No LLM API keys configured")


def parse_with_llm(resume_text: str) -> dict:
    """Parse resume text using LLM (OpenAI / Claude).

    Returns canonical profile_json.
    """
    llm_output = _call_llm(resume_text)
    logger.debug("Raw LLM output for resume parse: %s", json.dumps(llm_output, default=str)[:5000])
    profile = map_llm_to_profile_json(llm_output)

    # Validate and fallback: calculate total_years if LLM didn't provide a valid value
    basics = profile.get("basics", {})
    tye = basics.get("total_years_experience")
    needs_calc = tye is None
    if not needs_calc:
        try:
            tye_int = int(tye)
            if tye_int < 1 or tye_int > 51:
                needs_calc = True
        except (ValueError, TypeError):
            needs_calc = True
    if needs_calc:
        years = _calculate_total_years_from_experience(profile.get("experience", []))
        if years is not None:
            basics["total_years_experience"] = years
        else:
            basics["total_years_experience"] = None

    return profile
