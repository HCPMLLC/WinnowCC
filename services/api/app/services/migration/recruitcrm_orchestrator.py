"""Recruit CRM ZIP orchestrator — imports multi-CSV ZIP exports.

Handles the Recruit CRM multi-file export format:
  company_data.csv → RecruiterClient
  contact_data.csv → merge into RecruiterClient
  job_data.csv     → RecruiterJob
  candidate_data.csv → RecruiterPipelineCandidate
  assignment_data.csv → link candidates to jobs

Uses in-memory slug_map for O(1) cross-referencing between entities.
"""

import csv
import io
import logging
import zipfile
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.migration import MigrationJob
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.services.migration.import_engine import BATCH_SIZE, _record_entity
from app.services.migration.recruiter_import_engine import (
    _log_migration_activity,
    _parse_int,
)

logger = logging.getLogger(__name__)

# Recruit CRM assignment status → Winnow stage
RCRM_ASSIGNMENT_STAGES: dict[str, str] = {
    "Applied": "sourced",
    "Assigned": "sourced",
    "Invited to Apply": "sourced",
    "Demographics Requested": "contacted",
    "Submittal Forms Sent": "contacted",
    "Submittal Forms Received": "screening",
    "Submitted to Prime": "screening",
    "Interviewing": "interviewing",
    "Selected": "placed",
    "Did Not Join": "rejected",
    "Insufficient Experience": "rejected",
    "Non-Resident": "rejected",
    "Not in Consideration": "rejected",
}

# Recruit CRM job status → Winnow job status
RCRM_JOB_STATUS: dict[str, str] = {
    "Open": "active",
    "Closed": "closed",
    "Canceled": "closed",
    "Lost": "closed",
    "Submitted": "active",
    "Interviewing": "active",
}

# Expected CSV filenames in the ZIP
RCRM_CSV_FILES = {
    "company_data.csv": "companies",
    "contact_data.csv": "contacts",
    "job_data.csv": "jobs",
    "candidate_data.csv": "candidates",
    "assignment_data.csv": "assignments",
}


def run_recruitcrm_zip_migration(migration_job_id: int, db: Session) -> dict:
    """Execute a Recruit CRM multi-CSV ZIP migration.

    Import order: Companies → Contacts → Jobs → Candidates → Assignments.
    Returns the same shape as run_recruiter_migration for API compat.
    """
    job = db.execute(
        select(MigrationJob).where(MigrationJob.id == migration_job_id)
    ).scalar_one_or_none()
    if not job:
        raise ValueError(f"Migration job {migration_job_id} not found")

    job.status = "importing"
    job.started_at = datetime.now(UTC)
    db.commit()

    config = job.config_json or {}
    recruiter_profile_id = config.get("recruiter_profile_id")
    if not recruiter_profile_id:
        raise ValueError("recruiter_profile_id missing from job config")

    stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "by_type": {}}
    errors: list[dict] = []

    try:
        file_path = job.source_file_path
        if not file_path:
            raise FileNotFoundError("Source file path is empty")

        # Read all CSVs from ZIP into memory
        csv_data = _read_csvs_from_zip(file_path)
        slug_map: dict[str, int] = {}  # "entity_type:slug" → winnow_id

        # 1. Companies
        if "company_data.csv" in csv_data:
            type_stats = _import_companies(
                migration_job_id, recruiter_profile_id,
                csv_data["company_data.csv"], slug_map, db,
            )
            stats["by_type"]["companies"] = type_stats
            _add_type_stats(stats, type_stats)
            errors.extend(type_stats.pop("_errors", []))

        # 2. Contacts → merge into RecruiterClient
        if "contact_data.csv" in csv_data:
            type_stats = _import_contacts(
                migration_job_id, recruiter_profile_id,
                csv_data["contact_data.csv"], slug_map, db,
            )
            stats["by_type"]["contacts"] = type_stats
            _add_type_stats(stats, type_stats)
            errors.extend(type_stats.pop("_errors", []))

        # 3. Jobs
        if "job_data.csv" in csv_data:
            type_stats = _import_jobs(
                migration_job_id, recruiter_profile_id,
                csv_data["job_data.csv"], slug_map, db,
            )
            stats["by_type"]["jobs"] = type_stats
            _add_type_stats(stats, type_stats)
            errors.extend(type_stats.pop("_errors", []))

        # 4. Candidates
        if "candidate_data.csv" in csv_data:
            type_stats = _import_candidates(
                migration_job_id, recruiter_profile_id,
                csv_data["candidate_data.csv"], slug_map, db,
            )
            stats["by_type"]["candidates"] = type_stats
            _add_type_stats(stats, type_stats)
            errors.extend(type_stats.pop("_errors", []))

        # 5. Assignments → link candidates to jobs
        if "assignment_data.csv" in csv_data:
            type_stats = _import_assignments(
                migration_job_id, recruiter_profile_id,
                csv_data["assignment_data.csv"], slug_map, db,
            )
            stats["by_type"]["assignments"] = type_stats
            _add_type_stats(stats, type_stats)
            errors.extend(type_stats.pop("_errors", []))

        job.status = "completed"
        job.completed_at = datetime.now(UTC)

        _log_migration_activity(
            db, recruiter_profile_id, "migration_completed",
            "Completed Recruit CRM ZIP migration",
            {
                "migration_job_id": migration_job_id,
                "platform": "recruitcrm",
                "stats": stats,
            },
        )

    except Exception as e:
        job.status = "failed"
        errors.append({"error": str(e), "fatal": True})
        logger.exception("Recruit CRM ZIP migration job %d failed", migration_job_id)

    job.stats_json = stats
    job.error_log = errors if errors else None
    job.updated_at = datetime.now(UTC)
    db.commit()

    return {"job_id": migration_job_id, "status": job.status, "stats": stats}


