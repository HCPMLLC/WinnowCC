from __future__ import annotations

import logging
import re
from pathlib import Path

from app.services.text_extraction import (  # noqa: F401 — re-exported
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)

SECTION_HEADINGS = {
    "summary",
    "professional summary",
    "executive summary",
    "objective",
    "career objective",
    "experience",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
    "employment",
    "career history",
    "relevant experience",
    "education",
    "projects",
    "certifications",
    "skills",
}

ABOUT_HEADINGS = {
    "summary",
    "professional summary",
    "executive summary",
    "objective",
    "career objective",
    "about",
    "about me",
    "profile",
    "personal statement",
    "career summary",
    "overview",
}

EXPERIENCE_HEADINGS = {
    "experience",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
    "employment",
    "career history",
    "relevant experience",
}


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d().\-\s]{7,}\d)")
DATE_RANGE_RE = re.compile(
    r"(?P<start>(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4}|\d{4})"
    r"\s*(to|-)\s*"
    r"(?P<end>(Present|Current|Now|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4}|\d{4}))",
    re.IGNORECASE,
)


def default_profile_json() -> dict:
    return {
        "basics": {},
        "experience": [],
        "education": [],
        "skills": [],
        "preferences": {
            "target_titles": [],
            "locations": [],
            "remote_ok": None,
            "job_type": None,
            "salary_min": None,
            "salary_max": None,
        },
    }


def parse_profile_from_text(text: str) -> dict:
    profile = default_profile_json()
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    email = _extract_email(text)
    phone = _extract_phone(text)
    name = _extract_name(lines, email, phone)
    location = _extract_location(lines)

    basics: dict[str, str] = {}
    if name:
        basics["name"] = name
        parts = name.strip().split(None, 1)
        basics["first_name"] = parts[0] if parts else ""
        basics["last_name"] = parts[1] if len(parts) > 1 else ""
    if email:
        basics["email"] = email
    if phone:
        basics["phone"] = phone
    if location:
        basics["location"] = location

    profile["basics"] = basics
    profile["skills"] = _extract_skills(lines, text)
    profile["experience"] = _extract_experience(lines)
    profile["education"] = _extract_education(lines)

    about = _extract_about(lines)
    if about:
        profile["about"] = about

    return profile


def _extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def _extract_phone(text: str) -> str | None:
    for match in PHONE_RE.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if 10 <= len(digits) <= 15:
            return candidate
    return None


def _extract_name(lines: list[str], email: str | None, phone: str | None) -> str | None:
    for line in lines[:8]:
        lowered = line.lower()
        if email and email.lower() in lowered:
            continue
        if phone and phone in line:
            continue
        if any(char.isdigit() for char in line):
            continue
        # Skip lines that are section headings
        normalized = lowered.strip(" :")
        if normalized in SECTION_HEADINGS or normalized in ABOUT_HEADINGS:
            continue
        words = [word for word in line.split() if word.isalpha()]
        if 1 < len(words) <= 4 and len(line) <= 40:
            return line
    return None


def _extract_about(lines: list[str]) -> str | None:
    """Extract professional summary / about section text."""
    section = _extract_section(lines, ABOUT_HEADINGS)
    if not section:
        return None
    return " ".join(section).strip() or None


