"""
File upload validation.
Validates file size, extension, MIME type, and magic bytes.
"""

import logging

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)

# Maximum file size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed file types with their MIME types and magic bytes
ALLOWED_TYPES = {
    ".pdf": {
        "mime_types": ["application/pdf"],
        "magic_bytes": [b"%PDF"],
    },
    ".docx": {
        "mime_types": [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",  # Some clients send this
        ],
        "magic_bytes": [b"PK\x03\x04"],  # DOCX is a ZIP file
    },
    ".doc": {
        "mime_types": [
            "application/msword",
            "application/octet-stream",
        ],
        "magic_bytes": [b"\xd0\xcf\x11\xe0"],  # OLE2 Compound Document
    },
}


async def validate_upload(file: UploadFile) -> bytes:
    """
    Validate an uploaded file and return its contents.

    Checks:
    1. File extension is allowed (.pdf or .docx)
    2. MIME type matches expected type for the extension
    3. File size is under the limit
    4. Magic bytes match expected file format

    Returns: The file contents as bytes.
    Raises: HTTPException if validation fails.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # 1. Check extension
    filename_lower = file.filename.lower()
    ext = None
    for allowed_ext in ALLOWED_TYPES:
        if filename_lower.endswith(allowed_ext):
            ext = allowed_ext
            break

    if not ext:
        allowed = ", ".join(ALLOWED_TYPES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {allowed}",
        )

    # 2. Check MIME type
    allowed_info = ALLOWED_TYPES[ext]
    if file.content_type and file.content_type not in allowed_info["mime_types"]:
        logger.warning(
            "MIME type mismatch for extension %s: got %s",
            ext,
            file.content_type,
        )
        # Log but don't block — some browsers send incorrect MIME types

    # 3. Read file and check size
    contents = await file.read()
    await file.seek(0)  # Reset for downstream consumers

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(contents) > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_mb} MB",
        )

    # 4. Check magic bytes
    magic_match = any(
        contents[: len(magic)] == magic for magic in allowed_info["magic_bytes"]
    )

    if not magic_match:
        raise HTTPException(
            status_code=400,
            detail=(
                "File content does not match its extension. The file may be corrupted."
            ),
        )

    return contents