# ---------------------------------------------------------------------------
# ZIP reader
# ---------------------------------------------------------------------------

def _read_csvs_from_zip(file_path: str) -> dict[str, list[dict]]:
    """Read all recognized CSVs from a ZIP into {filename: [rows]}."""
    result = {}
    with zipfile.ZipFile(file_path) as zf:
        for name in zf.namelist():
            basename = name.split("/")[-1].lower()
            # Match against known filenames (case-insensitive)
            for expected in RCRM_CSV_FILES:
                if basename == expected:
                    with zf.open(name) as f:
                        text = io.TextIOWrapper(f, encoding="utf-8-sig")
                        reader = csv.DictReader(text)
                        result[expected] = list(reader)
                    break
    return result


# ---------------------------------------------------------------------------
# Entity importers
# ---------------------------------------------------------------------------

def _import_companies(
    migration_job_id: int,
    recruiter_profile_id: int,
    rows: list[dict],
    slug_map: dict[str, int],
    db: Session,
) -> dict:
    """Import company_data.csv → RecruiterClient."""
    type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "_errors": []}
    parent_links: list[tuple[str, str]] = []  # (slug, parent_slug) for second pass

    for i, row in enumerate(rows):
        try:
            slug = (row.get("Slug") or "").strip()
            company_name = (row.get("Company") or row.get("Name") or "").strip()
            if not company_name:
                type_stats["skipped"] += 1
                continue

            # Dedup by company_name scoped to recruiter
            existing = db.execute(
                select(RecruiterClient).where(
                    RecruiterClient.recruiter_profile_id == recruiter_profile_id,
                    func.lower(RecruiterClient.company_name) == company_name.lower(),
                )
            ).scalar_one_or_none()

            if existing:
                if row.get("Website") and not existing.website:
                    existing.website = row["Website"]
                if row.get("Industry") and not existing.industry:
                    existing.industry = row["Industry"]
                if slug:
                    slug_map[f"company:{slug}"] = existing.id
                _record_entity(
                    migration_job_id, "company", slug or str(i),
                    "recruiter_client", existing.id, row, "merged", db,
                )
                type_stats["merged"] += 1
            else:
                client = RecruiterClient(
                    recruiter_profile_id=recruiter_profile_id,
                    company_name=company_name,
                    industry=row.get("Industry") or None,
                    website=row.get("Website") or None,
                )
                db.add(client)
                db.flush()
                if slug:
                    slug_map[f"company:{slug}"] = client.id
                _record_entity(
                    migration_job_id, "company", slug or str(i),
                    "recruiter_client", client.id, row, "imported", db,
                )
                type_stats["imported"] += 1

            # Track parent company for second pass
            parent_slug = (row.get("Parent Company Slug") or "").strip()
            if parent_slug and slug:
                parent_links.append((slug, parent_slug))

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            type_stats["errors"] += 1
            type_stats["_errors"].append(
                {"row": i, "entity": "company", "error": str(e)}
            )
            logger.warning("Company row %d error: %s", i, e)

    db.commit()

    # Second pass: resolve parent company relationships
    # (RecruiterClient doesn't have parent_client_id yet — skip for now)
    # Future: for slug, parent_slug in parent_links: ...

    return type_stats


