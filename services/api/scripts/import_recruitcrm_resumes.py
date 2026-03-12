"""Import resumes from RecruitCRM attachment export ZIP into Winnow.

Maps RecruitCRM candidate slugs → emails → pipeline candidates,
extracts resume files, parses them, and links to CandidateProfiles.

Usage:
    cd services/api
    python scripts/import_recruitcrm_resumes.py                    # full run
    python scripts/import_recruitcrm_resumes.py --limit 10         # test with 10
    python scripts/import_recruitcrm_resumes.py --skip-existing    # skip already-linked
    python scripts/import_recruitcrm_resumes.py --dry-run          # preview only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dotenv
dotenv.load_dotenv()

from sqlalchemy import text

from app.db.session import get_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths (Windows)
CSV_ZIP = Path(r"C:\Users\ronle\Downloads\csv-data-export-2026-02-19-13-42-57-105.zip")
ATTACH_ZIP = Path(r"c:\tmp\recruitcrm_inner.zip")
RESUME_EXTENSIONS = {".pdf", ".docx", ".doc"}


def build_slug_to_email(csv_zip: Path) -> dict[str, str]:
    """Build slug → email mapping from candidate_data.csv."""
    zf = zipfile.ZipFile(csv_zip)
    data = zf.read("candidate_data.csv").decode("utf-8", errors="replace")
    zf.close()

    mapping = {}
    for row in csv.DictReader(io.StringIO(data)):
        slug = (row.get("Slug") or "").strip()
        email = (row.get("Email") or "").strip().lower()
        if slug and email:
            mapping[slug] = email
    return mapping


def build_slug_to_resume_path(csv_zip: Path, attach_zip: zipfile.ZipFile) -> dict[str, str]:
    """Build slug → actual resume file path in the attachment ZIP.

    Uses the resumefilename/ subfolder for each candidate slug.
    Falls back to fuzzy match when filenames are truncated.
    """
    # Get all files in the ZIP
    zip_files = {}
    for info in attach_zip.infolist():
        if info.is_dir():
            continue
        parts = info.filename.split("/")
        if (
            len(parts) >= 3
            and parts[0] == "Candidates"
            and "resumefilename" in info.filename
        ):
            ext = os.path.splitext(info.filename)[1].lower().split("?")[0]
            if ext in RESUME_EXTENSIONS:
                slug = parts[1]
                # Prefer larger files (more likely to be the actual resume)
                if slug not in zip_files or info.file_size > zip_files[slug][1]:
                    zip_files[slug] = (info.filename, info.file_size)

    return {slug: path for slug, (path, _) in zip_files.items()}


def build_email_to_pipeline(session) -> dict[str, dict]:
    """Build email → {pipeline_candidate_id, candidate_profile_id} from DB."""
    rows = session.execute(text(
        "SELECT id, external_email, candidate_profile_id "
        "FROM recruiter_pipeline_candidates "
        "WHERE external_email IS NOT NULL"
    )).fetchall()

    mapping = {}
    for row in rows:
        email = row[1].strip().lower()
        mapping[email] = {
            "pipeline_id": row[0],
            "profile_id": row[2],
        }
    return mapping


def process_one_resume(
    *,
    attach_zip: zipfile.ZipFile,
    resume_path: str,
    pipeline_id: int,
    profile_id: int | None,
    email: str,
    session,
    dry_run: bool = False,
) -> dict:
    """Extract, parse, and link one resume file. Returns status dict."""
    from app.models.candidate_profile import CandidateProfile
    from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
    from app.models.resume_document import ResumeDocument
    from app.services.resume_pipeline import ParseOptions, extract_and_parse
    from app.services.storage import upload_bytes

    filename = os.path.basename(resume_path)
    ext = os.path.splitext(filename)[1].lower()

    if dry_run:
        return {"status": "dry_run", "file": filename}

    # Extract file to temp
    raw_bytes = attach_zip.read(resume_path)
    tmp_path = Path(tempfile.mktemp(suffix=ext))
    tmp_path.write_bytes(raw_bytes)

    try:
        # Parse resume
        result = extract_and_parse(
            tmp_path,
            ParseOptions(parser_strategy="regex_only", min_text_length=20),
        )
        profile_json = result.profile_json
    except (ValueError, Exception) as e:
        return {"status": "parse_failed", "error": str(e), "file": filename}
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    # Save resume file permanently
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    dest_filename = f"{file_hash[:16]}_{filename}"
    stored_path = upload_bytes(raw_bytes, "recruiter_resumes/", dest_filename)

    # Create ResumeDocument
    resume_doc = ResumeDocument(
        user_id=None,
        filename=filename,
        path=stored_path,
        sha256=file_hash,
    )
    session.add(resume_doc)
    session.flush()

    # Update or create CandidateProfile
    profile_json["source"] = "recruitcrm_import"
    profile_json["sourced_by_user_id"] = 9  # Ron's user_id

    if profile_id:
        existing_cp = session.get(CandidateProfile, profile_id)
        if existing_cp:
            # Merge: keep existing basics, add parsed skills/experience
            old_json = existing_cp.profile_json or {}
            # Preserve existing basics (name, email, phone from migration)
            if "basics" in old_json:
                merged_basics = {**profile_json.get("basics", {}), **old_json["basics"]}
                profile_json["basics"] = merged_basics
            # Keep sourced_by
            profile_json["sourced_by_user_id"] = old_json.get("sourced_by_user_id", 9)
            existing_cp.profile_json = profile_json
            existing_cp.resume_document_id = resume_doc.id
            existing_cp.llm_parse_status = "pending"
            cp_id = existing_cp.id
        else:
            new_cp = CandidateProfile(
                user_id=None,
                resume_document_id=resume_doc.id,
                version=1,
                profile_json=profile_json,
                profile_visibility="private",
                open_to_opportunities=False,
                llm_parse_status="pending",
            )
            session.add(new_cp)
            session.flush()
            cp_id = new_cp.id
            # Update pipeline candidate link
            pc = session.get(RecruiterPipelineCandidate, pipeline_id)
            if pc:
                pc.candidate_profile_id = cp_id
    else:
        # Dedup: check if a sourced profile with this email already exists
        email_val = (
            (profile_json.get("basics") or {}).get("email") or ""
        ).strip().lower()
        existing_by_email = None
        if email_val:
            existing_by_email = session.execute(text(
                "SELECT id FROM candidate_profiles "
                "WHERE user_id IS NULL "
                "AND LOWER(profile_json->'basics'->>'email') = :email "
                "LIMIT 1"
            ), {"email": email_val}).scalar_one_or_none()

        if existing_by_email:
            existing_cp = session.get(CandidateProfile, existing_by_email)
            existing_cp.resume_document_id = resume_doc.id
            existing_cp.llm_parse_status = "pending"
            cp_id = existing_cp.id
            pc = session.get(RecruiterPipelineCandidate, pipeline_id)
            if pc:
                pc.candidate_profile_id = cp_id
        else:
            new_cp = CandidateProfile(
                user_id=None,
                resume_document_id=resume_doc.id,
                version=1,
                profile_json=profile_json,
                profile_visibility="private",
                open_to_opportunities=False,
                llm_parse_status="pending",
            )
            session.add(new_cp)
            session.flush()
            cp_id = new_cp.id
            # Update pipeline candidate link
            pc = session.get(RecruiterPipelineCandidate, pipeline_id)
            if pc:
                pc.candidate_profile_id = cp_id

    # Update pipeline candidate tracking
    pc = session.get(RecruiterPipelineCandidate, pipeline_id)
    if pc:
        pc.bulk_attach_status = "attached"
        pc.bulk_attach_matched_by = "email"
        pc.external_resume_url = stored_path

    skills = profile_json.get("skills", [])
    exp_count = len(profile_json.get("experience", []))

    return {
        "status": "success",
        "file": filename,
        "profile_id": cp_id,
        "resume_doc_id": resume_doc.id,
        "skills_count": len(skills),
        "experience_count": exp_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Import RecruitCRM resumes into Winnow")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of resumes to process (0 = all)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip candidates that already have a resume linked")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't write anything")
    parser.add_argument("--batch-size", type=int, default=50, help="Commit every N resumes")
    args = parser.parse_args()

    logger.info("=== RecruitCRM Resume Import ===")
    logger.info("CSV ZIP: %s", CSV_ZIP)
    logger.info("Attachments ZIP: %s", ATTACH_ZIP)

    # Step 1: Build mappings
    logger.info("Building slug → email mapping...")
    slug_to_email = build_slug_to_email(CSV_ZIP)
    logger.info("  %d slugs with email", len(slug_to_email))

    logger.info("Opening attachment ZIP...")
    attach_zip = zipfile.ZipFile(ATTACH_ZIP)

    logger.info("Building slug → resume path mapping...")
    slug_to_resume = build_slug_to_resume_path(CSV_ZIP, attach_zip)
    logger.info("  %d slugs with resume file", len(slug_to_resume))

    logger.info("Building email → pipeline candidate mapping...")
    Session = get_session_factory()
    session = Session()
    email_to_pipeline = build_email_to_pipeline(session)
    logger.info("  %d pipeline candidates with email", len(email_to_pipeline))

    # Step 2: Build the work list
    work_items = []
    for slug, resume_path in slug_to_resume.items():
        email = slug_to_email.get(slug)
        if not email:
            continue
        pipeline = email_to_pipeline.get(email)
        if not pipeline:
            continue

        if args.skip_existing:
            # Check if pipeline candidate already has resume attached
            attached = session.execute(text(
                "SELECT bulk_attach_status FROM recruiter_pipeline_candidates WHERE id = :pid"
            ), {"pid": pipeline["pipeline_id"]}).scalar()
            if attached == "attached":
                continue

        work_items.append({
            "slug": slug,
            "email": email,
            "resume_path": resume_path,
            "pipeline_id": pipeline["pipeline_id"],
            "profile_id": pipeline["profile_id"],
        })

    if args.limit > 0:
        work_items = work_items[:args.limit]

    logger.info("Work items: %d resumes to process", len(work_items))

    if not work_items:
        logger.info("Nothing to do.")
        attach_zip.close()
        session.close()
        return

    # Step 3: Process
    stats = {"success": 0, "parse_failed": 0, "error": 0, "dry_run": 0}
    start_time = time.time()

    for i, item in enumerate(work_items):
        # Use savepoint so a single failure doesn't roll back the whole batch
        savepoint = session.begin_nested()
        try:
            result = process_one_resume(
                attach_zip=attach_zip,
                resume_path=item["resume_path"],
                pipeline_id=item["pipeline_id"],
                profile_id=item["profile_id"],
                email=item["email"],
                session=session,
                dry_run=args.dry_run,
            )
            savepoint.commit()
            stats[result["status"]] = stats.get(result["status"], 0) + 1

            if result["status"] == "parse_failed":
                logger.warning(
                    "  [%d/%d] PARSE FAILED: %s — %s",
                    i + 1, len(work_items), item["email"], result.get("error", ""),
                )
            elif result["status"] == "success" and (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                eta = (len(work_items) - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "  [%d/%d] %s — %d skills, %d exp | %.1f/sec, ETA %.0fs",
                    i + 1, len(work_items), item["email"],
                    result.get("skills_count", 0), result.get("experience_count", 0),
                    rate, eta,
                )
        except Exception as e:
            stats["error"] += 1
            logger.error("  [%d/%d] ERROR: %s — %s", i + 1, len(work_items), item["email"], e)
            savepoint.rollback()

        # Batch commit
        if not args.dry_run and (i + 1) % args.batch_size == 0:
            session.commit()
            logger.info("  Committed batch at %d/%d", i + 1, len(work_items))

    # Final commit
    if not args.dry_run:
        session.commit()

    elapsed = time.time() - start_time
    logger.info("=== Import Complete ===")
    logger.info("  Total: %d", len(work_items))
    logger.info("  Success: %d", stats["success"])
    logger.info("  Parse failed: %d", stats["parse_failed"])
    logger.info("  Errors: %d", stats["error"])
    logger.info("  Time: %.1fs (%.1f/sec)", elapsed, len(work_items) / elapsed if elapsed > 0 else 0)

    attach_zip.close()
    session.close()


if __name__ == "__main__":
    main()
