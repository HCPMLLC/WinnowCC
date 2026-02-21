"""Convert legacy .doc (Word 97-2003) files to .docx or extract raw text."""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_doc_to_docx(doc_path: Path) -> Path:
    """Convert a .doc file to .docx using LibreOffice headless.

    Returns the path to the converted .docx in a temporary directory.
    Caller is responsible for cleaning up the temp directory.
    Raises RuntimeError if conversion fails.
    """
    tmp_dir = tempfile.mkdtemp(prefix="doc2docx_")
    try:
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                tmp_dir,
                str(doc_path),
            ],
            timeout=30,
            capture_output=True,
            check=True,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"LibreOffice conversion failed: {exc}") from exc

    docx_path = Path(tmp_dir) / (doc_path.stem + ".docx")
    if not docx_path.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("LibreOffice produced no output file")
    return docx_path


def _extract_text_olefile(doc_path: Path) -> str:
    """Fallback: extract printable text from .doc using olefile (OLE2 stream)."""
    import olefile

    ole = olefile.OleFileIO(str(doc_path))
    try:
        if not ole.exists("WordDocument"):
            raise ValueError("No WordDocument stream found in OLE2 file")
        stream = ole.openstream("WordDocument").read()
    finally:
        ole.close()

    # The WordDocument stream contains binary data interleaved with text.
    # Extract runs of printable ASCII/Latin-1 characters.
    chars: list[str] = []
    for byte in stream:
        if 32 <= byte < 127 or byte in (9, 10, 13):
            chars.append(chr(byte))
        elif chars and chars[-1] != "\n":
            chars.append("\n")

    raw = "".join(chars)
    # Collapse multiple blank lines
    lines = raw.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped or (cleaned and cleaned[-1] != ""):
            cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def extract_text_from_doc(doc_path: Path) -> str:
    """Extract text from a .doc file.

    Primary: convert to .docx via LibreOffice, then use python-docx.
    Fallback: extract raw text via olefile if LibreOffice is unavailable.
    """
    # Try LibreOffice conversion first
    try:
        docx_path = convert_doc_to_docx(doc_path)
        try:
            from docx import Document

            document = Document(str(docx_path))
            return "\n".join(p.text for p in document.paragraphs)
        finally:
            shutil.rmtree(docx_path.parent, ignore_errors=True)
    except RuntimeError:
        logger.warning(
            "LibreOffice unavailable, falling back to olefile for %s",
            doc_path.name,
        )

    # Fallback to olefile
    return _extract_text_olefile(doc_path)