def _import_contacts(
    migration_job_id: int,
    recruiter_profile_id: int,
    rows: list[dict],
    slug_map: dict[str, int],
    db: Session,
) -> dict:
    """Import contact_data.csv → merge into RecruiterClient."""
    type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "_errors": []}

    for i, row in enumerate(rows):
        try:
            company_slug = (row.get("Company Slug") or "").strip()
            first_name = (row.get("First Name") or "").strip()
            last_name = (row.get("Last Name") or "").strip()
            name = f"{first_name} {last_name}".strip()
            email = (row.get("Email") or "").strip()
            phone = (row.get("Contact Number") or "").strip()
            title = (row.get("Designation") or "").strip()

            client = None
            if company_slug and f"company:{company_slug}" in slug_map:
                client_id = slug_map[f"company:{company_slug}"]
                client = db.get(RecruiterClient, client_id)

            if client:
                # Append to contacts JSONB array
                contact_entry = {
                    k: v for k, v in {
                        "name": name, "email": email, "phone": phone, "title": title,
                    }.items() if v
                }
                if contact_entry:
                    current_contacts = client.contacts or []
                    current_contacts.append(contact_entry)
                    client.contacts = current_contacts

                # Set primary contact fields if empty
                if name and not client.contact_name:
                    client.contact_name = name
                if email and not client.contact_email:
                    client.contact_email = email
                if phone and not client.contact_phone:
                    client.contact_phone = phone
                if title and not client.contact_title:
                    client.contact_title = title

                slug = (row.get("Slug") or "").strip()
                _record_entity(
                    migration_job_id, "contact", slug or str(i),
                    "recruiter_client", client.id, row, "merged", db,
                )
                type_stats["merged"] += 1
            else:
                # No matching company — create a new client from contact info
                company_name = name or email or f"Contact {i}"
                client = RecruiterClient(
                    recruiter_profile_id=recruiter_profile_id,
                    company_name=company_name,
                    contact_name=name or None,
                    contact_email=email or None,
                    contact_phone=phone or None,
                    contact_title=title or None,
                )
                db.add(client)
                db.flush()

                if company_slug:
                    slug_map[f"company:{company_slug}"] = client.id

                slug = (row.get("Slug") or "").strip()
                _record_entity(
                    migration_job_id, "contact", slug or str(i),
                    "recruiter_client", client.id, row, "imported", db,
                )
                type_stats["imported"] += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            type_stats["errors"] += 1
            type_stats["_errors"].append(
                {"row": i, "entity": "contact", "error": str(e)}
            )
            logger.warning("Contact row %d error: %s", i, e)

    db.commit()
    return type_stats


def _import_jobs(
    migration_job_id: int,
    recruiter_profile_id: int,
    rows: list[dict],
    slug_map: dict[str, int],
    db: Session,
) -> dict:
    """Import job_data.csv → RecruiterJob."""
    type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "_errors": []}

    for i, row in enumerate(rows):
        try:
            slug = (row.get("Slug") or "").strip()
            title = (row.get("Name") or row.get("Job Title") or "").strip()
            if not title:
                type_stats["skipped"] += 1
                continue

            # Resolve company
            company_slug = (row.get("Company Slug") or "").strip()
            client_id = slug_map.get(f"company:{company_slug}")
            company_name = (row.get("Company") or "").strip()

            # Map status
            raw_status = (row.get("Job Status") or "").strip()
            status = RCRM_JOB_STATUS.get(raw_status, "active")

            # Parse salary
            salary_min = _parse_int(row.get("Minimum Annual Salary"))
            salary_max = _parse_int(row.get("Maximum Annual Salary"))

            # Location
            city = (row.get("City") or "").strip()
            state = (row.get("State") or "").strip()
            country = (row.get("Country") or "").strip()
            location_parts = [p for p in [city, state, country] if p]
            location = ", ".join(location_parts) or None

            # Employment type
            employment_type = (row.get("Job Type") or "").strip() or None

            rjob = RecruiterJob(
                recruiter_profile_id=recruiter_profile_id,
                title=title,
                description=f"Imported from Recruit CRM: {title}",
                client_company_name=company_name or None,
                client_id=client_id,
                location=location,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                status=status,
            )
            db.add(rjob)
            db.flush()

            if slug:
                slug_map[f"job:{slug}"] = rjob.id

            _record_entity(
                migration_job_id, "job", slug or str(i),
                "recruiter_job", rjob.id, row, "imported", db,
            )
            type_stats["imported"] += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            type_stats["errors"] += 1
            type_stats["_errors"].append({"row": i, "entity": "job", "error": str(e)})
            logger.warning("Job row %d error: %s", i, e)

    db.commit()
    return type_stats


