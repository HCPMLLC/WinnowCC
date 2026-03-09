"""Recruit CRM ZIP orchestrator — imports multi-CSV ZIP exports.

Handles the Recruit CRM multi-file export format:
  company_data.csv → RecruiterClient
  contact_data.csv → merge into RecruiterClient
  job_data.csv     → RecruiterJob
  candidate_data.csv → RecruiterPipelineCandidate
  assignment_data.csv → link candidates to jobs

Also handles Recruit CRM attachments ZIP (nested ZIP with candidate resumes):
  outer.zip → inner.zip → Candidates/{slug}/resumefilename/{file}

Uses in-memory slug_map for O(1) cross-referencing between entities.
"""

import csv
import hashlib
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.migration import MigrationEntityMap, MigrationJob
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.upload_batch import UploadBatch, UploadBatchFile
from app.services.migration.import_engine import BATCH_SIZE, _record_entity
from app.services.migration.recruiter_import_engine import (
    _log_migration_activity,
    _parse_int,
)

logger = logging.getLogger(__name__)

# Date formats Recruit CRM may use
_DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]


def _parse_date(val: str | None) -> datetime | None:
    """Parse a date string from Recruit CRM export."""
    if not val or not str(val).strip():
        return None
    val = str(val).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


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
# Contact "Stage" field → contact role
_CONTACT_STAGE_ROLE: dict[str, str] = {
    "client": "Hiring Manager",
    "lead": "Hiring Manager",
    "prime": "Prime Contractor",
    "hsp": "Prime Contractor",
    "supplier": "Subcontractor",
}

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
        db.rollback()
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
    """Read all recognized CSVs from a ZIP into {filename: [rows]}.

    Supports both local paths and gs:// GCS paths (downloads to a temp
    file first).
    """
    from app.services.storage import download_to_tempfile, is_gcs_path

    local_path = file_path
    tmp_file = None
    if is_gcs_path(file_path):
        tmp_file = download_to_tempfile(file_path, suffix=".zip")
        local_path = str(tmp_file)

    result = {}
    try:
        with zipfile.ZipFile(local_path) as zf:
            for name in zf.namelist():
                basename = name.split("/")[-1].lower()
                for expected in RCRM_CSV_FILES:
                    if basename == expected:
                        with zf.open(name) as f:
                            text = io.TextIOWrapper(f, encoding="utf-8-sig")
                            reader = csv.DictReader(text)
                            result[expected] = list(reader)
                        break
    finally:
        if tmp_file:
            tmp_file.unlink(missing_ok=True)
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
            db.rollback()
            type_stats["errors"] += 1
            type_stats["_errors"].append(
                {"row": i, "entity": "company", "error": str(e)}
            )
            logger.warning("Company row %d error: %s", i, e)

    db.commit()

    # Second pass: resolve parent company relationships
    for slug, parent_slug in parent_links:
        child_id = slug_map.get(f"company:{slug}")
        parent_id = slug_map.get(f"company:{parent_slug}")
        if child_id and parent_id and child_id != parent_id:
            child_client = db.get(RecruiterClient, child_id)
            if child_client:
                child_client.parent_client_id = parent_id
    if parent_links:
        db.commit()

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
            slug = (row.get("Slug") or "").strip()
            company_slug = (row.get("Company Slug") or "").strip()
            first_name = (row.get("First Name") or "").strip()
            last_name = (row.get("Last Name") or "").strip()
            name = f"{first_name} {last_name}".strip()
            email = (row.get("Email") or "").strip()
            phone = (row.get("Contact Number") or "").strip()
            title = (row.get("Designation") or "").strip()

            # Map Stage field to contact role
            stage_raw = (row.get("Stage") or "").strip().lower()
            role = _CONTACT_STAGE_ROLE.get(stage_raw)

            client = None
            if company_slug and f"company:{company_slug}" in slug_map:
                client_id = slug_map[f"company:{company_slug}"]
                client = db.get(RecruiterClient, client_id)

            if client:
                # Track contact slug → client_id for job-level contact resolution
                if slug:
                    slug_map[f"contact:{slug}"] = client.id

                # Append to contacts JSONB array
                contact_entry = {
                    k: v for k, v in {
                        "name": name, "email": email, "phone": phone,
                        "title": title, "role": role,
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
                if slug:
                    slug_map[f"contact:{slug}"] = client.id

                _record_entity(
                    migration_job_id, "contact", slug or str(i),
                    "recruiter_client", client.id, row, "imported", db,
                )
                type_stats["imported"] += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()

        except Exception as e:
            db.rollback()
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

            # Text fields
            description = (row.get("Job Description") or "").strip()
            requirements = (row.get("Requirements") or "").strip() or None
            nice_to_haves = (row.get("Nice to Have") or "").strip() or None
            job_category = (row.get("Job Category") or "").strip() or None
            department = (row.get("Department") or "").strip() or None
            positions_to_fill = _parse_int(row.get("Number Of Openings"))

            # External job ID (Solicitation #)
            job_id_external = (
                row.get("Solicitation #") or row.get("Job ID") or ""
            ).strip() or None

            # Dates
            close_date = _parse_date(row.get("Close Date"))
            start_date = _parse_date(row.get("Start Date"))

            # Resolve job-level primary contact from Contact Slug
            primary_contact = None
            contact_slug = (row.get("Contact Slug") or "").strip()
            contact_name_raw = (row.get("Contact") or "").strip()
            if contact_slug:
                contact_client_id = slug_map.get(f"contact:{contact_slug}")
                if contact_client_id:
                    contact_client = db.get(RecruiterClient, contact_client_id)
                    if contact_client and contact_client.contacts:
                        # Find matching contact by name
                        for ce in contact_client.contacts:
                            if ce.get("name") == contact_name_raw:
                                primary_contact = {
                                    k: v for k, v in {
                                        "name": ce.get("name"),
                                        "email": ce.get("email"),
                                        "phone": ce.get("phone"),
                                        "role": ce.get("role"),
                                    }.items() if v
                                }
                                break
                        # Fallback: first contact with a role priority
                        if not primary_contact:
                            for pref_role in [
                                "Prime Contractor", "Hiring Manager", "Purchaser",
                            ]:
                                for ce in contact_client.contacts:
                                    if ce.get("role") == pref_role:
                                        primary_contact = {
                                            k: v for k, v in {
                                                "name": ce.get("name"),
                                                "email": ce.get("email"),
                                                "phone": ce.get("phone"),
                                                "role": ce.get("role"),
                                            }.items() if v
                                        }
                                        break
                                if primary_contact:
                                    break

            rjob = RecruiterJob(
                recruiter_profile_id=recruiter_profile_id,
                title=title,
                description=description or f"Imported from Recruit CRM: {title}",
                requirements=requirements,
                nice_to_haves=nice_to_haves,
                client_company_name=company_name or None,
                client_id=client_id,
                location=location,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                status=status,
                department=department,
                job_category=job_category,
                job_id_external=job_id_external,
                primary_contact=primary_contact,
                positions_to_fill=positions_to_fill or 1,
                closes_at=close_date,
                start_at=start_date,
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
            db.rollback()
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

            # Dedup by email — enrich existing entry with CSV fields
            if email and email in existing_emails:
                pc_id = existing_emails[email]
                existing_pc = db.get(RecruiterPipelineCandidate, pc_id)
                if existing_pc:
                    if not existing_pc.external_name and name:
                        existing_pc.external_name = name
                    if not existing_pc.external_phone and phone:
                        existing_pc.external_phone = phone
                    if not existing_pc.external_linkedin and linkedin:
                        existing_pc.external_linkedin = linkedin
                    current_org = (row.get("Current Organisation") or "").strip() or None
                    position = (row.get("Position") or "").strip() or None
                    if not existing_pc.current_company and current_org:
                        existing_pc.current_company = current_org
                    if not existing_pc.current_title and position:
                        existing_pc.current_title = position
                    if not existing_pc.location:
                        city = (row.get("City") or "").strip()
                        state = (row.get("State") or "").strip()
                        country = (row.get("Country") or "").strip()
                        loc_parts = [p for p in [city, state, country] if p]
                        if loc_parts:
                            existing_pc.location = ", ".join(loc_parts)
                if slug:
                    slug_map[f"candidate:{slug}"] = pc_id
                _record_entity(
                    migration_job_id, "candidate", slug or str(i),
                    "recruiter_pipeline_candidate", pc_id, row, "merged", db,
                )
                type_stats["merged"] += 1
                continue

            # Professional context
            current_org = (row.get("Current Organisation") or "").strip() or None
            position = (row.get("Position") or "").strip() or None
            city = (row.get("City") or "").strip()
            state = (row.get("State") or "").strip()
            country = (row.get("Country") or "").strip()
            loc_parts = [p for p in [city, state, country] if p]
            candidate_location = ", ".join(loc_parts) or None

            pc = RecruiterPipelineCandidate(
                recruiter_profile_id=recruiter_profile_id,
                external_name=name or None,
                external_email=email or None,
                external_phone=phone or None,
                external_linkedin=linkedin or None,
                current_company=current_org,
                current_title=position,
                location=candidate_location,
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
            db.rollback()
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
            db.rollback()
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


# ---------------------------------------------------------------------------
# Attachments import (Phase 2)
# ---------------------------------------------------------------------------

RESUME_EXTENSIONS = {".pdf", ".docx", ".doc"}
STAGE_BATCH_SIZE = 50


def stage_attachments_job(migration_job_id: int) -> None:
    """RQ worker entry point for attachments import."""
    from app.db.session import get_session_factory

    session = get_session_factory()()
    try:
        stage_recruitcrm_attachments(migration_job_id, session)
    finally:
        session.close()


def stage_recruitcrm_attachments(
    migration_job_id: int, db: Session
) -> dict:
    """Extract resumes from attachments ZIP, match & enqueue.

    Runs as a background RQ job. Creates UploadBatch +
    UploadBatchFile rows and enqueues process_bulk_attach_file
    workers for each matched resume.
    """
    from app.services.bulk_resume_attach import process_bulk_attach_file
    from app.services.queue import get_queue
    from app.services.storage import upload_bytes

    job = db.execute(
        select(MigrationJob).where(MigrationJob.id == migration_job_id)
    ).scalar_one_or_none()
    if not job:
        raise ValueError(f"Migration job {migration_job_id} not found")

    config = job.config_json or {}
    recruiter_profile_id = config.get("recruiter_profile_id")
    csv_migration_job_id = config.get("csv_migration_job_id")

    if not recruiter_profile_id:
        raise ValueError("recruiter_profile_id missing from job config")
    if not csv_migration_job_id:
        raise ValueError("csv_migration_job_id missing from job config")

    try:
        # Build slug → pipeline_candidate_id map from the prior CSV migration
        slug_to_pc = _build_slug_map(csv_migration_job_id, db)
        if not slug_to_pc:
            raise ValueError(
                "No candidate mappings found from prior CSV migration. "
                "Ensure the CSV import completed successfully."
            )

        outer_path = job.source_file_path
        if not outer_path:
            raise FileNotFoundError("Source file path is empty")

        # Handle GCS paths — download to temp file first
        from app.services.storage import is_gcs_path

        gcs_tmp = None
        if is_gcs_path(outer_path):
            from app.services.storage import download_to_tempfile

            gcs_tmp = download_to_tempfile(outer_path, suffix=".zip")
            outer_path = str(gcs_tmp)
        elif not os.path.exists(outer_path):
            raise FileNotFoundError(
                f"Source file not found: {outer_path}"
            )

        # Extract inner ZIP to a temp file (avoid holding 1.4GB in RAM twice)
        with tempfile.TemporaryDirectory() as temp_dir:
            inner_path = _extract_inner_zip(outer_path, temp_dir)
            if not inner_path:
                raise ValueError("No inner ZIP found in attachments export")

            # Scan for candidate resumes and match to slug map
            matched, unmatched = _scan_and_match_resumes(inner_path, slug_to_pc)

            if not matched:
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.stats_json = {
                    "total_resumes": 0,
                    "matched": 0,
                    "unmatched": len(unmatched),
                    "message": "No resumes matched to imported candidates",
                }
                db.commit()
                return {"job_id": migration_job_id, "status": "completed"}

            # Create UploadBatch
            batch_id = str(uuid4())
            batch = UploadBatch(
                batch_id=batch_id,
                user_id=job.user_id,
                batch_type="recruitcrm_attachments",
                owner_profile_id=recruiter_profile_id,
                status="pending",
                total_files=len(matched),
            )
            db.add(batch)
            db.flush()

            # Update migration job with batch info early so frontend can poll
            job.stats_json = {
                "batch_id": batch_id,
                "total_resumes": len(matched) + len(unmatched),
                "matched": len(matched),
                "unmatched": len(unmatched),
            }
            db.commit()

            # Stage files in batches and enqueue workers
            bulk_queue = get_queue("bulk")
            staged_count = 0
            stage_errors = 0

            with zipfile.ZipFile(inner_path) as izf:
                batch_files_to_enqueue: list[int] = []

                for idx, (zip_entry, pc_id, slug) in enumerate(matched):
                    try:
                        file_bytes = izf.read(zip_entry)
                        filename = Path(zip_entry).name
                        file_hash = hashlib.sha256(file_bytes).hexdigest()

                        staged_name = f"{idx}_{file_hash[:12]}_{filename}"
                        staged_path = upload_bytes(
                            file_bytes, f"staging/{batch_id}/", staged_name
                        )

                        bf = UploadBatchFile(
                            batch_id=batch_id,
                            file_index=idx,
                            original_filename=filename,
                            staged_path=staged_path,
                            file_size_bytes=len(file_bytes),
                            sha256=file_hash,
                            status="pending",
                            result_json=json.dumps({
                                "candidate_id": pc_id,
                                "matched_by": "slug",
                            }),
                        )
                        db.add(bf)
                        db.flush()
                        batch_files_to_enqueue.append(bf.id)
                        staged_count += 1
                        del file_bytes

                    except Exception as e:
                        stage_errors += 1
                        logger.warning(
                            "Failed to stage resume %s for candidate %s: %s",
                            zip_entry, slug, e,
                        )

                    # Commit + enqueue in batches
                    if len(batch_files_to_enqueue) >= STAGE_BATCH_SIZE:
                        db.commit()
                        for bf_id in batch_files_to_enqueue:
                            bulk_queue.enqueue(
                                process_bulk_attach_file,
                                bf_id,
                                batch_id,
                                recruiter_profile_id,
                                job_timeout="10m",
                            )
                        batch_files_to_enqueue = []

                # Flush remaining
                if batch_files_to_enqueue:
                    db.commit()
                    for bf_id in batch_files_to_enqueue:
                        bulk_queue.enqueue(
                            process_bulk_attach_file,
                            bf_id,
                            batch_id,
                            recruiter_profile_id,
                            job_timeout="10m",
                        )

            # Activate batch
            batch.status = "processing"
            job.stats_json = {
                **job.stats_json,
                "staged": staged_count,
                "stage_errors": stage_errors,
            }
            db.commit()

            _log_migration_activity(
                db, recruiter_profile_id, "attachments_staged",
                f"Staged {staged_count} resumes from Recruit CRM attachments",
                {
                    "migration_job_id": migration_job_id,
                    "batch_id": batch_id,
                    "matched": len(matched),
                    "unmatched": len(unmatched),
                },
            )

        return {
            "job_id": migration_job_id,
            "status": "importing",
            "batch_id": batch_id,
            "matched": len(matched),
        }

    except Exception as e:
        db.rollback()
        job.status = "failed"
        job.error_log = [{"error": str(e)[:1000], "fatal": True}]
        job.updated_at = datetime.now(UTC)
        db.commit()
        logger.exception(
            "Recruit CRM attachments migration job %d failed",
            migration_job_id,
        )
        return {"job_id": migration_job_id, "status": "failed"}
    finally:
        # Clean up GCS temp download
        if gcs_tmp is not None:
            try:
                gcs_tmp.unlink(missing_ok=True)
            except OSError:
                pass


def _build_slug_map(csv_migration_job_id: int, db: Session) -> dict[str, int]:
    """Build slug → pipeline_candidate_id from the prior CSV migration's entity map."""
    rows = db.execute(
        select(
            MigrationEntityMap.source_entity_id,
            MigrationEntityMap.winnow_entity_id,
        ).where(
            MigrationEntityMap.migration_job_id == csv_migration_job_id,
            MigrationEntityMap.source_entity_type == "candidate",
            MigrationEntityMap.winnow_entity_id.isnot(None),
        )
    ).all()
    return {row.source_entity_id: row.winnow_entity_id for row in rows}


def _extract_inner_zip(outer_path: str, temp_dir: str) -> str | None:
    """Extract the inner ZIP from the outer attachments export to disk."""
    with zipfile.ZipFile(outer_path) as zf:
        inner_names = [n for n in zf.namelist() if n.lower().endswith(".zip")]
        if not inner_names:
            return None
        inner_name = inner_names[0]
        zf.extract(inner_name, temp_dir)
        return os.path.join(temp_dir, inner_name)


def _scan_and_match_resumes(
    inner_zip_path: str,
    slug_to_pc: dict[str, int],
) -> tuple[list[tuple[str, int, str]], list[str]]:
    """Scan inner ZIP for candidate resumes, match by slug.

    Returns (matched, unmatched_slugs).
    matched = [(zip_entry_name, pipeline_candidate_id, slug), ...]
    """
    # Group files by candidate slug, picking the largest resumefilename/ file
    slug_files: dict[str, list[tuple[str, int]]] = {}  # slug -> [(entry, size)]

    with zipfile.ZipFile(inner_zip_path) as izf:
        for info in izf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            # Expected: Candidates/{slug}/resumefilename/{file}
            if not name.startswith("Candidates/"):
                continue
            if "/resumefilename/" not in name:
                continue
            ext = Path(name).suffix.lower()
            if ext not in RESUME_EXTENSIONS:
                continue

            parts = name.split("/")
            if len(parts) < 4:
                continue
            slug = parts[1]

            if slug not in slug_files:
                slug_files[slug] = []
            slug_files[slug].append((name, info.file_size))

    matched: list[tuple[str, int, str]] = []
    unmatched: list[str] = []

    for slug, files in slug_files.items():
        pc_id = slug_to_pc.get(slug)
        if not pc_id:
            unmatched.append(slug)
            continue

        # Pick the largest file (most complete resume)
        best_entry = max(files, key=lambda x: x[1])[0]
        matched.append((best_entry, pc_id, slug))

    return matched, unmatched
