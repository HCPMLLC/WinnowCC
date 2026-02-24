#!/usr/bin/env python3
"""Bulk upload resumes to the Winnow API.

Standalone script — no project dependencies required.
Install: pip install aiohttp

Usage:
    python scripts/bulk_upload_resumes.py \
        --api-url https://api.winnowcc.ai \
        --email rlevi@hcpm.llc \
        --resume-dir "C:\\Users\\ronle\\OneDrive\\Documents\\HCPM Resumes" \
        --concurrency 5 \
        --delay 0.2
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
import time
from pathlib import Path

try:
    import aiohttp
except ImportError:
    sys.exit("aiohttp is required. Install with: pip install aiohttp")

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
PROGRESS_FILENAME = "upload_progress.json"
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


def load_progress(progress_path: Path) -> dict:
    if progress_path.exists():
        with open(progress_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress_path: Path, progress: dict) -> None:
    tmp = progress_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
    tmp.replace(progress_path)


def collect_files(resume_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (uploadable, doc_files, other_files)."""
    uploadable = []
    doc_files = []
    other_files = []
    for entry in sorted(resume_dir.iterdir()):
        if not entry.is_file():
            continue
        ext = entry.suffix.lower()
        if ext in ALLOWED_EXTENSIONS:
            uploadable.append(entry)
        elif ext == ".doc":
            doc_files.append(entry)
        else:
            other_files.append(entry)
    return uploadable, doc_files, other_files


async def login(session: aiohttp.ClientSession, api_url: str, email: str, password: str) -> str:
    """Login and return Bearer token."""
    url = f"{api_url}/api/auth/login"
    payload = {"email": email, "password": password}
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            sys.exit(f"Login failed ({resp.status}): {body}")
        data = await resp.json()
        if data.get("requires_mfa"):
            sys.exit(
                "MFA is enabled for this account. Disable MFA or use the web UI to login first.\n"
                "Script does not support MFA flow."
            )
        token = data.get("token")
        if not token:
            sys.exit(f"Login response missing token: {data}")
        return token


async def upload_file(
    session: aiohttp.ClientSession,
    api_url: str,
    filepath: Path,
    token: str,
) -> dict:
    """Upload a single resume file. Returns {"resume_document_id": int, "filename": str}."""
    url = f"{api_url}/api/resume/upload"
    headers = {"Authorization": f"Bearer {token}"}

    data = aiohttp.FormData()
    data.add_field(
        "file",
        open(filepath, "rb"),
        filename=filepath.name,
        content_type="application/octet-stream",
    )
    async with session.post(url, data=data, headers=headers) as resp:
        body = await resp.text()
        if resp.status == 200:
            return json.loads(body)
        raise UploadError(resp.status, body)


async def parse_resume(
    session: aiohttp.ClientSession,
    api_url: str,
    resume_id: int,
    token: str,
) -> dict:
    """Trigger parse for a resume. Returns {"job_id": str, "job_run_id": int, "status": str}."""
    url = f"{api_url}/api/resume/{resume_id}/parse"
    headers = {"Authorization": f"Bearer {token}"}
    async with session.post(url, headers=headers) as resp:
        body = await resp.text()
        if resp.status == 200:
            return json.loads(body)
        raise ParseError(resp.status, body)


class UploadError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Upload failed ({status}): {body}")


class ParseError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Parse failed ({status}): {body}")


