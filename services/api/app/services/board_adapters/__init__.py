"""Board adapter registry."""

from app.services.board_adapters.base import BoardAdapter
from app.services.board_adapters.google_jobs import GoogleJobsAdapter
from app.services.board_adapters.indeed import IndeedAdapter
from app.services.board_adapters.state_portal import StatePortalAdapter
from app.services.board_adapters.usajobs import USAJobsAdapter
from app.services.board_adapters.xml_feed import XmlFeedAdapter

ADAPTER_REGISTRY: dict[str, type[BoardAdapter]] = {
    "indeed": IndeedAdapter,
    "google_jobs": GoogleJobsAdapter,
    "custom": XmlFeedAdapter,
    "usajobs": USAJobsAdapter,
    "state_portal": StatePortalAdapter,
    # Future adapters:
    # "linkedin": LinkedInAdapter,
    # "ziprecruiter": ZipRecruiterAdapter,
    # "glassdoor": GlassdoorAdapter,
}


def get_adapter(board_type: str) -> BoardAdapter | None:
    """Get an adapter instance for the given board type."""
    adapter_cls = ADAPTER_REGISTRY.get(board_type)
    if adapter_cls is None:
        return None
    return adapter_cls()