def _extract_location(lines: list[str]) -> str | None:
    for line in lines[:15]:
        match = re.match(r"(location|address)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if match:
            value = match.group(2).strip()
            if value:
                return value
    return None


_ENV_LINE_RE = re.compile(
    r"^(?:environment|technologies|tools|tech stack|platforms|software)\s*[:/]\s*(.+)$",
    re.IGNORECASE,
)
_PAREN_LIST_RE = re.compile(r"\(([^)]{5,})\)")


def _extract_skills(lines: list[str], text: str) -> list[str]:
    skills: list[str] = []

    # 1. Skills section
    skills_section = _extract_section(lines, {"skills"})
    if skills_section:
        tokens = []
        for line in skills_section:
            cleaned = line.lstrip("-* ").strip()
            if cleaned:
                tokens.append(cleaned)
        skills_text = " ".join(tokens)
        for part in re.split(r"[,|/;]", skills_text):
            item = part.strip()
            if item:
                skills.append(item)

    # 2. "Environment: / Technologies: / Tools:" lines anywhere in resume
    for line in lines:
        m = _ENV_LINE_RE.match(line)
        if m:
            for part in re.split(r"[,|;]", m.group(1)):
                item = part.strip()
                if item:
                    skills.append(item)

    # 3. Parenthetical lists in bullets: "Built API (Python, FastAPI, Redis)"
    for line in lines:
        for m in _PAREN_LIST_RE.finditer(line):
            inner = m.group(1)
            if "," in inner or ";" in inner or "|" in inner:
                for part in re.split(r"[,|;]", inner):
                    item = part.strip()
                    if item:
                        skills.append(item)

    # 4. Taxonomy matching (~600 skills with aliases)
    from app.services.skill_taxonomy import extract_skills_from_text, normalize_skills

    taxonomy_hits = extract_skills_from_text(text)
    skills.extend(taxonomy_hits)

    # Normalize all skills to canonical names and deduplicate
    return normalize_skills(skills)


def _extract_experience(lines: list[str]) -> list[dict]:
    section = _extract_section(lines, EXPERIENCE_HEADINGS)
    return _parse_role_section(section)


_DEGREE_PREFIXES_RE = re.compile(
    r"\b(?:Bachelor|Master|Doctor|Associate|Diploma|Certificate|Ph\.?D|M\.?[ABSF]\.?[A-Z]?"
    r"|B\.?[ABSF]\.?[A-Z]?|A\.?[ABS]\.?|D\.?[A-Z]\.?[A-Z]?|MBA|MFA|JD|MD|LLB|LLM"
    r"|Bachelor's|Master's|Doctorate)\b",
    re.IGNORECASE,
)


def _looks_like_degree(text: str) -> bool:
    """Return True if text looks like a degree designation."""
    return bool(_DEGREE_PREFIXES_RE.search(text))


def _split_school_degree_field(raw: str) -> tuple[str | None, str | None, str | None]:
    """Split a combined string into (school, degree, field).

    Handles formats like:
    - "MIT, Bachelor of Science in Computer Science"
    - "Bachelor of Science, University of Texas"
    - "MIT - BS in CS"
    - "MIT | Bachelor of Arts in Psychology"
    """
    if not raw or not raw.strip():
        return None, None, None

    raw = raw.strip()

    # Try splitting on common delimiters: comma, dash, pipe
    for delim_re in [r"\s*,\s*", r"\s+-\s+", r"\s*\|\s*"]:
        parts = re.split(delim_re, raw, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            if _looks_like_degree(right) and not _looks_like_degree(left):
                # "School, Degree..."
                degree = right
                field = None
                if " in " in degree:
                    degree, field = degree.split(" in ", 1)
                    degree, field = degree.strip(), field.strip()
                return left, degree, field
            elif _looks_like_degree(left) and not _looks_like_degree(right):
                # "Degree..., School"
                degree = left
                field = None
                if " in " in degree:
                    degree, field = degree.split(" in ", 1)
                    degree, field = degree.strip(), field.strip()
                return right, degree, field

    # No delimiter found or both/neither look like degrees — check for " in " pattern
    if " in " in raw and _looks_like_degree(raw):
        parts = raw.split(" in ", 1)
        return None, parts[0].strip(), parts[1].strip()

    return raw, None, None


def _extract_education(lines: list[str]) -> list[dict]:
    section = _extract_section(lines, {"education"})
    items: list[dict] = []
    for chunk in _split_chunks(section):
        if not chunk:
            continue

        first_line = chunk[0]
        school = None
        degree = None
        field = None

        # Try " - " format first (original logic)
        if " - " in first_line:
            left, right = [part.strip() for part in first_line.split(" - ", 1)]
            if _looks_like_degree(right):
                school = left
                degree = right
            elif _looks_like_degree(left):
                school = right
                degree = left
            else:
                school = left
                degree = right
            if degree and " in " in degree:
                degree, field = [part.strip() for part in degree.split(" in ", 1)]
        # Try comma or pipe split
        elif "," in first_line or "|" in first_line:
            school, degree, field = _split_school_degree_field(first_line)
        # Check for multi-line: school on line 1, degree on line 2
        elif len(chunk) >= 2 and _looks_like_degree(chunk[1]):
            school = first_line
            degree_line = chunk[1].strip()
            if " in " in degree_line:
                degree, field = degree_line.split(" in ", 1)
                degree, field = degree.strip(), field.strip()
            else:
                degree = degree_line
        # Single line that looks like a degree
        elif _looks_like_degree(first_line):
            school, degree, field = _split_school_degree_field(first_line)
        else:
            school = first_line

        start_date, end_date = _extract_dates(chunk)
        if school or degree:
            items.append(
                {
                    "school": school,
                    "degree": degree,
                    "field": field,
                    "start_date": start_date,
                    "end_date": end_date,
                }
            )
    return items


def _extract_section(lines: list[str], headings: set[str]) -> list[str]:
    start_index = None
    for idx, line in enumerate(lines):
        normalized = line.lower().strip(" :")
        if normalized in headings:
            start_index = idx + 1
            break
    if start_index is None:
        return []

    collected = []
    for line in lines[start_index:]:
        normalized = line.lower().strip(" :")
        if normalized in SECTION_HEADINGS:
            break
        collected.append(line)
    return collected


def _split_chunks(lines: list[str]) -> list[list[str]]:
    """Split lines into chunks, separated by blank lines or date range patterns.

    Many resumes don't have blank lines between experience entries, so we also
    look for lines containing date ranges as potential chunk boundaries.
    """
    chunks = []
    current = []

    for _i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            # Blank line - end current chunk
            if current:
                chunks.append(current)
                current = []
            continue

        # Check if this line starts a new chunk
        # (contains a date range and isn't a bullet)
        is_bullet = stripped.startswith(("-", "*", "•", "○", "►", "▪"))
        has_date = DATE_RANGE_RE.search(line) is not None

        # If line has a date range and isn't a bullet, it might be a new entry
        if has_date and not is_bullet and current:
            # Check if current chunk has at least one bullet or multiple lines
            # to avoid splitting too aggressively
            has_content = len(current) > 1 or any(
                ln.strip().startswith(("-", "*", "•", "○", "►", "▪")) for ln in current
            )
            if has_content:
                chunks.append(current)
                current = []

        current.append(line)

    if current:
        chunks.append(current)

    return chunks


_TITLE_WORDS = {
    "engineer",
    "manager",
    "developer",
    "analyst",
    "director",
    "specialist",
    "consultant",
    "lead",
    "senior",
    "junior",
    "associate",
    "coordinator",
    "administrator",
    "designer",
    "architect",
    "scientist",
    "intern",
    "executive",
    "officer",
    "president",
    "vp",
    "head",
}


def _has_title_word(text: str) -> bool:
    """Return True if text contains a common job title word."""
    low = text.lower()
    return any(word in low for word in _TITLE_WORDS)


def _parse_role_section(lines: list[str]) -> list[dict]:
    items = []
    for chunk in _split_chunks(lines):
        if not chunk:
            continue

        company = None
        title = None
        headline = chunk[0]

        # Try "Title at Company" format
        if " at " in headline.lower():
            parts = re.split(r"\s+at\s+", headline, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                title = parts[0].strip()
                company = parts[1].strip()
        # Try "Title | Company" or "Company | Title"
        elif " | " in headline:
            left, right = [part.strip() for part in headline.split(" | ", 1)]
            if left and right:
                right_is_title = _has_title_word(right)
                left_is_title = _has_title_word(left)
                if right_is_title:
                    company = left
                    title = right
                elif left_is_title:
                    title = left
                    company = right
                else:
                    title = left
                    company = right
        # Try "Title (Company)" parenthetical format
        elif re.search(r"\(([^)]+)\)\s*$", headline):
            m = re.search(r"^(.+?)\s*\(([^)]+)\)\s*$", headline)
            if m:
                title = m.group(1).strip()
                company = m.group(2).strip()
        # Try "Company - Title" or "Title - Company" format
        elif " - " in headline:
            left, right = [part.strip() for part in headline.split(" - ", 1)]
            if left and right:
                if _has_title_word(right):
                    company = left
                    title = right
                else:
                    company = left
                    title = right
        # Try to extract from separate lines (common format)
        elif len(chunk) >= 2:
            line1 = chunk[0].strip()
            is_bullet = chunk[1].startswith(("-", "*", "•"))
            line2 = chunk[1].strip() if not is_bullet else None

            if line2:
                clean_line1 = DATE_RANGE_RE.sub("", line1).strip()
                clean_line2 = DATE_RANGE_RE.sub("", line2).strip()

                if _has_title_word(line2):
                    company = clean_line1 or None
                    title = clean_line2 or None
                elif _has_title_word(line1):
                    title = clean_line1 or None
                    company = clean_line2 or None
                else:
                    company = clean_line1 or None
                    title = clean_line2 or None

        # If still no company/title, use headline as company (fallback)
        if not company and not title and headline:
            # Remove dates from headline
            clean_headline = DATE_RANGE_RE.sub("", headline).strip()
            if clean_headline:
                company = clean_headline

        start_date, end_date = _extract_dates(chunk)
        # Extract bullets from any line starting with bullet characters
        bullets = []
        for line in chunk[1:]:
            stripped = line.strip()
            if stripped.startswith(("-", "*", "•", "○", "►", "▪")):
                bullet_text = stripped.lstrip("-*•○►▪ ").strip()
                if bullet_text:
                    bullets.append(bullet_text)

        if company or title or bullets or start_date or end_date:
            items.append(
                {
                    "company": company,
                    "title": title,
                    "start_date": start_date,
                    "end_date": end_date,
                    "bullets": bullets,
                }
            )
    return items


def _extract_dates(chunk: list[str]) -> tuple[str | None, str | None]:
    combined = " ".join(chunk)
    match = DATE_RANGE_RE.search(combined)
    if not match:
        return None, None
    return match.group("start"), match.group("end")