def _import_candidates(
    migration_job_id: int,
    recruiter_profile_id: int,
    rows: list[dict],
    slug_map: dict[str, int],
    db: Session,
) -> dict:
    """Import candidate_data.csv → RecruiterPipelineCandidate."""
    type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "_errors": []}

    # Pre-load existing emails for O(1) dedup
    existing_emails: dict[str, int] = {}
    existing_pcs = db.execute(
        select(
            RecruiterPipelineCandidate.id,
            RecruiterPipelineCandidate.external_email,
        ).where(
            RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
            RecruiterPipelineCandidate.external_email.isnot(None),
        )
    ).all()
    for pc_id, pc_email in existing_pcs:
        if pc_email:
            existing_emails[pc_email.lower()] = pc_id

    for i, row in enumerate(rows):
        try:
            slug = (row.get("Slug") or "").strip()
            first_name = (row.get("First Name") or "").strip()
            last_name = (row.get("Last Name") or "").strip()
            name = f"{first_name} {last_name}".strip()
            email = (row.get("Email") or "").strip().lower()
            phone = (row.get("Contact Number") or "").strip()
            linkedin = (row.get("Profile Linkedin") or "").strip()
            source = (row.get("Source") or "").strip() or "migration_recruitcrm"

            if not email and not name:
                type_stats["skipped"] += 1
                continue

            # Dedup by email
            if email and email in existing_emails:
                pc_id = existing_emails[email]
                if slug:
                    slug_map[f"candidate:{slug}"] = pc_id
                _record_entity(
                    migration_job_id, "candidate", slug or str(i),
                    "recruiter_pipeline_candidate", pc_id, row, "merged", db,
                )
                type_stats["merged"] += 1
                continue

            pc = RecruiterPipelineCandidate(
                recruiter_profile_id=recruiter_profile_id,
                external_name=name or None,
                external_email=email or None,
                external_phone=phone or None,
                external_linkedin=linkedin or None,
                source=source,
                stage="sourced",
            )
            db.add(pc)
            db.flush()

            if slug:
                slug_map[f"candidate:{slug}"] = pc.id
            if email:
                existing_emails[email] = pc.id

            _record_entity(
                migration_job_id, "candidate", slug or str(i),
                "recruiter_pipeline_candidate", pc.id, row, "imported", db,
            )
            type_stats["imported"] += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            type_stats["errors"] += 1
            type_stats["_errors"].append(
                {"row": i, "entity": "candidate", "error": str(e)}
            )
            logger.warning("Candidate row %d error: %s", i, e)

    db.commit()
    return type_stats


def _import_assignments(
    migration_job_id: int,
    recruiter_profile_id: int,
    rows: list[dict],
    slug_map: dict[str, int],
    db: Session,
) -> dict:
    """Import assignment_data.csv → link candidates to jobs with stage."""
    type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "_errors": []}

    # Group assignments by candidate to pick the most recent per candidate-job pair
    # Key: (candidate_slug, job_slug) → (stage_date_str, row_index, row)
    best_assignments: dict[tuple[str, str], tuple[str, int, dict]] = {}

    for i, row in enumerate(rows):
        cand_slug = (row.get("Candidate Slug") or "").strip()
        job_slug = (row.get("Job Slug") or "").strip()
        if not cand_slug or not job_slug:
            continue
        stage_date = (row.get("Stage Date") or "").strip()
        key = (cand_slug, job_slug)
        existing = best_assignments.get(key)
        if not existing or stage_date > existing[0]:
            best_assignments[key] = (stage_date, i, row)

    batch_count = 0
    for (cand_slug, job_slug), (_, row_idx, row) in best_assignments.items():
        try:
            pc_id = slug_map.get(f"candidate:{cand_slug}")
            job_id = slug_map.get(f"job:{job_slug}")

            if not pc_id:
                type_stats["skipped"] += 1
                continue

            pc = db.get(RecruiterPipelineCandidate, pc_id)
            if not pc:
                type_stats["skipped"] += 1
                continue

            # Link to job
            if job_id:
                pc.recruiter_job_id = job_id

            # Map stage
            raw_status = (row.get("Candidate Status") or "").strip()
            stage = RCRM_ASSIGNMENT_STAGES.get(raw_status, "sourced")
            pc.stage = stage

            slug = (row.get("Slug") or f"assign-{row_idx}").strip()
            _record_entity(
                migration_job_id, "assignment", slug,
                "recruiter_pipeline_candidate", pc.id, row, "imported", db,
            )
            type_stats["imported"] += 1

            batch_count += 1
            if batch_count % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            type_stats["errors"] += 1
            type_stats["_errors"].append(
                {"row": row_idx, "entity": "assignment",
                 "error": str(e)}
            )
            logger.warning("Assignment row %d error: %s", row_idx, e)

    db.commit()
    return type_stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_type_stats(stats: dict, type_stats: dict) -> None:
    """Add type_stats counts to the top-level stats."""
    for key in ("imported", "merged", "skipped", "errors"):
        stats[key] += type_stats.get(key, 0)
