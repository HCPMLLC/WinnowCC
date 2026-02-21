"""State government portal adapter — configurable template-based adapter."""

import logging
import uuid

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob
from app.services.board_adapters.base import BoardAdapter

logger = logging.getLogger(__name__)


class StatePortalAdapter(BoardAdapter):
    """Configurable adapter for state government job portals.

    Supports common state portal patterns (NeoGov-based systems).
    Employer provides the portal's submission URL and field mappings
    via the board connection config.
    """

    board_type = "state_portal"

    def format_job(self, job: EmployerJob) -> dict:
        """Format job for a state government portal."""
        location = job.location or "See posting"
        salary_text = ""
        if job.salary_min and job.salary_max:
            currency = job.salary_currency or "USD"
            salary_text = f"{currency} {job.salary_min:,} - {job.salary_max:,} per year"

        return {
            "title": job.title or "",
            "description": job.description or "",
            "minimum_qualifications": job.requirements or "",
            "salary_range": salary_text,
            "location": location,
            "employment_type": job.employment_type or "full_time",
            "department": "",  # Filled from config
            "job_class": "",  # Filled from config
            "filing_deadline": (job.close_date.isoformat() if job.close_date else ""),
            "contact_info": "",  # Filled from config
            "application_url": job.application_url or "",
        }

    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Validate state portal configuration.

        State portals typically don't have API auth — they use
        form-based submission or XML feed ingestion.
        """
        config = connection.config or {}
        portal_url = config.get("portal_url")
        portal_type = config.get("portal_type", "generic")

        if not portal_url:
            return False

        # Validate the portal URL is reachable
        # TODO: Replace with real HTTP check
        logger.info(
            "State portal validation (stubbed) for %s (%s)",
            portal_url,
            portal_type,
        )
        return True

    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Submit a job to a state portal."""
        formatted = self.format_job(job)
        config = connection.config or {}
        portal_type = config.get("portal_type", "generic")

        # Apply portal-specific field mappings
        field_mappings = config.get("field_mappings", {})
        for target_field, source_field in field_mappings.items():
            if source_field in formatted:
                formatted[target_field] = formatted[source_field]

        external_id = f"state-{uuid.uuid4().hex[:12]}"

        # TODO: Replace with real submission
        # For NeoGov: POST to their API endpoint
        # For generic: generate structured XML/PDF for manual upload
        logger.info(
            "Submitted job %s to state portal %s (stubbed)",
            job.id,
            portal_type,
        )

        return {
            "external_id": external_id,
            "status": "pending",
            "payload": formatted,
        }

    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update a job on a state portal."""
        formatted = self.format_job(job)

        # TODO: Replace with real API call
        logger.info(
            "Updated job %s on state portal (stubbed)",
            distribution.external_job_id,
        )

        return {"status": "updated", "payload": formatted}

    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove a job from a state portal."""
        # TODO: Replace with real API call
        logger.info(
            "Removed job %s from state portal (stubbed)",
            distribution.external_job_id,
        )
        return True

    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Fetch metrics from a state portal.

        Most state portals don't provide per-posting metrics.
        """
        return {
            "impressions": 0,
            "clicks": 0,
            "applications": 0,
        }
