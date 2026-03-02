"""IP protection service — admin allowlist, geo-blocking, employer IP allowlist."""

import ipaddress
import logging
import os

from fastapi import Request

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from X-Forwarded-For or request.client.host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def check_admin_ip(ip: str | None) -> bool:
    """Check IP against ADMIN_IP_ALLOWLIST env var (comma-separated CIDRs).

    Returns True if allowed (or if allowlist is empty/unset).
    """
    allowlist_raw = os.getenv("ADMIN_IP_ALLOWLIST", "").strip()
    if not allowlist_raw:
        return True  # No allowlist configured = allow all
    if not ip:
        return False

    try:
        client_ip = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for cidr in allowlist_raw.split(","):
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if client_ip in network:
                return True
        except ValueError:
            logger.warning("Invalid CIDR in ADMIN_IP_ALLOWLIST: %s", cidr)

    return False


def check_geo_allowed(ip: str | None) -> bool:
    """Check if IP's country is in GEO_BLOCK_COUNTRIES.

    Uses ipinfo.io free tier with Redis cache (24h TTL).
    Returns True if allowed (or if GEO_BLOCK_COUNTRIES is not set).
    """
    blocked_raw = os.getenv("GEO_BLOCK_COUNTRIES", "").strip()
    if not blocked_raw or not ip:
        return True

    blocked_countries = {c.strip().upper() for c in blocked_raw.split(",") if c.strip()}
    if not blocked_countries:
        return True

    # Check Redis cache
    redis = _get_redis()
    cache_key = f"geo:{ip}"
    if redis:
        try:
            cached = redis.get(cache_key)
            if cached:
                return cached.upper() not in blocked_countries
        except Exception:
            pass

    # Query ipinfo.io
    try:
        import httpx

        resp = httpx.get(f"https://ipinfo.io/{ip}/country", timeout=3)
        country = resp.text.strip().upper() if resp.status_code == 200 else ""

        # Cache for 24 hours
        if redis and country:
            try:
                redis.setex(cache_key, 86400, country)
            except Exception:
                pass

        if country in blocked_countries:
            logger.info("Geo-blocked IP %s (country=%s)", ip, country)
            return False
    except Exception:
        logger.debug("Geo lookup failed for %s", ip, exc_info=True)

    return True


def check_employer_ip_allowed(
    employer_profile, ip: str | None
) -> bool:
    """Check if IP is in employer's ip_allowlist JSONB.

    Returns True if allowed (or if allowlist is empty/None).
    """
    allowlist = getattr(employer_profile, "ip_allowlist", None)
    if not allowlist or not ip:
        return True

    try:
        client_ip = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for entry in allowlist:
        entry = str(entry).strip()
        if not entry:
            continue
        try:
            network = ipaddress.ip_network(entry, strict=False)
            if client_ip in network:
                return True
        except ValueError:
            pass

    return False


def _get_redis():
    """Get Redis connection, return None if unavailable."""
    try:
        from redis import Redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
    except Exception:
        return None
