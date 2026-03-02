"""
Security posture check endpoint (admin-only).
Reports on security configuration of the running instance.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.services.auth import require_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/security", tags=["admin-security"])


@router.get("/check")
async def security_check(
    admin_token: str = Query(..., alias="admin_token"),
):
    """
    Check the security posture of the running instance.
    Admin-only. Returns a report of security configuration.
    """
    expected_token = os.environ.get("ADMIN_TOKEN", "")
    if not expected_token or admin_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    env = os.environ.get("ENV", "dev")
    auth_secret = os.environ.get("AUTH_SECRET", "")

    checks = []
    all_pass = True

    # 1. AUTH_SECRET strength
    if len(auth_secret) >= 32 and auth_secret not in ("dev-secret-change-me",):
        checks.append({"check": "AUTH_SECRET strength", "status": "PASS"})
    else:
        checks.append(
            {
                "check": "AUTH_SECRET strength",
                "status": "FAIL",
                "detail": "Secret too short or default value",
            }
        )
        all_pass = False

    # 2. Environment mode
    if env != "dev":
        checks.append(
            {
                "check": "Production mode",
                "status": "PASS",
                "detail": f"ENV={env}",
            }
        )
    else:
        checks.append(
            {
                "check": "Production mode",
                "status": "WARN",
                "detail": "Running in dev mode",
            }
        )

    # 3. CORS origin
    cors_origin = os.environ.get("CORS_ORIGIN", "")
    if cors_origin and "localhost" not in cors_origin:
        checks.append(
            {
                "check": "CORS origin",
                "status": "PASS",
                "detail": cors_origin,
            }
        )
    else:
        checks.append(
            {
                "check": "CORS origin",
                "status": "WARN",
                "detail": "CORS origin not set or is localhost",
            }
        )

    # 4. Stripe keys (live mode)
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if stripe_key.startswith("sk_live_"):
        checks.append({"check": "Stripe live mode", "status": "PASS"})
    elif stripe_key.startswith("sk_test_"):
        checks.append(
            {
                "check": "Stripe live mode",
                "status": "WARN",
                "detail": "Using test mode keys",
            }
        )
    else:
        checks.append(
            {
                "check": "Stripe live mode",
                "status": "SKIP",
                "detail": "No Stripe key configured",
            }
        )

    # 5. Database encryption
    db_url = os.environ.get("DB_URL", "")
    if "cloudsql" in db_url or "cloud" in db_url:
        checks.append(
            {
                "check": "Database encryption at rest",
                "status": "PASS",
                "detail": "Cloud SQL (encrypted by default)",
            }
        )
    else:
        checks.append(
            {
                "check": "Database encryption at rest",
                "status": "WARN",
                "detail": "Local database — no encryption at rest",
            }
        )

    # 6. GCS bucket configured
    gcs_bucket = os.environ.get("GCS_BUCKET", "")
    if gcs_bucket:
        checks.append(
            {
                "check": "GCS bucket",
                "status": "PASS",
                "detail": gcs_bucket,
            }
        )
    else:
        checks.append(
            {
                "check": "GCS bucket",
                "status": "WARN",
                "detail": "Using local file storage",
            }
        )

    return {
        "environment": env,
        "all_pass": all_pass,
        "checks": checks,
    }


@router.get("/auth-events")
def get_auth_events(
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
    email: str | None = Query(None),
    ip: str | None = Query(None),
    hours: int = Query(24, ge=1, le=720),
) -> dict:
    """Query auth event log. Admin only."""
    from app.services.abuse_detection import get_abuse_summary

    events = get_abuse_summary(session, email=email, ip_address=ip, hours=hours)
    return {"events": events, "count": len(events)}


@router.get("/locked-accounts")
def get_locked_accounts(
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
) -> dict:
    """List currently locked accounts. Admin only."""
    locked = (
        session.execute(
            select(User).where(User.account_locked_at.isnot(None))
        )
        .scalars()
        .all()
    )
    return {
        "accounts": [
            {
                "user_id": u.id,
                "email": u.email,
                "locked_at": u.account_locked_at.isoformat()
                if u.account_locked_at
                else None,
                "reason": u.account_lock_reason,
                "failed_count": u.failed_login_count,
            }
            for u in locked
        ]
    }


@router.post("/unlock/{user_id}")
def unlock_account_endpoint(
    user_id: int,
    admin: User = Depends(require_admin_user),
    session: Session = Depends(get_session),
) -> dict:
    """Manually unlock a locked account. Admin only."""
    from app.services.abuse_detection import unlock_account

    user = session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    unlock_account(session, user=user)
    return {"status": "unlocked", "user_id": user_id, "email": user.email}
