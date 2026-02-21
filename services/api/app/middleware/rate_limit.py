"""
Rate limiting middleware using slowapi.
Limits are per IP address for unauthenticated endpoints
and per user ID for authenticated endpoints.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_key(request):
    """
    Use user ID from JWT cookie if authenticated, otherwise IP address.
    Falls back to IP for unauthenticated requests (login, signup, webhook).
    """
    cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
    token = request.cookies.get(cookie_name)
    if token:
        try:
            from app.services.auth import decode_token

            payload = decode_token(token)
            user_id = payload.get("sub") or payload.get("user_id")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)


# Disable rate limiting in tests to avoid false 429s
_enabled = os.environ.get("TESTING", "").lower() not in ("1", "true")
limiter = Limiter(key_func=_get_key, enabled=_enabled)
