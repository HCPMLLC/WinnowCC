from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.admin_test_email import AdminTestEmail
from app.models.user import User
from app.services.auth import require_admin_user
from app.services.billing import (
    _ENV_ADMIN_TEST_EMAILS,
    ADMIN_TEST_EMAILS,
    reload_admin_test_emails,
)

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class TestEmailEntry(BaseModel):
    email: str
    source: str  # "env" or "db"
    added_by: str | None = None
    created_at: str | None = None


class TestEmailsResponse(BaseModel):
    env_emails: list[str]
    db_emails: list[TestEmailEntry]
    all_emails: list[str]


class AddTestEmailRequest(BaseModel):
    email: EmailStr


class RemoveTestEmailRequest(BaseModel):
    email: EmailStr


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/test-emails", response_model=TestEmailsResponse)
def list_test_emails(
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Return all admin test emails split by source (env vs DB)."""
    db_rows = session.execute(
        select(AdminTestEmail).order_by(AdminTestEmail.created_at.desc())
    ).scalars().all()

    db_entries = [
        TestEmailEntry(
            email=row.email,
            source="db",
            added_by=row.added_by,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in db_rows
    ]

    return TestEmailsResponse(
        env_emails=sorted(_ENV_ADMIN_TEST_EMAILS),
        db_emails=db_entries,
        all_emails=sorted(ADMIN_TEST_EMAILS),
    )


@router.post("/test-emails", response_model=TestEmailsResponse)
def add_test_email(
    body: AddTestEmailRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Add a new dynamic test email (persisted in DB)."""
    email = body.email.strip().lower()

    # Already in env?
    if email in _ENV_ADMIN_TEST_EMAILS:
        raise HTTPException(
            status_code=409,
            detail="Email is already in the server config (env var). No action needed.",
        )

    # Already in DB?
    existing = session.execute(
        select(AdminTestEmail).where(AdminTestEmail.email == email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists.")

    row = AdminTestEmail(email=email, added_by=admin.email or str(admin.id))
    session.add(row)
    session.commit()

    reload_admin_test_emails(session)
    return list_test_emails(session=session, admin=admin)


@router.delete("/test-emails", response_model=TestEmailsResponse)
def remove_test_email(
    body: RemoveTestEmailRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin_user),
):
    """Remove a dynamic test email (DB-managed only)."""
    email = body.email.strip().lower()

    if email in _ENV_ADMIN_TEST_EMAILS:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove env-var emails via the UI. "
            "Edit the server config instead.",
        )

    row = session.execute(
        select(AdminTestEmail).where(AdminTestEmail.email == email)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Email not found.")

    session.delete(row)
    session.commit()

    reload_admin_test_emails(session)
    return list_test_emails(session=session, admin=admin)
