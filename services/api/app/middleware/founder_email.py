"""ASGI middleware to propagate the request user's email via ContextVar.

Setting the ContextVar in an async ASGI middleware (rather than in a sync
FastAPI dependency) ensures the value is part of the async context that
gets copied into every ``run_in_threadpool`` call.  This makes the email
visible to all sync billing helpers regardless of call depth.
"""

from __future__ import annotations

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class FounderEmailMiddleware:
    """Extract email from JWT (cookie or Authorization header) and store it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            email = self._extract_email(scope)
            if email:
                from app.services.billing import set_request_user_email

                set_request_user_email(email)

        await self.app(scope, receive, send)

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_email(scope: Scope) -> str:
        """Best-effort email extraction from the JWT — no DB hit."""
        import os

        from jose import jwt as _jwt

        secret = (
            os.getenv("AUTH_JWT_SECRET") or os.getenv("AUTH_SECRET") or ""
        ).strip()
        if not secret:
            return ""

        token = _extract_token(scope)
        if not token:
            return ""

        try:
            payload = _jwt.decode(token, secret, algorithms=["HS256"])
            return (payload.get("email") or "").strip().lower()
        except Exception:
            return ""


def _extract_token(scope: Scope) -> str:
    """Pull the JWT from the Authorization header or the session cookie."""
    import os

    cookie_name = os.getenv("AUTH_COOKIE_NAME", "rm_session").strip()

    headers: dict[bytes, bytes] = dict(scope.get("headers", []))

    # 1. Authorization: Bearer <token>
    auth = headers.get(b"authorization", b"").decode()
    if auth.startswith("Bearer "):
        return auth[7:]

    # 2. Session cookie
    raw_cookie = headers.get(b"cookie", b"").decode()
    if raw_cookie:
        for part in raw_cookie.split(";"):
            part = part.strip()
            if part.startswith(f"{cookie_name}="):
                return part[len(cookie_name) + 1 :]

    return ""
