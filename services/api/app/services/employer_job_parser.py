"""Backward-compatibility shim — delegates to unified job_parser.py.

All job parsing logic now lives in app.services.job_parser (PROMPT77).
This file preserves the old import path so existing callers don't break.
"""

from app.services.job_parser import parse_job_from_file


def parse_job_document(file_path: str) -> dict:
    """Legacy alias. See job_parser.parse_job_from_file()."""
    return parse_job_from_file(file_path, source="web_upload")
