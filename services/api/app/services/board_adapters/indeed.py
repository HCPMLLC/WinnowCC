"""Indeed job board adapter."""

import logging
import uuid

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob
from app.services.board_adapters.base import BoardAdapter

logger = logging.getLogger(__name__)


class IndeedAdapter(BoardAdapter):
    """Adapter for Indeed Sponsored Jobs API."""

    board_type = "indeed"

    def format_job(self, job: EmployerJob) -> dict:
        """Format job for Indeed's XML Sponsored Jobs specification."""
        salary_text = ""
        if job.salary_min and job.salary_max:
            currency = job.salary_currency or "USD"
            salary_text = f"{currency} {job.salary_min:,}–{job.salary_max:,}/year"
        elif job.salary_min:
            currency = job.salary_currency or "USD"
            salary_text = f"From {currency} {job.salary_min:,}/year"

        location = job.location or "Remote"
        remote_tag = ""
        if job.remote_policy == "remote":
            remote_tag = "TELECOMMUTE"
        elif job.remote_policy == "hybrid":
            remote_tag = "TEMPORARILY_REMOTE"

        return {
            "title": job.title,
            "description": job.description or "",
            "requirements": job.requirements or "",
            "company": "",  # Filled by distribution service from employer profile
            "location": location,
            "salary": salary_text,
            "jobtype": _map_employment_type(job.employment_type),
            "remotetype": remote_tag,
            "url": job.application_url or "",
            "referencenumber": str(job.id),
            "category": job.job_category or "",
        }

    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Validate Indeed API credentials."""
        # TODO: Replace with real API call to Indeed's /auth/validate endpoint
        logger.info("Validating Indeed credentials for connection %s", connection.id)
        return bool(connection.api_key_encrypted)

    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Submit job to Indeed."""
        payload = self.format_job(job)
        # TODO: Replace with real API call — POST to Indeed Sponsored Jobs API
        logger.info(
            "Submitting job %s to Indeed (connection %s)", job.id, connection.id
        )
        external_id = f"indeed-{uuid.uuid4().hex[:12]}"
        return {"external_id": external_id, "status": "pending", "payload": payload}

    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update an existing Indeed posting."""
        payload = self.format_job(job)
        # TODO: Replace with real API call — PUT to Indeed Sponsored Jobs API
        logger.info(
            "Updating Indeed distribution %s (external_id=%s)",
            distribution.id,
            distribution.external_job_id,
        )
        return {"status": "live", "payload": payload}

    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove a job from Indeed."""
        # TODO: Replace with real API call — DELETE to Indeed Sponsored Jobs API
        logger.info(
            "Removing Indeed distribution %s (external_id=%s)",
            distribution.id,
            distribution.external_job_id,
        )
        return True

    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Fetch performance metrics from Indeed."""
        # TODO: Replace with real API call — GET Indeed Analytics API
        logger.info("Fetching Indeed metrics for distribution %s", distribution.id)
        return {
            "impressions": distribution.impressions,
            "clicks": distribution.clicks,
            "applications": distribution.applications,
            "cost_spent": float(distribution.cost_spent),
        }


def _map_employment_type(employment_type: str | None) -> str:
    """Map internal employment type to Indeed's jobtype values."""
    mapping = {
        "full-time": "fulltime",
        "part-time": "parttime",
        "contract": "contract",
        "internship": "internship",
    }
    return mapping.get(employment_type or "", "")
