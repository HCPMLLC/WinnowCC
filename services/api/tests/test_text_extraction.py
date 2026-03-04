"""Tests for the shared text extraction module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.text_extraction import (
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


def test_extract_text_from_pdf_uses_pdfplumber(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello from PDF"
    mock_page.extract_tables.return_value = []

    mock_pdf_ctx = MagicMock()
    mock_pdf_ctx.pages = [mock_page]

    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf_ctx)
    mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
        result = extract_text_from_pdf(pdf_path)

    assert "Hello from PDF" in result


def test_extract_text_from_pdf_falls_back_to_pypdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"fake")

    # Make pdfplumber fail
    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.side_effect = Exception("pdfplumber failed")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Fallback text"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    mock_pypdf = MagicMock()
    mock_pypdf.PdfReader.return_value = mock_reader

    with patch.dict(
        sys.modules, {"pdfplumber": mock_pdfplumber, "pypdf": mock_pypdf}
    ):
        result = extract_text_from_pdf(pdf_path)

    assert "Fallback text" in result


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------


def test_extract_text_from_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "test.docx"
    docx_path.write_bytes(b"fake")

    mock_para = MagicMock()
    mock_para.text = "Resume paragraph"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]

    with patch("docx.Document", return_value=mock_doc):
        result = extract_text_from_docx(docx_path)

    assert "Resume paragraph" in result


# ---------------------------------------------------------------------------
# Router: extract_text
# ---------------------------------------------------------------------------


def test_extract_text_routes_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"fake")

    with patch(
        "app.services.text_extraction.extract_text_from_pdf",
        return_value="pdf content",
    ):
        result = extract_text(pdf_path)

    assert result == "pdf content"


def test_extract_text_routes_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "resume.docx"
    docx_path.write_bytes(b"fake")

    with patch(
        "app.services.text_extraction.extract_text_from_docx",
        return_value="docx content",
    ):
        result = extract_text(docx_path)

    assert result == "docx content"


def test_extract_text_raises_for_unsupported_type(tmp_path: Path) -> None:
    txt_path = tmp_path / "readme.txt"
    txt_path.write_bytes(b"hello")

    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(txt_path)
