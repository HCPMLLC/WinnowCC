"""
Middleware to set Sentry user context on each request.
Allows Sentry to group errors by user and show which users are affected.
"""

import os

import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SentryUserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
        token = request.cookies.get(cookie_name)

        if token:
            try:
                from app.services.auth import decode_token

                payload = decode_token(token)
                user_id = payload.get("sub") or payload.get("user_id")
                if user_id:
                    sentry_sdk.set_user({"id": str(user_id)})
            except Exception:
                pass

        try:
            response = await call_next(request)
        except Exception:
            from starlette.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        sentry_sdk.set_user(None)

        return response
