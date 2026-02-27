#!/usr/bin/env python3
"""Bulk upload resumes to the Winnow recruiter pipeline.

Standalone script — no project dependencies required.
Install: pip install aiohttp pywin32

Usage:
    python scripts/bulk_upload_resumes.py \
        --batch-size 10 \
        --concurrency 8

    # Retry any failures
    python scripts/bulk_upload_resumes.py --retry

    # Check pipeline count
    python scripts/bulk_upload_resumes.py --verify

Defaults: email=rlevi@hcpm.llc, api-url=Cloud Run, resume-dir=HCPM Resumes.
Password: prompted once at start (or set WINNOW_PASSWORD env var).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

try:
    import aiohttp
except ImportError:
    sys.exit("aiohttp is required. Install with: pip install aiohttp")

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
PROGRESS_FILENAME = "pipeline_upload_progress.json"
MAX_RETRIES = 5
BACKOFF_BASE = 3  # seconds


def sha256_file(filepath: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


def convert_doc_to_docx(doc_files: list[Path], temp_dir: Path) -> list[Path]:
    """Convert .doc files to .docx using Microsoft Word COM automation.

    Requires pywin32 and Microsoft Word installed on Windows.
    Returns list of converted .docx file paths in temp_dir.
    """
    if not doc_files:
        return []

    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        print("  [!] pywin32 not installed. Install with: pip install pywin32")
        print("  [!] Skipping .doc files.")
        return []

    converted = []
    word = None
    try:
        print(f"  Converting {len(doc_files)} .doc files to .docx...")
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone

        for i, doc_path in enumerate(doc_files, 1):
            out_path = temp_dir / (doc_path.stem + ".docx")
            try:
                doc = word.Documents.Open(str(doc_path), ReadOnly=True)
                # wdFormatXMLDocument = 12
                doc.SaveAs2(str(out_path), FileFormat=12)
                doc.Close(False)
                converted.append(out_path)
                if i % 20 == 0:
                    print(f"    Converted {i}/{len(doc_files)}...")
            except Exception as exc:
                print(f"    [!] Failed to convert {doc_path.name}: {exc}")

        print(f"  Converted {len(converted)}/{len(doc_files)} .doc files")
    except Exception as exc:
        print(f"  [!] Word COM error: {exc}")
        print("  [!] Make sure Microsoft Word is installed.")
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass

    return converted


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"API error ({status}): {body[:200]}")


async def do_login(
    session: aiohttp.ClientSession, api_url: str, email: str, password: str
) -> str:
    """Login and return Bearer token (handles MFA if enabled)."""
    url = f"{api_url}/api/auth/login"
    payload = {"email": email, "password": password}
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            sys.exit(f"Login failed ({resp.status}): {body}")
        data = await resp.json()

    if data.get("requires_mfa"):
        method = data.get("mfa_delivery_method", "email")
        print(f"  MFA required — a code was sent via {method}.")
        otp_code = os.environ.get("WINNOW_OTP") or ""
        if not otp_code:
            otp_code = input("  Enter the OTP code: ").strip()
        if not otp_code:
            sys.exit("OTP code is required.")

        verify_url = f"{api_url}/api/auth/verify-otp"
        verify_payload = {"email": email, "otp_code": otp_code}
        async with session.post(verify_url, json=verify_payload) as resp2:
            if resp2.status != 200:
                body = await resp2.text()
                sys.exit(f"OTP verification failed ({resp2.status}): {body}")
            data = await resp2.json()

    token = data.get("token")
    if not token:
        sys.exit(f"Login response missing token: {data}")
    return token


async def upload_batch(
    session: aiohttp.ClientSession,
    api_url: str,
    filepaths: list[Path],
    token: str,
) -> dict:
    """Upload a batch of resume files to the recruiter pipeline endpoint.

    POST /api/recruiter/pipeline/upload-resumes (multipart form).
    Returns the JSON response with per-file results.
    """
    url = f"{api_url}/api/recruiter/pipeline/upload-resumes"
    headers = {"Authorization": f"Bearer {token}"}

    data = aiohttp.FormData()
    file_handles = []
    for fp in filepaths:
        fh = open(fp, "rb")
        file_handles.append(fh)
        data.add_field(
            "files",
            fh,
            filename=fp.name,
            content_type="application/octet-stream",
        )

    try:
        async with session.post(url, data=data, headers=headers) as resp:
            body = await resp.text()
            if resp.status == 200:
                return json.loads(body)
            raise ApiError(resp.status, body)
    finally:
        for fh in file_handles:
            fh.close()


async def verify_pipeline(
    session: aiohttp.ClientSession,
    api_url: str,
    token: str,
) -> None:
    """Check current pipeline candidate count."""
    url = f"{api_url}/api/recruiter/pipeline?limit=1&offset=0"
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(url, headers=headers) as resp:
        body = await resp.text()
        if resp.status != 200:
            print(f"  Pipeline check failed ({resp.status}): {body[:200]}")
            return
        data = json.loads(body)
        if isinstance(data, dict) and "total" in data:
            print(f"  Pipeline candidates: {data['total']}")
        elif isinstance(data, list):
            print(f"  Pipeline candidates (from list): {len(data)}")
        else:
            print(f"  Pipeline response: {body[:300]}")


class BulkPipelineUploader:
    def __init__(
        self,
        api_url: str,
        email: str,
        password: str,
        resume_dir: Path,
        batch_size: int = 10,
        concurrency: int = 8,
        delay: float = 0.5,
        verify_only: bool = False,
        retry_failed: bool = False,
        prefetched_token: str = "",
    ):
        self.api_url = api_url.rstrip("/")
        self.email = email
        self.password = password
        self.prefetched_token = prefetched_token
        self.resume_dir = resume_dir
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.delay = delay
        self.verify_only = verify_only
        self.retry_failed = retry_failed
        self.progress_path = Path(__file__).parent / PROGRESS_FILENAME
        self.progress: dict = {}
        self.token: str = ""
        self.session: aiohttp.ClientSession | None = None
        self._progress_lock: asyncio.Lock | None = None
        self._token_lock: asyncio.Lock | None = None

        # Counters
        self.succeeded = 0
        self.matched = 0
        self.new_count = 0
        self.linked_platform = 0
        self.skipped_doc = 0
        self.skipped_dup = 0
        self.failed = 0
        self.already_done = 0

    async def _save_progress(self) -> None:
        assert self._progress_lock is not None
        async with self._progress_lock:
            save_progress(self.progress_path, self.progress)

    async def _get_token(self) -> str:
        assert self.session is not None
        assert self._token_lock is not None
        async with self._token_lock:
            if self.prefetched_token:
                self.token = self.prefetched_token
                self.prefetched_token = ""  # Only use once; refresh via login
            elif self.password:
                self.token = await do_login(
                    self.session, self.api_url, self.email, self.password
                )
            else:
                # No password (using prefetched token mode) — keep existing token
                print("  [!] Token refresh skipped (no password, using prefetched token)")
        return self.token

    async def _upload_batch_with_retry(
        self, filepaths: list[Path]
    ) -> dict | None:
        """Upload a batch with retries."""
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                return await upload_batch(
                    self.session, self.api_url, filepaths, self.token
                )
            except ApiError as exc:
                last_exc = exc
                if exc.status == 401:
                    print(f"  [!] 401, re-authenticating...")
                    await self._get_token()
                    continue
                if exc.status == 429:
                    wait = BACKOFF_BASE ** (attempt + 1) * 5
                    print(f"  [!] 429 rate limited, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                if exc.status >= 500:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    print(
                        f"  [!] {exc.status} server error, retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                    continue
                # 4xx other than 401/429 — don't retry
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                wait = BACKOFF_BASE ** (attempt + 1)
                print(f"  [!] Network error: {exc}, retrying in {wait}s...")
                await asyncio.sleep(wait)

        # All retries exhausted
        print(f"  [FAIL] Batch failed after {MAX_RETRIES} retries: {last_exc}")
        return None

    async def process_batch(
        self,
        batch: list[Path],
        sem: asyncio.Semaphore,
        batch_num: int,
        total_batches: int,
    ) -> None:
        """Process a single batch of files."""
        async with sem:
            result = await self._upload_batch_with_retry(batch)

            if result is None:
                # All retries failed — mark all files as failed
                for fp in batch:
                    self.progress[fp.name] = {
                        "status": "failed",
                        "error": "Batch upload failed after retries",
                    }
                    self.failed += 1
                await self._save_progress()
                return

            # Process per-file results
            file_results = result.get("results", [])
            for fr in file_results:
                fname = fr.get("filename", "")
                if fr.get("success"):
                    self.progress[fname] = {
                        "status": "success",
                        "pipeline_candidate_id": fr.get(
                            "pipeline_candidate_id"
                        ),
                        "candidate_profile_id": fr.get(
                            "candidate_profile_id"
                        ),
                        "matched_email": fr.get("matched_email"),
                        "parsed_name": fr.get("parsed_name"),
                        "result_status": fr.get("status"),
                    }
                    self.succeeded += 1
                    rs = fr.get("status", "")
                    if rs == "matched":
                        self.matched += 1
                    elif rs == "new":
                        self.new_count += 1
                    elif rs == "linked_platform":
                        self.linked_platform += 1
                else:
                    self.progress[fname] = {
                        "status": "failed",
                        "error": fr.get("error", "Unknown error")[:200],
                    }
                    self.failed += 1

            await self._save_progress()

            total_in_batch = result.get("total_succeeded", 0)
            remaining = result.get("remaining_monthly_quota", "?")
            print(
                f"  Batch {batch_num}/{total_batches}: "
                f"{total_in_batch}/{len(batch)} succeeded, "
                f"quota remaining: {remaining}"
            )

            if self.delay > 0:
                await asyncio.sleep(self.delay)

    async def run(self) -> None:
        self._progress_lock = asyncio.Lock()
        self._token_lock = asyncio.Lock()

        # Collect files
        uploadable, doc_files, other_files = collect_files(self.resume_dir)

        print(f"Resume directory: {self.resume_dir}")
        print(f"  PDF/DOCX files: {len(uploadable)}")
        print(f"  DOC files:      {len(doc_files)}")
        print(f"  Other files (skipping): {len(other_files)}")
        print()

        # Convert .doc files to .docx
        temp_dir = None
        converted_files: list[Path] = []
        if doc_files:
            temp_dir = Path(tempfile.mkdtemp(prefix="winnow_doc_convert_"))
            converted_files = convert_doc_to_docx(doc_files, temp_dir)
            if converted_files:
                uploadable.extend(converted_files)
                print(f"  Added {len(converted_files)} converted .docx files")
            unconverted = len(doc_files) - len(converted_files)
            if unconverted > 0:
                print(f"  {unconverted} .doc files could not be converted")
            print()

        try:
            await self._run_upload(uploadable, doc_files)
        finally:
            # Clean up temp directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def _run_upload(
        self, uploadable: list[Path], doc_files: list[Path]
    ) -> None:
        # Load existing progress
        self.progress = load_progress(self.progress_path)
        already_done = sum(
            1
            for v in self.progress.values()
            if v.get("status") == "success"
        )
        if already_done:
            print(f"  Resuming — {already_done} files already completed")
            self.already_done = already_done

        # Build set of already-seen SHA256 hashes from progress
        seen_hashes: set[str] = set()
        for v in self.progress.values():
            h = v.get("sha256")
            if h:
                seen_hashes.add(h)

        # Log unconverted .doc files that weren't converted
        for doc in doc_files:
            # Check if this doc was converted (its .docx would be in uploadable)
            docx_name = doc.stem + ".docx"
            was_converted = any(f.name == docx_name for f in uploadable)
            if not was_converted and doc.name not in self.progress:
                self.progress[doc.name] = {
                    "status": "skipped",
                    "error": "Failed to convert .doc to .docx",
                }
                self.skipped_doc += 1
        save_progress(self.progress_path, self.progress)

        # SHA256 dedup pass — hash all files, skip duplicates
        print("  Computing file hashes for duplicate detection...")
        deduped: list[Path] = []
        dup_count = 0
        for fp in uploadable:
            file_hash = sha256_file(fp)
            if file_hash in seen_hashes:
                if fp.name not in self.progress:
                    self.progress[fp.name] = {
                        "status": "skipped",
                        "error": "Duplicate content (SHA256 match)",
                        "sha256": file_hash,
                    }
                dup_count += 1
                continue
            seen_hashes.add(file_hash)
            # Store hash in progress for future dedup even before upload
            if fp.name in self.progress and self.progress[fp.name].get("status") == "success":
                # Already succeeded, just ensure hash is stored
                self.progress[fp.name]["sha256"] = file_hash
            else:
                # Store hash for tracking; will be updated on upload result
                if fp.name not in self.progress:
                    self.progress[fp.name] = {"sha256": file_hash}
                else:
                    self.progress[fp.name]["sha256"] = file_hash
            deduped.append(fp)

        if dup_count > 0:
            self.skipped_dup = dup_count
            print(f"  Skipped {dup_count} duplicate files (same content)")
        save_progress(self.progress_path, self.progress)

        # Connect and login
        timeout = aiohttp.ClientTimeout(total=600, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session

            print(f"Logging in as {self.email}...")
            await self._get_token()
            print("  Login successful")
            print()

            # Verify current pipeline state
            print("Current pipeline state:")
            await verify_pipeline(session, self.api_url, self.token)
            print()

            if self.verify_only:
                return

            # Determine which files to process
            if self.retry_failed:
                pending = [
                    f
                    for f in deduped
                    if self.progress.get(f.name, {}).get("status")
                    in ("failed", "upload_failed", "parse_failed")
                ]
                print(f"  Retrying {len(pending)} failed files")
            else:
                pending = [
                    f
                    for f in deduped
                    if self.progress.get(f.name, {}).get("status")
                    not in ("success", "skipped")
                ]

            print(f"  Files to process: {len(pending)}")
            print(
                f"  Batch size: {self.batch_size}, "
                f"Concurrency: {self.concurrency}, "
                f"Delay: {self.delay}s"
            )
            print()

            if not pending:
                print("All files already processed!")
                return

            # Split into batches
            batches = [
                pending[i : i + self.batch_size]
                for i in range(0, len(pending), self.batch_size)
            ]
            total_batches = len(batches)
            print(f"  Total batches: {total_batches}")
            print()

            sem = asyncio.Semaphore(self.concurrency)
            start_time = time.time()

            # Launch all batches concurrently (semaphore limits parallelism)
            tasks = [
                asyncio.create_task(
                    self.process_batch(batch, sem, i, total_batches)
                )
                for i, batch in enumerate(batches, 1)
            ]

            # Monitor progress while tasks run
            done_count = 0
            last_report = 0
            last_token_refresh = time.time()
            for coro in asyncio.as_completed(tasks):
                await coro
                done_count += 1

                # Progress update every 50 files worth of batches
                files_done = done_count * self.batch_size
                if files_done - last_report >= 50:
                    last_report = files_done
                    elapsed = time.time() - start_time
                    rate = done_count / elapsed if elapsed > 0 else 0
                    eta = (
                        (total_batches - done_count) / rate
                        if rate > 0
                        else 0
                    )
                    print(
                        f"\n  === Progress: {done_count}/{total_batches} batches, "
                        f"{self.succeeded} succeeded, {self.failed} failed, "
                        f"ETA: {eta / 60:.0f}m ===\n"
                    )

                # Re-login periodically to prevent token expiry (every 10 min)
                if time.time() - last_token_refresh > 600:
                    print("  Refreshing auth token...")
                    await self._get_token()
                    last_token_refresh = time.time()

        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Succeeded:          {self.succeeded}")
        print(f"    New candidates:   {self.new_count}")
        print(f"    Matched email:    {self.matched}")
        print(f"    Linked platform:  {self.linked_platform}")
        print(f"  Already done:       {self.already_done}")
        print(f"  Skipped (dup):      {self.skipped_dup}")
        print(f"  Skipped (DOC fail): {self.skipped_doc}")
        print(f"  Failed:             {self.failed}")
        print(f"  Time elapsed:       {elapsed / 60:.1f} minutes")
        print(f"  Progress file:      {self.progress_path}")
        print()

        if self.failed > 0:
            failed_files = [
                k
                for k, v in self.progress.items()
                if v.get("status") == "failed"
            ]
            print(f"Failed files ({len(failed_files)}):")
            for f in failed_files[:20]:
                print(
                    f"  - {f}: {self.progress[f].get('error', 'unknown')}"
                )
            if len(failed_files) > 20:
                print(
                    f"  ... and {len(failed_files) - 20} more "
                    f"(see {self.progress_path})"
                )
            print()
            print("Run with --retry to retry failed files.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk upload resumes to Winnow recruiter pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-url",
        default="https://winnow-api-cdn2d6pc5q-uc.a.run.app",
        help="API base URL (default: Cloud Run production)",
    )
    parser.add_argument(
        "--email",
        default="rlevi@hcpm.llc",
        help="Login email (default: rlevi@hcpm.llc)",
    )
    parser.add_argument(
        "--resume-dir",
        default=r"C:\Users\ronle\OneDrive\Documents\HCPM Resumes",
        help="Directory containing resume files",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Files per API request (default: 10, max: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Max concurrent batch uploads (default: 8)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay in seconds between batches (default: 0.5)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password (prompts if not provided). Also reads WINNOW_PASSWORD env var.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only check pipeline state, don't upload",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Retry previously failed files only",
    )
    args = parser.parse_args()

    resume_dir = Path(args.resume_dir)
    if not resume_dir.is_dir():
        sys.exit(f"Resume directory not found: {resume_dir}")

    if args.batch_size > 50:
        sys.exit("Batch size cannot exceed 50 (API limit).")

    # Accept pre-fetched token to skip login (useful when MFA is enabled)
    prefetched_token = os.environ.get("WINNOW_TOKEN") or ""

    password = args.password or os.environ.get("WINNOW_PASSWORD") or ""
    if not password and not prefetched_token:
        password = getpass.getpass(f"Password for {args.email}: ")
    if not password and not prefetched_token:
        sys.exit("Password is required (or set WINNOW_TOKEN to skip login).")

    uploader = BulkPipelineUploader(
        api_url=args.api_url,
        email=args.email,
        password=password,
        resume_dir=resume_dir,
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        delay=args.delay,
        verify_only=args.verify,
        retry_failed=args.retry,
        prefetched_token=prefetched_token,
    )

    asyncio.run(uploader.run())


if __name__ == "__main__":
    main()
