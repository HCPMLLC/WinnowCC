"""Google for Jobs adapter — generates JSON-LD JobPosting structured data."""

import json
import logging
import uuid

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob
from app.services.board_adapters.base import BoardAdapter

logger = logging.getLogger(__name__)


class GoogleJobsAdapter(BoardAdapter):
    """Adapter for Google for Jobs via JSON-LD structured data."""

    board_type = "google_jobs"

    def format_job(self, job: EmployerJob) -> dict:
        """Generate schema.org/JobPosting JSON-LD structured data."""
        job_posting = {
            "@context": "https://schema.org/",
            "@type": "JobPosting",
            "title": job.title,
            "description": _html_wrap(job.description or ""),
            "datePosted": (job.posted_at.strftime("%Y-%m-%d") if job.posted_at else ""),
            "employmentType": _map_employment_type(job.employment_type),
            "identifier": {
                "@type": "PropertyValue",
                "name": "Winnow Job ID",
                "value": str(job.id),
            },
            "hiringOrganization": {
                "@type": "Organization",
                "name": "",  # Filled by distribution service
                "sameAs": "",
            },
        }

        # Location
        if job.remote_policy == "remote":
            job_posting["jobLocationType"] = "TELECOMMUTE"
        if job.location:
            job_posting["jobLocation"] = {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": job.location,
                },
            }

        # Salary
        if job.salary_min or job.salary_max:
            salary = {
                "@type": "MonetaryAmount",
                "currency": job.salary_currency or "USD",
                "value": {
                    "@type": "QuantitativeValue",
                    "unitText": "YEAR",
                },
            }
            if job.salary_min and job.salary_max:
                salary["value"]["minValue"] = job.salary_min
                salary["value"]["maxValue"] = job.salary_max
            elif job.salary_min:
                salary["value"]["value"] = job.salary_min
            job_posting["baseSalary"] = salary

        # Valid through
        if job.close_date:
            job_posting["validThrough"] = job.close_date.isoformat()
        elif job.closes_at:
            job_posting["validThrough"] = job.closes_at.strftime("%Y-%m-%d")

        # Application URL
        if job.application_url:
            job_posting["directApply"] = True
            job_posting["applicationContact"] = {
                "@type": "ContactPoint",
                "url": job.application_url,
            }

        return job_posting

    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Google Jobs uses structured data — no API credentials needed."""
        logger.info(
            "Google Jobs validation: structured data mode (connection %s)",
            connection.id,
        )
        return True

    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Generate and store the JSON-LD for embedding on career pages."""
        payload = self.format_job(job)
        json_ld = json.dumps(payload, indent=2)
        # TODO: POST structured data to employer's career page CMS or
        # generate an indexable page hosted by Winnow
        logger.info(
            "Generated Google Jobs JSON-LD for job %s (%d bytes)",
            job.id,
            len(json_ld),
        )
        external_id = f"goog-{uuid.uuid4().hex[:12]}"
        return {"external_id": external_id, "status": "live", "payload": payload}

    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Regenerate JSON-LD with updated job data."""
        payload = self.format_job(job)
        logger.info("Updated Google Jobs JSON-LD for distribution %s", distribution.id)
        return {"status": "live", "payload": payload}

    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove JSON-LD from career page."""
        # TODO: Remove structured data from hosted page or notify CMS
        logger.info(
            "Removing Google Jobs structured data for distribution %s",
            distribution.id,
        )
        return True

    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Google Jobs doesn't expose per-listing metrics directly."""
        # TODO: Integrate with Google Search Console API for impression data
        logger.info(
            "Google Jobs metrics not directly available for distribution %s",
            distribution.id,
        )
        return {
            "impressions": distribution.impressions,
            "clicks": distribution.clicks,
            "applications": distribution.applications,
            "cost_spent": 0,
        }


def _map_employment_type(employment_type: str | None) -> str:
    """Map to schema.org EmploymentType."""
    mapping = {
        "full-time": "FULL_TIME",
        "part-time": "PART_TIME",
        "contract": "CONTRACTOR",
        "internship": "INTERN",
    }
    return mapping.get(employment_type or "", "OTHER")


def _html_wrap(text: str) -> str:
    """Wrap plain text in basic HTML paragraphs for Google indexing."""
    paragraphs = text.strip().split("\n\n")
    return "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
