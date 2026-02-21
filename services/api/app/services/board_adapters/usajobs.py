"""USAJobs board adapter."""

import logging
import uuid

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob
from app.services.board_adapters.base import BoardAdapter
from app.services.gs_mapper import format_gs_posting, map_salary_to_gs_grade

logger = logging.getLogger(__name__)


class USAJobsAdapter(BoardAdapter):
    """Adapter for USAJobs API (developer.usajobs.gov)."""

    board_type = "usajobs"

    def format_job(self, job: EmployerJob) -> dict:
        """Format job for USAJobs API submission."""
        gs_info = map_salary_to_gs_grade(
            salary_min=job.salary_min or 0,
            salary_max=job.salary_max or 0,
            location=job.location,
        )

        posting = format_gs_posting(
            title=job.title or "",
            gs_grade_info=gs_info,
            description=job.description or "",
            requirements=job.requirements,
        )

        location = job.location or "Multiple Locations"
        remote_tag = ""
        if job.remote_policy == "remote":
            remote_tag = "Yes"
        elif job.remote_policy == "hybrid":
            remote_tag = "Partial"

        return {
            **posting,
            "duty_location": location,
            "telework_eligible": remote_tag,
            "travel_required": "Occasional Travel",
            "announcement_number": f"WN-{job.id}-{uuid.uuid4().hex[:6]}",
            "gs_grade_info": gs_info,
        }

    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Validate USAJobs API credentials.

        USAJobs requires API key + User-Agent email.
        """
        api_key = connection.api_key_encrypted
        config = connection.config or {}
        email = config.get("user_agent_email")

        if not api_key or not email:
            return False

        # TODO: Replace with real API validation call
        # url = "https://data.usajobs.gov/api/search"
        # headers = {
        #     "Authorization-Key": api_key,
        #     "User-Agent": email,
        # }
        # response = requests.get(url, headers=headers, params={"Keyword": "test"})
        # return response.status_code == 200

        logger.info("USAJobs credential validation (stubbed)")
        return True

    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Submit a job to USAJobs."""
        formatted = self.format_job(job)

        # TODO: Replace with real USAJobs API call
        # USAJobs posting typically requires going through
        # USA Staffing or USAJOBS Recruiter.
        external_id = f"usajobs-{uuid.uuid4().hex[:12]}"

        logger.info(
            "Submitted job %s to USAJobs (stubbed): %s",
            job.id,
            formatted.get("position_title"),
        )

        return {
            "external_id": external_id,
            "status": "pending",
            "payload": formatted,
        }

    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update a job on USAJobs."""
        formatted = self.format_job(job)

        # TODO: Replace with real API call
        logger.info(
            "Updated job %s on USAJobs (stubbed)",
            distribution.external_job_id,
        )

        return {"status": "updated", "payload": formatted}

    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove a job from USAJobs."""
        # TODO: Replace with real API call
        logger.info(
            "Removed job %s from USAJobs (stubbed)",
            distribution.external_job_id,
        )
        return True

    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Fetch metrics from USAJobs."""
        # TODO: USAJobs does not natively provide per-posting metrics
        # via API. This would need to integrate with USA Staffing reports.
        return {
            "impressions": 0,
            "clicks": 0,
            "applications": 0,
        }
