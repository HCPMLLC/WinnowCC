"""Shared text extraction utilities for PDF and DOCX files.

Moved from profile_parser.py to eliminate duplication across
resume_parse_job, batch_upload, recruiter_llm_reparse, and
cover_letter_scoring.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from PDF using pdfplumber.

    Handles multi-column layouts and tables.
    """
    try:
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                if text:
                    pages.append(text)

                # Also extract tables and append as pipe-delimited text
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        if row:
                            cells = [cell.strip() if cell else "" for cell in row]
                            line = " | ".join(c for c in cells if c)
                            if line:
                                pages.append(line)

        result = "\n".join(pages)
        if result.strip():
            logger.debug("PDF extracted with pdfplumber (%d chars)", len(result))
            return result

        # Fall through to pypdf if pdfplumber returned nothing
        logger.warning("pdfplumber returned empty text, falling back to pypdf")
    except Exception as exc:
        logger.warning("pdfplumber extraction failed (%s), falling back to pypdf", exc)

    # Fallback: pypdf
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    fallback_pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        fallback_pages.append(text)
    return "\n".join(fallback_pages)


def extract_text_from_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text(path: Path) -> str:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return extract_text_from_pdf(path)
    if extension == ".docx":
        return extract_text_from_docx(path)
    raise ValueError("Unsupported file type for extraction.")