class BulkUploader:
    def __init__(
        self,
        api_url: str,
        email: str,
        password: str,
        resume_dir: Path,
        concurrency: int = 5,
        delay: float = 0.2,
    ):
        self.api_url = api_url.rstrip("/")
        self.email = email
        self.password = password
        self.resume_dir = resume_dir
        self.concurrency = concurrency
        self.delay = delay
        self.progress_path = Path(__file__).parent / PROGRESS_FILENAME
        self.progress: dict = {}
        self.token: str = ""
        self.session: aiohttp.ClientSession | None = None
        self._progress_lock: asyncio.Lock | None = None  # initialized in run()

        # Counters
        self.uploaded = 0
        self.parsed = 0
        self.skipped = 0
        self.failed = 0
        self.already_done = 0

    async def _save_progress(self) -> None:
        """Thread-safe progress save using async lock."""
        assert self._progress_lock is not None
        async with self._progress_lock:
            save_progress(self.progress_path, self.progress)

    async def _get_token(self) -> str:
        assert self.session is not None
        self.token = await login(self.session, self.api_url, self.email, self.password)
        return self.token

    async def _retry(self, coro_factory, filepath: Path):
        """Execute a coroutine with retries and exponential backoff."""
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                return await coro_factory()
            except (UploadError, ParseError) as exc:
                last_exc = exc
                status = exc.status
                if status == 401:
                    print(f"  [!] 401 on {filepath.name}, re-authenticating...")
                    await self._get_token()
                    continue
                if status == 429 or status >= 500:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    print(f"  [!] {status} on {filepath.name}, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"  [!] Network error on {filepath.name}: {exc}, retrying in {wait}s...")
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    async def process_file(self, filepath: Path, sem: asyncio.Semaphore) -> None:
        """Upload + parse a single file with concurrency limiting."""
        filename = filepath.name
        entry = self.progress.get(filename, {})

        # Skip already fully processed
        if entry.get("status") == "parsed":
            self.already_done += 1
            return

        async with sem:
            # Step 1: Upload (skip if already uploaded)
            resume_id = entry.get("resume_id")
            if resume_id is None:
                try:
                    result = await self._retry(
                        lambda fp=filepath: upload_file(self.session, self.api_url, fp, self.token),
                        filepath,
                    )
                    resume_id = result["resume_document_id"]
                    self.progress[filename] = {"status": "uploaded", "resume_id": resume_id}
                    await self._save_progress()
                    self.uploaded += 1
                except (UploadError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    err_msg = str(exc)[:200]
                    self.progress[filename] = {"status": "upload_failed", "error": err_msg}
                    await self._save_progress()
                    self.failed += 1
                    print(f"  [FAIL] Upload {filename}: {err_msg}")
                    return

            # Small delay between upload and parse
            if self.delay > 0:
                await asyncio.sleep(self.delay)

            # Step 2: Parse
            try:
                result = await self._retry(
                    lambda rid=resume_id: parse_resume(self.session, self.api_url, rid, self.token),
                    filepath,
                )
                self.progress[filename] = {
                    "status": "parsed",
                    "resume_id": resume_id,
                    "job_run_id": result.get("job_run_id"),
                }
                await self._save_progress()
                self.parsed += 1
            except (ParseError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
                err_msg = str(exc)[:200]
                self.progress[filename] = {
                    "status": "parse_failed",
                    "resume_id": resume_id,
                    "error": err_msg,
                }
                await self._save_progress()
                self.failed += 1
                print(f"  [FAIL] Parse {filename}: {err_msg}")
                return

            if self.delay > 0:
                await asyncio.sleep(self.delay)

    async def run(self) -> None:
        self._progress_lock = asyncio.Lock()
        # Collect files
        uploadable, doc_files, other_files = collect_files(self.resume_dir)

        print(f"Resume directory: {self.resume_dir}")
        print(f"  PDF/DOCX files: {len(uploadable)}")
        print(f"  DOC files (unsupported, skipping): {len(doc_files)}")
        print(f"  Other files (skipping): {len(other_files)}")
        print()

        # Load existing progress
        self.progress = load_progress(self.progress_path)
        already_parsed = sum(1 for v in self.progress.values() if v.get("status") == "parsed")
        if already_parsed:
            print(f"  Resuming — {already_parsed} files already completed")

        # Log skipped DOC files
        for doc in doc_files:
            if doc.name not in self.progress:
                self.progress[doc.name] = {
                    "status": "skipped",
                    "error": f"Unsupported extension .doc",
                }
                self.skipped += 1
        save_progress(self.progress_path, self.progress)

        if not uploadable:
            print("No uploadable files found.")
            return

        # Filter to only files that still need processing
        pending = [
            f for f in uploadable
            if self.progress.get(f.name, {}).get("status") not in ("parsed",)
        ]
        print(f"  Files to process: {len(pending)}")
        print(f"  Concurrency: {self.concurrency}, Delay: {self.delay}s")
        print()

        if not pending:
            print("All files already processed!")
            return

        timeout = aiohttp.ClientTimeout(total=300, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session

            # Login
            print(f"Logging in as {self.email}...")
            await self._get_token()
            print("  Login successful")
            print()

            # Process files with concurrency limit
            sem = asyncio.Semaphore(self.concurrency)
            total = len(pending)
            start_time = time.time()

            # Track progress with a simple counter
            completed = 0

            async def tracked_process(filepath: Path) -> None:
                nonlocal completed
                await self.process_file(filepath, sem)
                completed += 1
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(
                    f"  [{completed}/{total}] {filepath.name} "
                    f"({rate:.1f} files/s, ETA: {eta / 60:.0f}m)"
                )

            tasks = [tracked_process(f) for f in pending]
            await asyncio.gather(*tasks)

        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Uploaded:       {self.uploaded}")
        print(f"  Parsed:         {self.parsed}")
        print(f"  Already done:   {self.already_done}")
        print(f"  Skipped (DOC):  {self.skipped}")
        print(f"  Failed:         {self.failed}")
        print(f"  Time elapsed:   {elapsed / 60:.1f} minutes")
        print(f"  Progress file:  {self.progress_path}")
        print()

        if self.failed > 0:
            failed_files = [
                k for k, v in self.progress.items()
                if v.get("status") in ("upload_failed", "parse_failed")
            ]
            print(f"Failed files ({len(failed_files)}):")
            for f in failed_files[:20]:
                print(f"  - {f}: {self.progress[f].get('error', 'unknown')}")
            if len(failed_files) > 20:
                print(f"  ... and {len(failed_files) - 20} more (see {self.progress_path})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk upload resumes to the Winnow API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-url",
        default="https://api.winnowcc.ai",
        help="API base URL (default: https://api.winnowcc.ai)",
    )
    parser.add_argument(
        "--email",
        default="rlevi@hcpm.llc",
        help="Login email (default: rlevi@hcpm.llc)",
    )
    parser.add_argument(
        "--resume-dir",
        required=True,
        help="Directory containing resume files (PDF/DOCX)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent uploads (default: 5)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay in seconds between requests (default: 0.2)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password (optional — prompts if not provided). Can also set WINNOW_PASSWORD env var.",
    )
    args = parser.parse_args()

    resume_dir = Path(args.resume_dir)
    if not resume_dir.is_dir():
        sys.exit(f"Resume directory not found: {resume_dir}")

    password = args.password or os.environ.get("WINNOW_PASSWORD") or ""
    if not password:
        password = getpass.getpass(f"Password for {args.email}: ")
    if not password:
        sys.exit("Password is required.")

    uploader = BulkUploader(
        api_url=args.api_url,
        email=args.email,
        password=password,
        resume_dir=resume_dir,
        concurrency=args.concurrency,
        delay=args.delay,
    )

    asyncio.run(uploader.run())


if __name__ == "__main__":
    main()
