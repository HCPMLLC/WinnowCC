"""
Security headers middleware.
Adds standard security headers to every response.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            import logging
            import traceback

            logging.getLogger("winnow.middleware").error(
                "Unhandled in SecurityHeaders: %s",
                traceback.format_exc(),
            )
            from starlette.responses import JSONResponse

            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy — don't leak URLs
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — restrict browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), interest-cohort=()"
        )

        # Strict Transport Security (only in production over HTTPS)
        # Cloud Run always terminates TLS, so this is safe
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Cache control for API responses — no caching of user data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, private"
            )
            response.headers["Pragma"] = "no-cache"

        return response
