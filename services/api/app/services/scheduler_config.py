"""Configuration loader for scheduler settings from environment variables."""

import os


def get_scheduler_enabled() -> bool:
    """Check if scheduler is enabled."""
    return os.getenv("SCHEDULER_ENABLED", "false").lower() in ("true", "1", "yes")


def get_scheduler_ingest_cron() -> str:
    """Get cron expression for job ingestion schedule.

    Default: "0 6 * * 0" = Sunday at 6am UTC
    """
    return os.getenv("SCHEDULER_INGEST_CRON", "0 6 * * 0")


def get_scheduler_default_search() -> str:
    """Get default search query for scheduled ingestion."""
    return os.getenv("SCHEDULER_DEFAULT_SEARCH", "")


def get_scheduler_default_location() -> str:
    """Get default location for scheduled ingestion."""
    return os.getenv("SCHEDULER_DEFAULT_LOCATION", "")


def get_scheduler_config() -> dict:
    """Get all scheduler configuration as a dictionary."""
    return {
        "enabled": get_scheduler_enabled(),
        "ingest_cron": get_scheduler_ingest_cron(),
        "default_search": get_scheduler_default_search(),
        "default_location": get_scheduler_default_location(),
    }
