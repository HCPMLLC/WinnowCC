"""Tests for the document merger service."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.document_merger import apply_naming_convention


def test_naming_convention_basic():
    result = apply_naming_convention(
        "{last_name}_{first_name}_Application",
        last_name="Smith",
        first_name="John",
    )
    assert result == "Smith_John_Application"


def test_naming_convention_special_chars():
    result = apply_naming_convention(
        "{last_name}_{first_name}_Application",
        last_name="O'Brien",
        first_name="Mary Jane",
    )
    assert "OBrien" in result
    assert "Mary_Jane" in result


def test_naming_convention_missing_placeholder():
    result = apply_naming_convention(
        "{last_name}_{first_name}_{job_title}",
        last_name="Doe",
        first_name="Jane",
    )
    # job_title placeholder should be removed, no double underscores
    assert "__" not in result
    assert "Doe" in result
    assert "Jane" in result


def test_naming_convention_empty():
    result = apply_naming_convention("{missing}")
    assert result == "application_packet"


def test_merge_empty_documents():
    """Merging with no documents should create an empty-ish PDF."""
    from app.services.document_merger import PACKETS_DIR, merge_documents_to_pdf

    result = merge_documents_to_pdf(
        documents=[],
        output_filename="test_empty_merge",
    )
    # Should still create the file (empty PDF merger)
    assert result.endswith(".pdf")
    # Cleanup
    Path(result).unlink(missing_ok=True)


def test_merge_with_missing_files():
    """Missing files should be skipped gracefully."""
    from app.services.document_merger import merge_documents_to_pdf

    result = merge_documents_to_pdf(
        documents=[
            {"path": "/nonexistent/file.pdf", "type": "pdf", "label": "missing"},
        ],
        output_filename="test_missing_merge",
    )
    assert result.endswith(".pdf")
    Path(result).unlink(missing_ok=True)
