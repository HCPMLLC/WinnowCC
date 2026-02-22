"""Unified file storage — local disk or Google Cloud Storage.

Toggle: set the ``GCS_BUCKET`` env var (e.g. ``winnow-resumes``) to use GCS.
When unset/empty, all operations fall back to local disk so development works
without any cloud credentials.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Local base directory (used when GCS is disabled)
_LOCAL_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Lazy-loaded GCS client — never imported on local dev if GCS is off.
_gcs_client = None


def _get_gcs_client():
    global _gcs_client
    if _gcs_client is None:
        from google.cloud import storage as gcs  # type: ignore[import-untyped]

        _gcs_client = gcs.Client()
    return _gcs_client


def _get_bucket():
    return _get_gcs_client().bucket(os.environ["GCS_BUCKET"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_gcs_enabled() -> bool:
    return bool(os.environ.get("GCS_BUCKET"))


def is_gcs_path(path: str) -> bool:
    return path.startswith("gs://")


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def upload_file(local_path: Path | str, prefix: str, filename: str) -> str:
    """Upload *local_path* to storage and return the stored path/URI.

    For GCS: uploads to ``gs://<bucket>/<prefix>/<filename>``.
    For local: copies into ``data/<prefix>/<filename>``.
    """
    local_path = Path(local_path)
    if is_gcs_enabled():
        blob_name = f"{prefix}{filename}"
        blob = _get_bucket().blob(blob_name)
        blob.upload_from_filename(str(local_path))
        uri = f"gs://{os.environ['GCS_BUCKET']}/{blob_name}"
        logger.info("Uploaded %s -> %s", local_path.name, uri)
        return uri

    dest_dir = _LOCAL_DATA_DIR / prefix.rstrip("/")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    shutil.copy2(str(local_path), str(dest))
    return str(dest)


def upload_bytes(data: bytes, prefix: str, filename: str) -> str:
    """Upload raw *data* bytes and return the stored path/URI."""
    if is_gcs_enabled():
        blob_name = f"{prefix}{filename}"
        blob = _get_bucket().blob(blob_name)
        blob.upload_from_string(data)
        uri = f"gs://{os.environ['GCS_BUCKET']}/{blob_name}"
        logger.info("Uploaded bytes -> %s", uri)
        return uri

    dest_dir = _LOCAL_DATA_DIR / prefix.rstrip("/")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    return str(dest)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_to_tempfile(stored_path: str, suffix: str = "") -> Path:
    """Return a local ``Path`` for *stored_path*.

    * GCS paths are downloaded to a temporary file (caller should clean up).
    * Local paths are returned as-is (no copy).
    """
    if is_gcs_path(stored_path):
        bucket_name = os.environ["GCS_BUCKET"]
        blob_name = stored_path.split(f"gs://{bucket_name}/", 1)[-1]
        blob = _get_bucket().blob(blob_name)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        blob.download_to_filename(tmp.name)
        tmp.close()
        logger.info("Downloaded %s -> %s", stored_path, tmp.name)
        return Path(tmp.name)

    return Path(stored_path)


def download_as_bytes(stored_path: str) -> bytes | None:
    """Read file contents as bytes. Returns ``None`` on any failure."""
    if not stored_path:
        return None
    try:
        if is_gcs_path(stored_path):
            bucket_name = os.environ["GCS_BUCKET"]
            blob_name = stored_path.split(f"gs://{bucket_name}/", 1)[-1]
            blob = _get_bucket().blob(blob_name)
            return blob.download_as_bytes()

        p = Path(stored_path)
        if p.is_file():
            return p.read_bytes()
    except Exception:
        logger.warning("Failed to read file %s", stored_path, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# FileResponse helper
# ---------------------------------------------------------------------------

def file_response_path(stored_path: str, suffix: str = "") -> Path:
    """Convenience wrapper for endpoints that return ``FileResponse``.

    Same as ``download_to_tempfile`` — the caller is responsible for cleaning
    up the temp file (use ``BackgroundTask``).
    """
    return download_to_tempfile(stored_path, suffix=suffix)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_file(stored_path: str) -> None:
    """Delete the file at *stored_path* (GCS or local). Best-effort."""
    if not stored_path:
        return
    try:
        if is_gcs_path(stored_path):
            bucket_name = os.environ["GCS_BUCKET"]
            blob_name = stored_path.split(f"gs://{bucket_name}/", 1)[-1]
            _get_bucket().blob(blob_name).delete()
            logger.info("Deleted GCS blob %s", stored_path)
        else:
            Path(stored_path).unlink(missing_ok=True)
    except Exception:
        logger.warning("Failed to delete %s", stored_path, exc_info=True)
