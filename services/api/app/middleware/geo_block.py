"""Geo-blocking middleware — blocks requests from configured countries."""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Paths that skip geo-blocking (auth, health, readiness)
_SKIP_PREFIXES = ("/api/auth/", "/health", "/ready")


class GeoBlockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Only active when GEO_BLOCK_COUNTRIES is set
        if not os.getenv("GEO_BLOCK_COUNTRIES", "").strip():
            return await call_next(request)

        # Skip certain paths
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        from app.services.ip_protection import check_geo_allowed, get_client_ip

        ip = get_client_ip(request)
        if not check_geo_allowed(ip):
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied from your region."},
            )

        return await call_next(request)
