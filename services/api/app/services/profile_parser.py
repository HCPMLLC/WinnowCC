from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader

SECTION_HEADINGS = {
    "summary",
    "objective",
    "experience",
    "work experience",
    "professional experience",
    "education",
    "projects",
    "certifications",
    "skills",
}

SKILL_KEYWORDS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "fastapi",
    "sql",
    "postgres",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "excel",
    "tableau",
    "power bi",
]

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


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def extract_text_from_docx(path: Path) -> str:
    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text(path: Path) -> str:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    if extension == ".docx":
        return extract_text_from_docx(path)
    raise ValueError("Unsupported file type for extraction.")


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
        words = [word for word in line.split() if word.isalpha()]
        if 1 < len(words) <= 4 and len(line) <= 40:
            return line
    return None


def _extract_location(lines: list[str]) -> str | None:
    for line in lines[:15]:
        match = re.match(r"(location|address)\s*[:\-]\s*(.+)$", line, re.IGNORECASE)
        if match:
            value = match.group(2).strip()
            if value:
                return value
    return None


def _extract_skills(lines: list[str], text: str) -> list[str]:
    skills = []
    skills_section = _extract_section(lines, {"skills"})
    if skills_section:
        tokens = []
        for line in skills_section:
            cleaned = line.lstrip("-* ").strip()
            if cleaned:
                tokens.append(cleaned)
        skills_text = " ".join(tokens)
        for part in re.split(r"[,\|/;]", skills_text):
            item = part.strip()
            if item:
                skills.append(item)

    lowered_text = text.lower()
    for keyword in SKILL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered_text):
            skills.append(keyword)

    deduped = []
    seen = set()
    for skill in skills:
        normalized = skill.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _extract_experience(lines: list[str]) -> list[dict]:
    section = _extract_section(
        lines, {"experience", "work experience", "professional experience"}
    )
    return _parse_role_section(section)


def _extract_education(lines: list[str]) -> list[dict]:
    section = _extract_section(lines, {"education"})
    items = []
    for chunk in _split_chunks(section):
        if not chunk:
            continue
        first_line = chunk[0]
        school = first_line
        degree = None
        field = None
        if " - " in first_line:
            school, degree = [part.strip() for part in first_line.split(" - ", 1)]
        if degree and " in " in degree:
            degree, field = [part.strip() for part in degree.split(" in ", 1)]
        start_date, end_date = _extract_dates(chunk)
        if school:
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
    chunks = []
    current = []
    for line in lines:
        if not line.strip():
            if current:
                chunks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _parse_role_section(lines: list[str]) -> list[dict]:
    items = []
    for chunk in _split_chunks(lines):
        if not chunk:
            continue
        headline = chunk[0]
        company = None
        title = None
        if " at " in headline.lower():
            parts = re.split(r"\s+at\s+", headline, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                title = parts[0].strip()
                company = parts[1].strip()
        elif " - " in headline:
            left, right = [part.strip() for part in headline.split(" - ", 1)]
            if left and right:
                company = left
                title = right

        start_date, end_date = _extract_dates(chunk)
        bullets = [line.lstrip("-* ").strip() for line in chunk[1:] if line.startswith(("-", "*"))]
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
