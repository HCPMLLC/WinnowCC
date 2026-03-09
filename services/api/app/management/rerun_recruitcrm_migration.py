"""Rollback and re-run Recruit CRM migration (data + attachments).

Usage:
    python -m app.management.rerun_recruitcrm_migration

This script:
1. Finds the completed recruitcrm data and attachments migration jobs
2. Rolls back attachments first (deletes candidate profiles, resume docs)
3. Rolls back data second (deletes pipeline candidates, jobs, clients)
4. Resets both jobs to "pending" so they can be re-started
5. Re-runs the data import (synchronous)
6. Re-runs the attachments import (queued to worker)

Requires: DB_URL environment variable.
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate_profile import CandidateProfile
from app.models.migration import MigrationJob
from app.models.recruiter_pipeline_candidate import RecruiterPipelineCandidate
from app.models.resume_document import ResumeDocument
from app.models.upload_batch import UploadBatch, UploadBatchFile


def main() -> None:
    session = get_session_factory()()

    # ---------------------------------------------------------------
    # 1. Find migration jobs
    # ---------------------------------------------------------------
    all_jobs = (
        session.execute(
            select(MigrationJob).order_by(MigrationJob.created_at.desc())
        )
        .scalars()
        .all()
    )

    data_job = None
    attach_job = None
    for j in all_jobs:
        if j.source_platform_detected == "recruitcrm" and j.status in (
            "completed",
            "rolled_back",
        ):
            if data_job is None:
                data_job = j
        if j.source_platform_detected == "recruitcrm_attachments" and j.status in (
            "completed",
            "rolled_back",
        ):
            if attach_job is None:
                attach_job = j

    if not data_job:
        print("ERROR: No completed recruitcrm data migration found.")
        sys.exit(1)

    print(f"Data migration:        job #{data_job.id}  status={data_job.status}")
    if attach_job:
        print(
            f"Attachments migration: job #{attach_job.id}"
            f"  status={attach_job.status}"
        )
    else:
        print("Attachments migration: not found (will skip)")

    # ---------------------------------------------------------------
    # 2. Rollback attachments (if exists)
    # ---------------------------------------------------------------
    if attach_job and attach_job.status != "rolled_back":
        print("\n--- Rolling back attachments migration ---")
        batch_id = (attach_job.stats_json or {}).get("batch_id")

        profiles_deleted = 0
        resumes_deleted = 0

        if batch_id:
            # Find all batch files and their created profiles/resumes
            batch_files = (
                session.execute(
                    select(UploadBatchFile).where(
                        UploadBatchFile.batch_id == batch_id,
                    )
                )
                .scalars()
                .all()
            )

            for bf in batch_files:
                try:
                    import json

                    result = json.loads(bf.result_json or "{}")
                    cp_id = result.get("candidate_profile_id")
                    rd_id = result.get("resume_document_id")

                    if cp_id:
                        cp = session.get(CandidateProfile, cp_id)
                        if cp:
                            # Unlink from pipeline candidate first
                            linked_pcs = (
                                session.execute(
                                    select(RecruiterPipelineCandidate).where(
                                        RecruiterPipelineCandidate.candidate_profile_id
                                        == cp_id,
                                    )
                                )
                                .scalars()
                                .all()
                            )
                            for pc in linked_pcs:
                                pc.candidate_profile_id = None
                                pc.bulk_attach_batch_id = None
                                pc.bulk_attach_status = None
                                pc.bulk_attach_matched_by = None
                                pc.external_resume_url = None
                            session.delete(cp)
                            profiles_deleted += 1

                    if rd_id:
                        rd = session.get(ResumeDocument, rd_id)
                        if rd:
                            session.delete(rd)
                            resumes_deleted += 1
                except Exception as e:
                    print(f"  Warning: error processing batch file {bf.id}: {e}")

            # Delete batch files and batch
            session.query(UploadBatchFile).filter(
                UploadBatchFile.batch_id == batch_id
            ).delete()
            session.query(UploadBatch).filter(
                UploadBatch.batch_id == batch_id
            ).delete()

        attach_job.status = "rolled_back"
        attach_job.updated_at = datetime.now(UTC)
        session.commit()

        print(f"  Deleted {profiles_deleted} candidate profiles")
        print(f"  Deleted {resumes_deleted} resume documents")
        print("  Attachments rollback complete.")

    # ---------------------------------------------------------------
    # 3. Rollback data migration
    # ---------------------------------------------------------------
    if data_job.status != "rolled_back":
        print("\n--- Rolling back data migration ---")
        from app.services.migration.recruiter_import_engine import (
            rollback_recruiter_migration,
        )

        result = rollback_recruiter_migration(data_job.id, session)
        print(f"  Deleted: {result['deleted']}")
        print(f"  Entity maps deleted: {result['entity_maps_deleted']}")
        print("  Data rollback complete.")

    # ---------------------------------------------------------------
    # 4. Reset jobs to pending
    # ---------------------------------------------------------------
    print("\n--- Resetting jobs to pending ---")
    data_job.status = "pending"
    data_job.started_at = None
    data_job.completed_at = None
    data_job.stats_json = None
    data_job.error_log = None
    data_job.updated_at = datetime.now(UTC)

    if attach_job:
        attach_job.status = "pending"
        attach_job.started_at = None
        attach_job.completed_at = None
        attach_job.stats_json = None
        attach_job.error_log = None
        attach_job.updated_at = datetime.now(UTC)

    session.commit()
    print(f"  Data job #{data_job.id} -> pending")
    if attach_job:
        print(f"  Attachments job #{attach_job.id} -> pending")

    # ---------------------------------------------------------------
    # 5. Re-run data import
    # ---------------------------------------------------------------
    print("\n--- Re-running data import ---")
    from app.services.migration.recruitcrm_orchestrator import (
        run_recruitcrm_zip_migration,
    )

    result = run_recruitcrm_zip_migration(data_job.id, session)
    print(f"  Status: {result['status']}")
    print(f"  Stats: {result.get('stats', {})}")

    if result["status"] != "completed":
        print(
            "ERROR: Data import did not complete. "
            "Fix errors before continuing."
        )
        sys.exit(1)

    # ---------------------------------------------------------------
    # 6. Re-run attachments import (queued to worker)
    # ---------------------------------------------------------------
    if attach_job:
        print("\n--- Queuing attachments import ---")
        # The attachments import needs to be started via the orchestrator
        # which stages files and enqueues worker jobs
        from app.services.migration.recruitcrm_orchestrator import (
            stage_attachments_job,
        )

        attach_job.status = "importing"
        attach_job.started_at = datetime.now(UTC)
        attach_job.config_json = {
            **(attach_job.config_json or {}),
            "csv_migration_job_id": data_job.id,
        }
        session.commit()

        try:
            stage_attachments_job(attach_job.id)
            print("  Attachments staged and queued for processing.")
            print("  Resume parsing will run in the background via workers.")
        except Exception as e:
            print(f"  ERROR staging attachments: {e}")
            print("  You can retry by starting the attachments job from the UI.")

    print("\n=== Migration re-run complete ===")
    session.close()


if __name__ == "__main__":
    main()
