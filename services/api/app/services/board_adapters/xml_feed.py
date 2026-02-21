"""Universal XML feed adapter — HR-XML compatible job feed generation."""

import logging
import uuid
from xml.etree.ElementTree import Element, SubElement, tostring

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob
from app.services.board_adapters.base import BoardAdapter

logger = logging.getLogger(__name__)


class XmlFeedAdapter(BoardAdapter):
    """Adapter that generates HR-XML compatible job feeds.

    This is the universal fallback for boards that ingest XML feeds
    rather than offering a direct push API.
    """

    board_type = "custom"

    def format_job(self, job: EmployerJob) -> dict:
        """Build an HR-XML compatible job element as a dict."""
        xml_data = {
            "referencenumber": str(job.id),
            "title": job.title,
            "description": _cdata_safe(job.description or ""),
            "requirements": _cdata_safe(job.requirements or ""),
            "city": "",
            "state": "",
            "country": "",
            "postalcode": "",
            "salary_min": str(job.salary_min or ""),
            "salary_max": str(job.salary_max or ""),
            "salary_currency": job.salary_currency or "USD",
            "employment_type": job.employment_type or "",
            "category": job.job_category or "",
            "url": job.application_url or "",
            "company": "",  # Filled by distribution service
            "date": (job.posted_at.strftime("%Y-%m-%d") if job.posted_at else ""),
            "expiration_date": (job.close_date.isoformat() if job.close_date else ""),
        }

        # Parse location into city/state if possible
        if job.location:
            parts = [p.strip() for p in job.location.split(",")]
            if len(parts) >= 2:
                xml_data["city"] = parts[0]
                xml_data["state"] = parts[1]
            else:
                xml_data["city"] = parts[0]

        return xml_data

    def generate_xml(self, jobs_data: list[dict]) -> str:
        """Generate a complete HR-XML feed document from multiple jobs."""
        root = Element("source")
        SubElement(root, "publisher").text = "Winnow"
        SubElement(root, "publisherurl").text = "https://winnowcc.ai"

        for data in jobs_data:
            job_el = SubElement(root, "job")
            for key, value in data.items():
                el = SubElement(job_el, key)
                el.text = str(value)

        return tostring(root, encoding="unicode", xml_declaration=True)

    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Validate feed URL is configured."""
        logger.info(
            "Validating XML feed connection %s (feed_url=%s)",
            connection.id,
            connection.feed_url,
        )
        return bool(connection.feed_url)

    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Add job to the XML feed."""
        payload = self.format_job(job)
        # TODO: Replace with real feed upload — POST XML to feed_url or
        # regenerate hosted feed file and upload to S3/CDN
        logger.info("Adding job %s to XML feed (connection %s)", job.id, connection.id)
        external_id = f"xml-{uuid.uuid4().hex[:12]}"
        return {"external_id": external_id, "status": "live", "payload": payload}

    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update job in the XML feed."""
        payload = self.format_job(job)
        # TODO: Regenerate feed with updated job data
        logger.info("Updating XML feed for distribution %s", distribution.id)
        return {"status": "live", "payload": payload}

    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove job from the XML feed."""
        # TODO: Regenerate feed without this job
        logger.info("Removing job from XML feed for distribution %s", distribution.id)
        return True

    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """XML feeds don't provide direct metrics."""
        logger.info(
            "XML feed metrics not available for distribution %s",
            distribution.id,
        )
        return {
            "impressions": distribution.impressions,
            "clicks": distribution.clicks,
            "applications": distribution.applications,
            "cost_spent": float(distribution.cost_spent),
        }


def _cdata_safe(text: str) -> str:
    """Escape XML-unsafe characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
