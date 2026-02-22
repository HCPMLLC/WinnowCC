"""Document Merger — combines documents into a single PDF.

Uses PyPDF2 for PDF merging. DOCX-to-PDF conversion uses LibreOffice
headless (Linux/production) or docx2pdf (Windows/dev).
"""

import logging
import platform
import re
import subprocess
import tempfile
from pathlib import Path

from PyPDF2 import PdfMerger

from app.services.storage import download_to_tempfile, is_gcs_path, upload_file

logger = logging.getLogger(__name__)


def merge_documents_to_pdf(
    documents: list[dict],
    output_filename: str,
    naming_convention: str | None = None,
    **kwargs: str,
) -> str:
    """Merge multiple documents into a single PDF.

    Args:
        documents: List of {"path": str, "type": "pdf"|"docx", "label": str}
            ordered as they should appear in the final packet.
        output_filename: Base filename for the merged PDF.
        naming_convention: Optional naming template, e.g.
            "{last_name}_{first_name}_{job_title}_Application"
        **kwargs: Values for naming convention placeholders.

    Returns:
        Absolute path to the merged PDF.
    """
    if naming_convention:
        output_filename = apply_naming_convention(naming_convention, **kwargs)

    if not output_filename.endswith(".pdf"):
        output_filename += ".pdf"

    merger = PdfMerger()
    temp_files: list[Path] = []  # Track all temp files for cleanup

    try:
        for doc in documents:
            raw_path = doc["path"]
            # Download from GCS if needed
            suffix = Path(raw_path).suffix if not is_gcs_path(raw_path) else (
                ".pdf" if doc.get("type") == "pdf" else ".docx"
            )
            local_path = download_to_tempfile(raw_path, suffix=suffix)
            if is_gcs_path(raw_path):
                temp_files.append(local_path)

            if not local_path.exists():
                logger.warning("Document not found, skipping: %s", raw_path)
                continue

            if local_path.suffix.lower() == ".pdf":
                merger.append(str(local_path))
            elif local_path.suffix.lower() == ".docx":
                pdf_path = convert_docx_to_pdf(str(local_path))
                if pdf_path:
                    merger.append(pdf_path)
                    temp_files.append(Path(pdf_path))
                else:
                    logger.warning("DOCX conversion failed, skipping: %s", raw_path)
            else:
                logger.warning("Unsupported document type: %s", local_path.suffix)

        # Write merged PDF to a temp file, then upload to storage
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_out:
            tmp_out_path = Path(tmp_out.name)
        merger.write(str(tmp_out_path))
    finally:
        merger.close()
        for tmp in temp_files:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        stored_path = upload_file(tmp_out_path, "packets/", output_filename)
    finally:
        tmp_out_path.unlink(missing_ok=True)

    logger.info("Merged %d documents into %s", len(documents), stored_path)
    return stored_path


def convert_docx_to_pdf(docx_path: str) -> str | None:
    """Convert a DOCX file to PDF.

    Uses LibreOffice headless on Linux, docx2pdf on Windows.
    Returns the path to the generated PDF, or None on failure.
    """
    docx_file = Path(docx_path)
    pdf_path = docx_file.with_suffix(".pdf")

    if platform.system() == "Windows":
        return _convert_docx_windows(docx_path, str(pdf_path))
    return _convert_docx_libreoffice(docx_path, str(pdf_path))


def _convert_docx_libreoffice(docx_path: str, pdf_path: str) -> str | None:
    """Convert using LibreOffice headless (Linux/macOS)."""
    outdir = str(Path(pdf_path).parent)
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                outdir,
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and Path(pdf_path).exists():
            return pdf_path
        logger.error("LibreOffice conversion failed: %s", result.stderr)
    except FileNotFoundError:
        logger.error("LibreOffice not found. Install with: apt-get install libreoffice")
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out for: %s", docx_path)
    return None


def _convert_docx_windows(docx_path: str, pdf_path: str) -> str | None:
    """Convert using docx2pdf on Windows."""
    try:
        from docx2pdf import convert

        convert(docx_path, pdf_path)
        if Path(pdf_path).exists():
            return pdf_path
    except ImportError:
        logger.warning("docx2pdf not installed. Trying LibreOffice fallback.")
        return _convert_docx_libreoffice(docx_path, pdf_path)
    except Exception as exc:
        logger.error("docx2pdf conversion failed: %s", exc)
    return None


def apply_naming_convention(convention: str, **kwargs: str) -> str:
    """Apply a naming convention template with placeholder substitution.

    Example:
        convention = "{last_name}_{first_name}_{job_title}_Application"
        kwargs = {"last_name": "Smith", "first_name": "John", "job_title": "PM"}
        -> "Smith_John_PM_Application"
    """
    result = convention
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        safe_value = re.sub(r"[^\w\s-]", "", value).strip().replace(" ", "_")
        result = result.replace(placeholder, safe_value)

    # Remove any unfilled placeholders
    result = re.sub(r"\{[^}]+\}", "", result)
    # Clean up double underscores
    result = re.sub(r"_+", "_", result).strip("_")

    return result or "application_packet"
