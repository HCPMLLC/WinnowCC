"""Session management endpoints — list, revoke, revoke-all."""

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.session import UserSession
from app.models.user import User
from app.services.auth import (
    COOKIE_NAME,
    _hash_jti,
    decode_token,
    get_current_user,
    revoke_all_sessions,
)

router = APIRouter(prefix="/api/auth/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: int
    device_info: str | None
    ip_address: str | None
    created_at: str
    last_active_at: str | None
    is_current: bool


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    rm_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> list[SessionResponse]:
    """List all active sessions for the current user."""
    now = datetime.now(UTC)
    rows = (
        session.execute(
            select(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Determine current session's token_hash
    current_hash = None
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif rm_session:
        token = rm_session
    if token:
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                current_hash = _hash_jti(jti)
        except Exception:
            pass

    return [
        SessionResponse(
            id=r.id,
            device_info=r.device_info,
            ip_address=r.ip_address,
            created_at=r.created_at.isoformat() if r.created_at else "",
            last_active_at=r.last_active_at.isoformat() if r.last_active_at else None,
            is_current=(r.token_hash == current_hash) if current_hash else False,
        )
        for r in rows
    ]


@router.delete("/{session_id}")
def revoke_single_session(
    session_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Revoke a specific session (must belong to current user)."""
    sess = session.execute(
        select(UserSession).where(
            UserSession.id == session_id, UserSession.user_id == user.id
        )
    ).scalar_one_or_none()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if sess.revoked_at:
        return {"status": "already_revoked"}

    sess.revoked_at = datetime.now(UTC)
    sess.revoke_reason = "user_revoked"
    session.commit()

    # Invalidate Redis cache
    from app.services.auth import _get_redis

    redis = _get_redis()
    if redis:
        try:
            redis.delete(f"session:{sess.token_hash}")
        except Exception:
            pass

    return {"status": "revoked"}


@router.delete("")
def revoke_all_other_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    rm_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> dict:
    """Revoke all sessions except the current one."""
    # Find current JTI
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif rm_session:
        token = rm_session

    current_jti = None
    if token:
        try:
            payload = decode_token(token)
            current_jti = payload.get("jti")
        except Exception:
            pass

    count = revoke_all_sessions(
        session,
        user_id=user.id,
        except_jti=current_jti,
        reason="user_revoked_all",
    )
    return {"status": "ok", "revoked_count": count}
