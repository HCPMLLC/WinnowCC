"""Abstract base class for job board adapters."""

from abc import ABC, abstractmethod

from app.models.distribution import BoardConnection, JobDistribution
from app.models.employer import EmployerJob


class BoardAdapter(ABC):
    """Interface for all job board integrations."""

    board_type: str

    @abstractmethod
    def validate_credentials(self, connection: BoardConnection) -> bool:
        """Test that the stored credentials are valid."""

    @abstractmethod
    def submit_job(self, job: EmployerJob, connection: BoardConnection) -> dict:
        """Push a job to this board.

        Returns: {'external_id': '...', 'status': 'live'|'pending'}
        """

    @abstractmethod
    def update_job(self, job: EmployerJob, distribution: JobDistribution) -> dict:
        """Update an existing job on this board."""

    @abstractmethod
    def remove_job(self, distribution: JobDistribution) -> bool:
        """Remove/unpublish a job from this board."""

    @abstractmethod
    def fetch_metrics(self, distribution: JobDistribution) -> dict:
        """Pull impressions, clicks, applications from the board."""

    @abstractmethod
    def format_job(self, job: EmployerJob) -> dict:
        """Transform job data into this board's required format."""
