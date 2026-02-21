"""
Input sanitization utilities.
Strip dangerous characters, enforce length limits, and prevent injection.
"""

import html
import re


def sanitize_text(value: str, max_length: int = 10000) -> str:
    """
    Sanitize a text input:
    - Strip leading/trailing whitespace
    - HTML-encode special characters
    - Enforce max length
    - Remove null bytes
    """
    if not isinstance(value, str):
        return value

    value = value.strip()
    value = value.replace("\x00", "")  # Remove null bytes
    value = html.escape(value)

    if len(value) > max_length:
        value = value[:max_length]

    return value


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename:
    - Remove path separators
    - Remove special characters except dots, hyphens, underscores
    - Enforce max length
    """
    if not filename:
        return "unnamed"

    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Keep only safe characters
    filename = re.sub(r"[^\w.\-]", "_", filename)

    # Prevent directory traversal
    filename = filename.lstrip(".")

    if len(filename) > 255:
        filename = filename[:255]

    return filename or "unnamed"
