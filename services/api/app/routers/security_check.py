"""
Security posture check endpoint (admin-only).
Reports on security configuration of the running instance.
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Query

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
