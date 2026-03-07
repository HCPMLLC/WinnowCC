"""Recruiter import engine — processes migration jobs into recruiter CRM entities.

Import order: companies/contacts -> jobs -> candidates -> placements.
Batched commits (100 rows), dedup scoped to recruiter profile, parent-child resolution.
Creates RecruiterClient, RecruiterJob, RecruiterPipelineCandidate.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.migration import MigrationEntityMap, MigrationJob
from app.models.recruiter_activity import RecruiterActivity
from app.models.recruiter_client import RecruiterClient
from app.models.recruiter_job import RecruiterJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.services.migration.import_engine import (
    _map_row,
    _read_csv,
    _record_entity,
)
from app.services.migration.platform_detector import FIELD_MAPPINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status/stage mapping constants
# ---------------------------------------------------------------------------

STAGE_MAPPINGS: dict[str, dict[str, str]] = {
    "bullhorn": {
        "New Lead": "sourced",
        "Submitted": "screening",
        "Interview": "interviewing",
        "Offer": "offered",
        "Placed": "placed",
        "Rejected": "rejected",
        "Active": "sourced",
        "Inactive": "rejected",
    },
    "recruitcrm": {
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
    },
    "catsone": {
        "Active": "sourced",
        "Submitted": "screening",
        "Interviewing": "interviewing",
        "Placed": "placed",
        "Inactive": "rejected",
    },
    "zoho_recruit": {
        "New": "sourced",
        "Associated": "contacted",
        "Screening": "screening",
        "Offered": "offered",
        "Hired": "placed",
        "Rejected": "rejected",
    },
}

JOB_STATUS_MAPPINGS: dict[str, str] = {
    "Open": "active",
    "Active": "active",
    "Approved": "active",
    "Closed": "closed",
    "Filled": "closed",
    "On Hold": "paused",
    "Draft": "draft",
    "Cancelled": "closed",
}

RECRUITER_WINNOW_TYPES: dict[str, str] = {
    "candidates": "recruiter_pipeline_candidate",
    "companies": "recruiter_client",
    "contacts": "recruiter_client",
    "jobs": "recruiter_job",
    "placements": "recruiter_pipeline_candidate",
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_recruiter_migration(migration_job_id: int, db: Session) -> dict:
    """Execute a recruiter migration job.

    1. Load job and determine platform/entity type
    2. Read CSV and map fields
    3. Import entities into recruiter CRM tables
    4. Resolve cross-entity relationships
    5. Log activity and update stats
    """
    job = db.execute(
        select(MigrationJob).where(MigrationJob.id == migration_job_id)
    ).scalar_one_or_none()
    if not job:
        raise ValueError(f"Migration job {migration_job_id} not found")

    if job.status != "importing":
        job.status = "importing"
        job.started_at = datetime.now(UTC)
        db.commit()

    config = job.config_json or {}
    recruiter_profile_id = config.get("recruiter_profile_id")

    stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0, "by_type": {}}
    errors: list[dict] = []

    try:
        if not recruiter_profile_id:
            raise ValueError("recruiter_profile_id missing from job config")
        file_path = job.source_file_path
        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")

        platform = job.source_platform_detected or job.source_platform
        field_mapping = FIELD_MAPPINGS.get(platform, {})

        entity_type = config.get("entity_type", "candidates")

        rows = _read_csv(file_path)
        stats["total_rows"] = len(rows)
        type_stats = {"imported": 0, "merged": 0, "skipped": 0, "errors": 0}

        # Write initial stats so polling shows total immediately
        job.stats_json = {**stats}
        job.updated_at = datetime.now(UTC)
        db.commit()

        for i, row in enumerate(rows):
            try:
                mapped = _map_row(row, field_mapping)
                source_id = mapped.get("external_id") or mapped.get("email") or str(i)

                if entity_type in ("companies", "contacts"):
                    result = _import_client(
                        migration_job_id,
                        recruiter_profile_id,
                        source_id,
                        mapped,
                        row,
                        db,
                    )
                elif entity_type == "jobs":
                    result = _import_recruiter_job(
                        migration_job_id,
                        recruiter_profile_id,
                        platform,
                        source_id,
                        mapped,
                        row,
                        db,
                    )
                elif entity_type == "candidates":
                    result = _import_pipeline_candidate(
                        migration_job_id,
                        recruiter_profile_id,
                        platform,
                        source_id,
                        mapped,
                        row,
                        db,
                    )
                elif entity_type == "placements":
                    result = _import_placement(
                        migration_job_id,
                        recruiter_profile_id,
                        platform,
                        source_id,
                        mapped,
                        row,
                        db,
                    )
                else:
                    # Unknown entity type — store in entity map for reference
                    winnow_type = RECRUITER_WINNOW_TYPES.get(entity_type, entity_type)
                    _record_entity(
                        migration_job_id,
                        entity_type,
                        source_id,
                        winnow_type,
                        None,
                        row,
                        "imported",
                        db,
                    )
                    result = "imported"

                type_stats[result] += 1
                stats[result] += 1

                if (i + 1) % 10 == 0:
                    # Update stats frequently so polling shows live progress
                    job.stats_json = {**stats}
                    job.updated_at = datetime.now(UTC)
                    db.commit()

            except Exception as e:
                db.rollback()
                type_stats["errors"] += 1
                stats["errors"] += 1
                errors.append({"row": i, "error": str(e)})
                logger.warning("Row %d import error: %s", i, e)

        db.commit()
        stats["by_type"][entity_type] = type_stats

        _resolve_recruiter_relationships(migration_job_id, recruiter_profile_id, db)

        job.status = "completed"
        job.completed_at = datetime.now(UTC)

        # Log completion activity
        _log_migration_activity(
            db,
            recruiter_profile_id,
            "migration_completed",
            f"Completed migration from {platform}",
            {
                "migration_job_id": migration_job_id,
                "platform": platform,
                "stats": stats,
            },
        )

    except Exception as e:
        job.status = "failed"
        errors.append({"error": str(e), "fatal": True})
        logger.exception("Recruiter migration job %d failed", migration_job_id)

    job.stats_json = stats
    job.error_log = errors if errors else None
    job.updated_at = datetime.now(UTC)
    db.commit()

    return {"job_id": migration_job_id, "status": job.status, "stats": stats}


# ---------------------------------------------------------------------------
# Entity import functions
# ---------------------------------------------------------------------------


def _import_client(
    migration_job_id: int,
    recruiter_profile_id: int,
    source_id: str,
    mapped: dict,
    raw: dict,
    db: Session,
) -> str:
    """Import a company/contact row → RecruiterClient."""
    company_name = (mapped.get("company_name") or mapped.get("company") or "").strip()
    if not company_name:
        _record_entity(
            migration_job_id,
            "company",
            source_id,
            "recruiter_client",
            None,
            raw,
            "skipped",
            db,
        )
        return "skipped"

    # Dedup by company_name scoped to this recruiter
    existing = db.execute(
        select(RecruiterClient).where(
            RecruiterClient.recruiter_profile_id == recruiter_profile_id,
            func.lower(RecruiterClient.company_name) == company_name.lower(),
        )
    ).scalar_one_or_none()

    if existing:
        # Merge empty fields only
        if mapped.get("website") and not existing.website:
            existing.website = mapped["website"]
        if mapped.get("industry") and not existing.industry:
            existing.industry = mapped["industry"]
        if mapped.get("email") and not existing.contact_email:
            existing.contact_email = mapped["email"]
        if mapped.get("phone") and not existing.contact_phone:
            existing.contact_phone = mapped["phone"]

        contact_name = _build_name(mapped)
        if contact_name and not existing.contact_name:
            existing.contact_name = contact_name
        if mapped.get("job_title") and not existing.contact_title:
            existing.contact_title = mapped["job_title"]

        _record_entity(
            migration_job_id,
            "company",
            source_id,
            "recruiter_client",
            existing.id,
            raw,
            "merged",
            db,
        )
        return "merged"

    # Create new client
    contact_name = _build_name(mapped)
    client = RecruiterClient(
        recruiter_profile_id=recruiter_profile_id,
        company_name=company_name,
        industry=mapped.get("industry"),
        website=mapped.get("website"),
        contact_name=contact_name or None,
        contact_email=mapped.get("email"),
        contact_phone=mapped.get("phone"),
        contact_title=mapped.get("job_title"),
    )
    db.add(client)
    db.flush()

    _record_entity(
        migration_job_id,
        "company",
        source_id,
        "recruiter_client",
        client.id,
        raw,
        "imported",
        db,
    )
    return "imported"


def _import_recruiter_job(
    migration_job_id: int,
    recruiter_profile_id: int,
    platform: str,
    source_id: str,
    mapped: dict,
    raw: dict,
    db: Session,
) -> str:
    """Import a job row → RecruiterJob."""
    title = (mapped.get("job_title") or mapped.get("title") or "").strip()
    if not title:
        _record_entity(
            migration_job_id,
            "job",
            source_id,
            "recruiter_job",
            None,
            raw,
            "skipped",
            db,
        )
        return "skipped"

    company = (mapped.get("company") or mapped.get("company_name") or "").strip()

    # Dedup by (title, company) scoped to recruiter
    stmt = select(RecruiterJob).where(
        RecruiterJob.recruiter_profile_id == recruiter_profile_id,
        func.lower(RecruiterJob.title) == title.lower(),
    )
    if company:
        stmt = stmt.where(
            func.lower(RecruiterJob.client_company_name) == company.lower()
        )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        _record_entity(
            migration_job_id,
            "job",
            source_id,
            "recruiter_job",
            existing.id,
            raw,
            "merged",
            db,
        )
        return "merged"

    # Build location
    location = mapped.get("location") or ""
    if not location:
        parts = [mapped.get("city", ""), mapped.get("state", "")]
        location = ", ".join(p for p in parts if p) or None

    # Map status
    raw_status = mapped.get("status", "")
    status = JOB_STATUS_MAPPINGS.get(raw_status, "active")

    # Parse salary
    salary_min = _parse_int(mapped.get("salary_min"))
    salary_max = _parse_int(mapped.get("salary_max"))
    if not salary_min and not salary_max and mapped.get("salary"):
        salary_min, salary_max = _parse_salary_range(mapped["salary"])

    job = RecruiterJob(
        recruiter_profile_id=recruiter_profile_id,
        title=title,
        description=mapped.get("description") or f"Imported from {platform}: {title}",
        requirements=mapped.get("requirements") or mapped.get("skills"),
        client_company_name=company or None,
        location=location or None,
        employment_type=mapped.get("employment_type"),
        salary_min=salary_min,
        salary_max=salary_max,
        status=status,
    )
    db.add(job)
    db.flush()

    _record_entity(
        migration_job_id,
        "job",
        source_id,
        "recruiter_job",
        job.id,
        raw,
        "imported",
        db,
    )
    return "imported"


def _import_pipeline_candidate(
    migration_job_id: int,
    recruiter_profile_id: int,
    platform: str,
    source_id: str,
    mapped: dict,
    raw: dict,
    db: Session,
) -> str:
    """Import a candidate row → RecruiterPipelineCandidate."""
    email = (mapped.get("email") or "").strip().lower()
    name = _build_name(mapped)

    if not email and not name:
        _record_entity(
            migration_job_id,
            "candidate",
            source_id,
            "recruiter_pipeline_candidate",
            None,
            raw,
            "skipped",
            db,
        )
        return "skipped"

    # Dedup by email scoped to recruiter
    existing = None
    if email:
        existing = db.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
                func.lower(RecruiterPipelineCandidate.external_email) == email,
            )
        ).scalar_one_or_none()

    if existing:
        # Merge empty fields
        if name and not existing.external_name:
            existing.external_name = name
        if mapped.get("phone") and not existing.external_phone:
            existing.external_phone = mapped["phone"]
        if mapped.get("linkedin_url") and not existing.external_linkedin:
            existing.external_linkedin = mapped["linkedin_url"]

        # Append new tags
        new_tags = _parse_tags(mapped.get("tags"))
        if new_tags:
            current = existing.tags or []
            merged = list(set(current) | set(new_tags))
            existing.tags = merged

        _record_entity(
            migration_job_id,
            "candidate",
            source_id,
            "recruiter_pipeline_candidate",
            existing.id,
            raw,
            "merged",
            db,
        )
        return "merged"

    # Map stage from platform-specific status
    raw_status = mapped.get("status", "")
    platform_stages = STAGE_MAPPINGS.get(platform, {})
    stage = platform_stages.get(raw_status, "sourced")

    tags = _parse_tags(mapped.get("tags"))
    source = mapped.get("source") or f"migration_{platform}"

    pc = RecruiterPipelineCandidate(
        recruiter_profile_id=recruiter_profile_id,
        external_name=name or None,
        external_email=email or None,
        external_phone=mapped.get("phone"),
        external_linkedin=mapped.get("linkedin_url"),
        source=source,
        stage=stage,
        tags=tags or None,
    )
    db.add(pc)
    db.flush()

    # Store parent reference for job linkage
    parent_id = mapped.get("company_source_id") or mapped.get("candidate_source_id")

    _record_entity(
        migration_job_id,
        "candidate",
        source_id,
        "recruiter_pipeline_candidate",
        pc.id,
        raw,
        "imported",
        db,
    )

    # If there's a parent reference, update the entity map
    if parent_id:
        entity = db.execute(
            select(MigrationEntityMap).where(
                MigrationEntityMap.migration_job_id == migration_job_id,
                MigrationEntityMap.source_entity_id == str(source_id),
                MigrationEntityMap.source_entity_type == "candidate",
            )
        ).scalar_one_or_none()
        if entity:
            entity.parent_source_id = str(parent_id)

    return "imported"


def _import_placement(
    migration_job_id: int,
    recruiter_profile_id: int,
    platform: str,
    source_id: str,
    mapped: dict,
    raw: dict,
    db: Session,
) -> str:
    """Import a placement row — updates existing pipeline candidate to 'placed'."""
    # Try to find the candidate by email or name
    email = (mapped.get("email") or "").strip().lower()
    name = _build_name(mapped)

    pc = None
    if email:
        pc = db.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
                func.lower(RecruiterPipelineCandidate.external_email) == email,
            )
        ).scalar_one_or_none()

    if not pc and name:
        pc = db.execute(
            select(RecruiterPipelineCandidate).where(
                RecruiterPipelineCandidate.recruiter_profile_id == recruiter_profile_id,
                func.lower(RecruiterPipelineCandidate.external_name) == name.lower(),
            )
        ).scalar_one_or_none()

    if pc:
        pc.stage = "placed"
        _record_entity(
            migration_job_id,
            "placement",
            source_id,
            "recruiter_pipeline_candidate",
            pc.id,
            raw,
            "merged",
            db,
        )
        return "merged"

    # No existing candidate — create one with stage=placed
    pc = RecruiterPipelineCandidate(
        recruiter_profile_id=recruiter_profile_id,
        external_name=name or None,
        external_email=email or None,
        external_phone=mapped.get("phone"),
        source=f"migration_{platform}",
        stage="placed",
    )
    db.add(pc)
    db.flush()

    _record_entity(
        migration_job_id,
        "placement",
        source_id,
        "recruiter_pipeline_candidate",
        pc.id,
        raw,
        "imported",
        db,
    )
    return "imported"


# ---------------------------------------------------------------------------
# Relationship resolution
# ---------------------------------------------------------------------------


def _resolve_recruiter_relationships(
    migration_job_id: int,
    recruiter_profile_id: int,
    db: Session,
) -> None:
    """Post-import: link jobs to clients, candidates to jobs."""
    # Phase 1: Link RecruiterJob → RecruiterClient by company name
    jobs = (
        db.execute(
            select(RecruiterJob).where(
                RecruiterJob.recruiter_profile_id == recruiter_profile_id,
                RecruiterJob.client_company_name.isnot(None),
                RecruiterJob.client_id.is_(None),
            )
        )
        .scalars()
        .all()
    )
    for job in jobs:
        client = db.execute(
            select(RecruiterClient).where(
                RecruiterClient.recruiter_profile_id == recruiter_profile_id,
                func.lower(RecruiterClient.company_name)
                == func.lower(job.client_company_name),
            )
        ).scalar_one_or_none()
        if client:
            job.client_id = client.id

    # Phase 2: Link pipeline candidates → jobs via MigrationEntityMap
    candidate_maps = (
        db.execute(
            select(MigrationEntityMap).where(
                MigrationEntityMap.migration_job_id == migration_job_id,
                MigrationEntityMap.source_entity_type == "candidate",
                MigrationEntityMap.parent_source_id.isnot(None),
            )
        )
        .scalars()
        .all()
    )
    for cmap in candidate_maps:
        parent = db.execute(
            select(MigrationEntityMap).where(
                MigrationEntityMap.migration_job_id == migration_job_id,
                MigrationEntityMap.source_entity_id == cmap.parent_source_id,
                MigrationEntityMap.winnow_entity_type == "recruiter_job",
            )
        ).scalar_one_or_none()
        if parent and parent.winnow_entity_id and cmap.winnow_entity_id:
            pc = db.get(RecruiterPipelineCandidate, cmap.winnow_entity_id)
            if pc:
                pc.recruiter_job_id = parent.winnow_entity_id

    db.commit()


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback_recruiter_migration(migration_job_id: int, db: Session) -> dict:
    """Delete all recruiter entities created by a migration job."""
    job = db.execute(
        select(MigrationJob).where(MigrationJob.id == migration_job_id)
    ).scalar_one_or_none()
    if not job:
        raise ValueError("Migration job not found")

    mappings = (
        db.execute(
            select(MigrationEntityMap).where(
                MigrationEntityMap.migration_job_id == migration_job_id,
                MigrationEntityMap.winnow_entity_id.isnot(None),
                MigrationEntityMap.status.in_(["imported"]),
            )
        )
        .scalars()
        .all()
    )

    deleted = {
        "recruiter_pipeline_candidate": 0,
        "recruiter_job": 0,
        "recruiter_client": 0,
    }

    # Delete in reverse FK order
    for winnow_type, model_cls in [
        ("recruiter_pipeline_candidate", RecruiterPipelineCandidate),
        ("recruiter_job", RecruiterJob),
        ("recruiter_client", RecruiterClient),
    ]:
        for m in mappings:
            if m.winnow_entity_type == winnow_type:
                entity = db.get(model_cls, m.winnow_entity_id)
                if entity:
                    db.delete(entity)
                    deleted[winnow_type] += 1

    # Delete entity map records
    map_count = (
        db.query(MigrationEntityMap)
        .filter(MigrationEntityMap.migration_job_id == migration_job_id)
        .delete()
    )

    job.status = "rolled_back"
    job.updated_at = datetime.now(UTC)
    db.commit()

    return {
        "job_id": migration_job_id,
        "entity_maps_deleted": map_count,
        "deleted": deleted,
        "status": "rolled_back",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_name(mapped: dict) -> str:
    """Build full name from first_name + last_name."""
    parts = [mapped.get("first_name", ""), mapped.get("last_name", "")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def _parse_tags(raw_tags: str | list | None) -> list[str] | None:
    """Parse tags from string or list."""
    if not raw_tags:
        return None
    if isinstance(raw_tags, list):
        return [str(t).strip() for t in raw_tags if str(t).strip()]
    if isinstance(raw_tags, str):
        return [t.strip() for t in raw_tags.split(",") if t.strip()]
    return None


def _parse_int(val: str | int | None) -> int | None:
    """Safely parse an integer from string."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        cleaned = val.replace(",", "").replace("$", "").strip()
        return int(float(cleaned)) if cleaned else None
    except (ValueError, TypeError):
        return None


def _parse_salary_range(salary_str: str) -> tuple[int | None, int | None]:
    """Parse salary range from strings like '$80,000-$100,000'."""
    if not salary_str:
        return None, None
    cleaned = salary_str.replace("$", "").replace(",", "").strip()
    parts = cleaned.split("-")
    if len(parts) == 2:
        return _parse_int(parts[0]), _parse_int(parts[1])
    single = _parse_int(cleaned)
    return single, None


def _log_migration_activity(
    db: Session,
    recruiter_profile_id: int,
    activity_type: str,
    subject: str,
    metadata: dict | None = None,
) -> None:
    """Log a migration activity to the recruiter activity trail."""
    activity = RecruiterActivity(
        recruiter_profile_id=recruiter_profile_id,
        activity_type=activity_type,
        subject=subject,
        activity_metadata=metadata,
    )
    db.add(activity)
