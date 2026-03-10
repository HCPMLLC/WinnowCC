"""Cloud Run worker autoscaler.

Sends concurrent long-held HTTP requests to the worker's /_scale/pressure
endpoint, forcing Cloud Run to spin up additional instances when queue
depth is high.  Combined with --concurrency=1 on the worker service,
each pressure request occupies one instance, causing Cloud Run to scale.
"""

import logging
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from app.services.worker_health import get_queue_stats

logger = logging.getLogger(__name__)

# Tiered mapping: (threshold, pressure_count)
_PRESSURE_TIERS = [
    (1000, 24),
    (200, 16),
    (50, 8),
    (10, 4),
    (1, 2),
]


def _calculate_pressure(total_pending: int) -> int:
    """Return the number of concurrent pressure requests to send."""
    for threshold, count in _PRESSURE_TIERS:
        if total_pending >= threshold:
            return count
    return 0


def _get_id_token(audience: str) -> str | None:
    """Fetch an ID token from the GCP metadata server (Cloud Run only)."""
    if not os.getenv("K_SERVICE"):
        return None
    try:
        meta_url = (
            "http://metadata.google.internal/computeMetadata/v1/"
            f"instance/service-accounts/default/identity?audience={audience}"
        )
        req = urllib.request.Request(meta_url, headers={"Metadata-Flavor": "Google"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode()
    except Exception:
        logger.debug("Failed to get ID token from metadata server", exc_info=True)
        return None


def _send_pressure_request(url: str, token: str | None) -> bool:
    """POST to /_scale/pressure with a 90s timeout. Returns True on success."""
    try:
        pressure_url = f"{url.rstrip('/')}/_scale/pressure"
        req = urllib.request.Request(pressure_url, method="POST", data=b"")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=90):
            pass
        return True
    except Exception:
        logger.debug("Pressure request failed", exc_info=True)
        return False


def scale_worker() -> dict:
    """Check queue depth and send pressure requests to scale the worker.

    Returns a dict with stats about what happened.
    """
    worker_url = os.getenv("WORKER_HEALTH_URL")
    if not worker_url:
        return {"skipped": True, "reason": "WORKER_HEALTH_URL not set"}

    try:
        stats = get_queue_stats()
    except Exception:
        logger.exception("Failed to get queue stats for scaler")
        return {"skipped": True, "reason": "queue_stats_failed"}

    total_pending = stats.get("total_pending", 0)
    pressure_needed = _calculate_pressure(total_pending)

    result = {
        "total_pending": total_pending,
        "pressure_needed": pressure_needed,
        "pressure_sent": 0,
        "pressure_succeeded": 0,
    }

    if pressure_needed == 0:
        return result

    token = _get_id_token(worker_url)

    # Fire N concurrent pressure requests
    with ThreadPoolExecutor(max_workers=pressure_needed) as pool:
        futures = [
            pool.submit(_send_pressure_request, worker_url, token)
            for _ in range(pressure_needed)
        ]
        result["pressure_sent"] = len(futures)
        result["pressure_succeeded"] = sum(1 for f in futures if f.result())

    logger.info(
        "scale_worker: pending=%d pressure_sent=%d succeeded=%d",
        total_pending,
        result["pressure_sent"],
        result["pressure_succeeded"],
    )
    return result
