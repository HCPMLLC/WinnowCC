"""Convert legacy .doc (Word 97-2003) files to .docx or extract raw text."""

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Word binary format field codes and formatting tokens to strip
_WORD_NOISE_RE = re.compile(
    r"\b("
    r"bjbj|CJ|PJ|KH|aJ|mH|nH|sH|tH|hfS|gd|"
    r"[Uu]nknown|\\[a-z]+|OJQJo|OJQJ|"
    r"h\s*:p|h\s*:O|"  # formatting references
    r"\^J|\\n"
    r")\b",
)
_SHORT_GARBAGE_LINE_RE = re.compile(r"^[\s\W\d]{0,3}$")


def convert_doc_to_docx(doc_path: Path) -> Path:
    """Convert a .doc file to .docx using LibreOffice headless.

    Returns the path to the converted .docx in a temporary directory.
    Caller is responsible for cleaning up the temp directory.
    Raises RuntimeError if conversion fails.
    """
    tmp_dir = tempfile.mkdtemp(prefix="doc2docx_")
    # LibreOffice needs a writable user profile; in containers the default
    # $HOME/.config/libreoffice may not be writable or may lock up with
    # concurrent conversions. Use a per-call temp profile.
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
    try:
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                "--nolockcheck",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to",
                "docx",
                "--outdir",
                tmp_dir,
                str(doc_path),
            ],
            timeout=60,
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(
                "LibreOffice returned %d: stdout=%s stderr=%s",
                result.returncode,
                result.stdout[:500] if result.stdout else b"",
                result.stderr[:500] if result.stderr else b"",
            )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ) as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise RuntimeError(f"LibreOffice conversion failed: {exc}") from exc
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    docx_path = Path(tmp_dir) / (doc_path.stem + ".docx")
    if not docx_path.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("LibreOffice produced no output file")
    return docx_path


def _extract_text_olefile(doc_path: Path) -> str:
    """Fallback: extract text from .doc using olefile (OLE2 stream).

    Handles both 8-bit and UTF-16LE encoded text common in Word 97-2003 files.
    Filters out Word binary formatting noise to return clean document text.
    """
    import olefile

    ole = olefile.OleFileIO(str(doc_path))
    try:
        if not ole.exists("WordDocument"):
            raise ValueError("No WordDocument stream found in OLE2 file")
        stream = ole.openstream("WordDocument").read()
    finally:
        ole.close()

    # Word binary format stores text as either 8-bit or 16-bit (UTF-16LE)
    # runs. Try both and pick the best.
    candidates: list[str] = []

    # Approach 1: Decode as UTF-16LE (most common encoding in .doc files).
    utf16_chars: list[str] = []
    i = 0
    while i + 1 < len(stream):
        low, high = stream[i], stream[i + 1]
        if high == 0 and (32 <= low < 127 or low in (9, 10, 13)):
            utf16_chars.append(chr(low))
        elif utf16_chars and utf16_chars[-1] != "\n":
            utf16_chars.append("\n")
        i += 2
    utf16_text = _filter_word_noise("".join(utf16_chars))
    if utf16_text:
        candidates.append(utf16_text)

    # Approach 2: Single-byte ASCII extraction (fallback for older files).
    ascii_chars: list[str] = []
    for byte in stream:
        if 32 <= byte < 127 or byte in (9, 10, 13):
            ascii_chars.append(chr(byte))
        elif ascii_chars and ascii_chars[-1] != "\n":
            ascii_chars.append("\n")
    ascii_text = _filter_word_noise("".join(ascii_chars))
    if ascii_text:
        candidates.append(ascii_text)

    if not candidates:
        return ""

    return max(candidates, key=_text_quality_score)


def _filter_word_noise(raw: str) -> str:
    """Remove Word binary formatting codes and keep real document text.

    Word .doc binary streams mix actual document text with formatting metadata
    (field codes, style refs, control words). This filter keeps lines that
    look like real human-written text and discards formatting residue.
    """
    lines = raw.splitlines()
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        # Remove known Word formatting tokens
        stripped = _WORD_NOISE_RE.sub("", stripped).strip()
        if not stripped:
            continue

        # Split into words and assess quality
        words = stripped.split()

        # Skip lines with no real words (3+ chars)
        real_words = [w for w in words if len(w) >= 3]
        if not real_words:
            continue

        # Skip lines where most words are very short (formatting residue)
        if len(real_words) < len(words) * 0.3 and len(words) > 2:
            continue

        # Skip lines that are mostly non-alphanumeric
        alpha_count = sum(1 for c in stripped if c.isalpha())
        if len(stripped) > 2 and alpha_count / len(stripped) < 0.4:
            continue

        cleaned.append(stripped)

    # Collapse consecutive blank lines
    result: list[str] = []
    for line in cleaned:
        if line == "" and result and result[-1] == "":
            continue
        result.append(line)

    return "\n".join(result).strip()


def _text_quality_score(text: str) -> float:
    """Score text quality: longer text with real words scores higher."""
    if not text:
        return 0.0
    words = text.split()
    if not words:
        return 0.0
    # Favor text with longer average word length (real words vs garbled bytes)
    avg_word_len = sum(len(w) for w in words) / len(words)
    # Penalize very short average words (likely garbled)
    word_quality = min(avg_word_len / 4.0, 1.0)
    return len(words) * word_quality


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
