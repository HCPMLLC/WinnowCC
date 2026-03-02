"""Abuse detection service — account lockout and IP blocking."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth_event import AuthEvent
from app.models.user import User

logger = logging.getLogger(__name__)

# Thresholds
ACCOUNT_LOCKOUT_THRESHOLD = 10  # failed attempts before lockout
ACCOUNT_LOCKOUT_WINDOW_MINUTES = 30  # rolling window for counting failures
ACCOUNT_LOCKOUT_DURATION_MINUTES = 30  # how long the lockout lasts
IP_BLOCK_THRESHOLD = 50  # failed attempts per IP before blocking
IP_BLOCK_WINDOW_MINUTES = 30


def record_auth_event(
    db_session: Session,
    *,
    event_type: str,
    email: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """Insert an auth_events row."""
    event = AuthEvent(
        user_id=user_id,
        email=email,
        event_type=event_type,
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
        failure_reason=failure_reason,
    )
    db_session.add(event)
    db_session.flush()


def check_account_locked(
    user: User,
) -> tuple[bool, str | None, int | None]:
    """Check if account is locked. Returns (is_locked, reason, minutes_remaining).

    Auto-unlocks after ACCOUNT_LOCKOUT_DURATION_MINUTES.
    """
    if not user.account_locked_at:
        return False, None, None

    elapsed = datetime.now(UTC) - user.account_locked_at
    remaining = ACCOUNT_LOCKOUT_DURATION_MINUTES - int(elapsed.total_seconds() / 60)

    if remaining <= 0:
        # Auto-unlock
        return False, None, None

    return True, user.account_lock_reason, remaining


def check_ip_blocked(
    db_session: Session, *, ip_address: str
) -> bool:
    """Return True if the IP has exceeded failure threshold."""
    if not ip_address:
        return False

    cutoff = datetime.now(UTC) - timedelta(minutes=IP_BLOCK_WINDOW_MINUTES)
    count = db_session.execute(
        select(func.count(AuthEvent.id)).where(
            AuthEvent.ip_address == ip_address,
            AuthEvent.event_type.in_(["login_failed", "otp_failed"]),
            AuthEvent.created_at > cutoff,
        )
    ).scalar_one()

    return count >= IP_BLOCK_THRESHOLD


def handle_login_failure(
    db_session: Session,
    *,
    user: User,
) -> None:
    """Increment failure count and lock if threshold reached."""
    now = datetime.now(UTC)

    # Reset window if it's expired
    if (
        user.failed_login_window_start is None
        or (now - user.failed_login_window_start).total_seconds()
        > ACCOUNT_LOCKOUT_WINDOW_MINUTES * 60
    ):
        user.failed_login_count = 1
        user.failed_login_window_start = now
    else:
        user.failed_login_count = (user.failed_login_count or 0) + 1

    # Check if we need to lock
    if user.failed_login_count >= ACCOUNT_LOCKOUT_THRESHOLD:
        user.account_locked_at = now
        user.account_lock_reason = (
            f"Too many failed login attempts ({user.failed_login_count})"
        )
        logger.warning(
            "Account locked for user %s (%s) after %d failures",
            user.id,
            user.email,
            user.failed_login_count,
        )

    db_session.flush()


def handle_login_success(
    db_session: Session,
    *,
    user: User,
) -> None:
    """Clear failure counters on successful login."""
    if user.failed_login_count or user.account_locked_at:
        user.failed_login_count = 0
        user.failed_login_window_start = None
        user.account_locked_at = None
        user.account_lock_reason = None
        db_session.flush()


def unlock_account(
    db_session: Session,
    *,
    user: User,
) -> None:
    """Manually unlock an account (admin action)."""
    user.account_locked_at = None
    user.account_lock_reason = None
    user.failed_login_count = 0
    user.failed_login_window_start = None
    db_session.commit()


def get_abuse_summary(
    db_session: Session,
    *,
    email: str | None = None,
    ip_address: str | None = None,
    hours: int = 24,
) -> list[dict]:
    """Query auth events for admin view."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    query = select(AuthEvent).where(AuthEvent.created_at > cutoff)

    if email:
        query = query.where(AuthEvent.email == email)
    if ip_address:
        query = query.where(AuthEvent.ip_address == ip_address)

    query = query.order_by(AuthEvent.created_at.desc()).limit(500)
    rows = db_session.execute(query).scalars().all()

    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "email": r.email,
            "event_type": r.event_type,
            "ip_address": r.ip_address,
            "failure_reason": r.failure_reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
