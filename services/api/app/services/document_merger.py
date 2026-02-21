"""Document Merger — combines documents into a single PDF.

Uses PyPDF2 for PDF merging. DOCX-to-PDF conversion uses LibreOffice
headless (Linux/production) or docx2pdf (Windows/dev).
"""

import logging
import platform
import re
import subprocess
from pathlib import Path

from PyPDF2 import PdfMerger

logger = logging.getLogger(__name__)

FORMS_DIR = Path(__file__).resolve().parents[2] / "generated" / "forms"
PACKETS_DIR = Path(__file__).resolve().parents[2] / "generated" / "packets"


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
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)

    if naming_convention:
        output_filename = apply_naming_convention(naming_convention, **kwargs)

    if not output_filename.endswith(".pdf"):
        output_filename += ".pdf"

    output_path = PACKETS_DIR / output_filename

    merger = PdfMerger()
    temp_pdfs: list[Path] = []

    try:
        for doc in documents:
            doc_path = Path(doc["path"])
            if not doc_path.exists():
                logger.warning("Document not found, skipping: %s", doc_path)
                continue

            if doc_path.suffix.lower() == ".pdf":
                merger.append(str(doc_path))
            elif doc_path.suffix.lower() == ".docx":
                pdf_path = convert_docx_to_pdf(str(doc_path))
                if pdf_path:
                    merger.append(pdf_path)
                    temp_pdfs.append(Path(pdf_path))
                else:
                    logger.warning("DOCX conversion failed, skipping: %s", doc_path)
            else:
                logger.warning("Unsupported document type: %s", doc_path.suffix)

        merger.write(str(output_path))
    finally:
        merger.close()
        # Clean up temporary PDF conversions
        for tmp in temp_pdfs:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    logger.info("Merged %d documents into %s", len(documents), output_path)
    return str(output_path)


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
