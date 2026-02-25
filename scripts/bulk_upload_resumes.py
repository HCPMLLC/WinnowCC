#!/usr/bin/env python3
"""Bulk upload resumes to the Winnow recruiter pipeline.

Standalone script — no project dependencies required.
Install: pip install aiohttp

Usage:
    python scripts/bulk_upload_resumes.py \
        --api-url https://winnow-api-cdn2d6pc5q-uc.a.run.app \
        --email rlevi@hcpm.llc \
        --resume-dir "C:\\Users\\ronle\\OneDrive\\Documents\\HCPM Resumes" \
        --batch-size 5 \
        --concurrency 2

Modes:
    --verify    Check how many pipeline candidates exist (no upload)
    --retry     Retry previously failed files only
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
PROGRESS_FILENAME = "pipeline_upload_progress.json"
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


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"API error ({status}): {body[:200]}")


async def do_login(
    session: aiohttp.ClientSession, api_url: str, email: str, password: str
) -> str:
    """Login and return Bearer token."""
    url = f"{api_url}/api/auth/login"
    payload = {"email": email, "password": password}
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            sys.exit(f"Login failed ({resp.status}): {body}")
        data = await resp.json()
        if data.get("requires_mfa"):
            sys.exit("MFA is enabled. Disable MFA or use web UI first.")
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
        batch_size: int = 5,
        concurrency: int = 2,
        delay: float = 1.0,
        verify_only: bool = False,
        retry_failed: bool = False,
    ):
        self.api_url = api_url.rstrip("/")
        self.email = email
        self.password = password
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

        # Counters
        self.succeeded = 0
        self.matched = 0
        self.new_count = 0
        self.linked_platform = 0
        self.skipped_doc = 0
        self.failed = 0
        self.already_done = 0

    async def _save_progress(self) -> None:
        assert self._progress_lock is not None
        async with self._progress_lock:
            save_progress(self.progress_path, self.progress)

    async def _get_token(self) -> str:
        assert self.session is not None
        self.token = await do_login(
            self.session, self.api_url, self.email, self.password
        )
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
            names = [f.name for f in batch]
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

        # Collect files
        uploadable, doc_files, other_files = collect_files(self.resume_dir)

        print(f"Resume directory: {self.resume_dir}")
        print(f"  PDF/DOCX files: {len(uploadable)}")
        print(f"  DOC files (unsupported, skipping): {len(doc_files)}")
        print(f"  Other files (skipping): {len(other_files)}")
        print()

        # Load existing progress
        self.progress = load_progress(self.progress_path)
        already_done = sum(
            1
            for v in self.progress.values()
            if v.get("status") == "success"
        )
        if already_done:
            print(f"  Resuming — {already_done} files already completed")

        # Log skipped DOC files
        for doc in doc_files:
            if doc.name not in self.progress:
                self.progress[doc.name] = {
                    "status": "skipped",
                    "error": "Unsupported extension .doc",
                }
                self.skipped_doc += 1
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
                    for f in uploadable
                    if self.progress.get(f.name, {}).get("status")
                    in ("failed", "upload_failed", "parse_failed")
                ]
                print(f"  Retrying {len(pending)} failed files")
            else:
                pending = [
                    f
                    for f in uploadable
                    if self.progress.get(f.name, {}).get("status")
                    not in ("success",)
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
            completed_batches = 0

            for i, batch in enumerate(batches, 1):
                await self.process_batch(batch, sem, i, total_batches)
                completed_batches += 1

                # Progress update every 10 batches
                if completed_batches % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed_batches / elapsed if elapsed > 0 else 0
                    eta = (
                        (total_batches - completed_batches) / rate
                        if rate > 0
                        else 0
                    )
                    print(
                        f"\n  === Progress: {completed_batches}/{total_batches} batches, "
                        f"{self.succeeded} succeeded, {self.failed} failed, "
                        f"ETA: {eta / 60:.0f}m ===\n"
                    )

                    # Re-login periodically to prevent token expiry
                    if completed_batches % 50 == 0:
                        print("  Refreshing auth token...")
                        await self._get_token()

        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  Succeeded:         {self.succeeded}")
        print(f"    New candidates:  {self.new_count}")
        print(f"    Matched email:   {self.matched}")
        print(f"    Linked platform: {self.linked_platform}")
        print(f"  Already done:      {already_done}")
        print(f"  Skipped (DOC):     {self.skipped_doc}")
        print(f"  Failed:            {self.failed}")
        print(f"  Time elapsed:      {elapsed / 60:.1f} minutes")
        print(f"  Progress file:     {self.progress_path}")
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
        help="API base URL",
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
        default=5,
        help="Files per API request (default: 5, max: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max concurrent batch uploads (default: 2)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between batches (default: 1.0)",
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

    password = args.password or os.environ.get("WINNOW_PASSWORD") or ""
    if not password:
        password = getpass.getpass(f"Password for {args.email}: ")
    if not password:
        sys.exit("Password is required.")

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
    )

    asyncio.run(uploader.run())


if __name__ == "__main__":
    main()
