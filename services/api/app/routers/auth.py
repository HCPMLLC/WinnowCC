from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.services.auth import (
    clear_auth_cookie,
    generate_otp,
    get_current_user,
    hash_password,
    make_token,
    require_admin_user,
    set_auth_cookie,
    verify_otp,
    verify_password,
)
from app.services.email import send_mfa_otp_email, send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

MFA_OTP_TTL_MINUTES = 10
MFA_MAX_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    user_id: int
    email: EmailStr
    onboarding_complete: bool
    is_admin: bool = False
    role: str = "candidate"
    token: str | None = None


class LoginResponse(BaseModel):
    requires_mfa: bool = False
    user_id: int | None = None
    email: str | None = None
    onboarding_complete: bool | None = None
    is_admin: bool | None = None
    role: str | None = None
    token: str | None = None


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp_code: str


class ResendOtpRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_password(password: str) -> None:
    # bcrypt only uses first 72 BYTES; passlib raises to prevent silent truncation
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password is too long for secure hashing. "
                "Use 72 bytes or fewer (roughly <=72 ASCII characters; fewer if using emojis/special characters)."
            ),
        )


def _me_response(user: User) -> MeResponse:
    return MeResponse(
        user_id=user.id,
        email=user.email,
        onboarding_complete=bool(user.onboarding_completed_at),
        is_admin=user.is_admin,
        role=user.role,
    )


def _send_otp_to_user(user: User, session: Session) -> None:
    """Generate an OTP, persist hash + expiry, and email the code."""
    code, otp_hash = generate_otp()
    user.mfa_otp_hash = otp_hash
    user.mfa_otp_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=MFA_OTP_TTL_MINUTES
    )
    user.mfa_otp_attempts = 0
    session.commit()
    try:
        send_mfa_otp_email(user.email, code)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to send MFA OTP email to %s", user.email, exc_info=True,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=MeResponse)
def signup(
    payload: AuthRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> MeResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    existing = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    set_auth_cookie(response, user_id=user.id, email=user.email)
    resp = _me_response(user)
    resp.token = make_token(user_id=user.id, email=user.email)
    return resp


@router.post("/login", response_model=LoginResponse)
def login(
    payload: AuthRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # --- MFA gate ---
    if user.mfa_required:
        _send_otp_to_user(user, session)
        return LoginResponse(requires_mfa=True, email=user.email)

    # No MFA — normal login
    set_auth_cookie(response, user_id=user.id, email=user.email)
    token = make_token(user_id=user.id, email=user.email)
    return LoginResponse(
        requires_mfa=False,
        user_id=user.id,
        email=user.email,
        onboarding_complete=bool(user.onboarding_completed_at),
        is_admin=user.is_admin,
        role=user.role,
        token=token,
    )


@router.post("/verify-otp", response_model=MeResponse)
def verify_otp_endpoint(
    payload: VerifyOtpRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> MeResponse:
    email = payload.email.lower().strip()
    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid request.")

    # Check expiry
    if (
        user.mfa_otp_expires_at is None
        or datetime.now(timezone.utc) > user.mfa_otp_expires_at
    ):
        raise HTTPException(status_code=401, detail="Code expired. Please request a new one.")

    # Check attempt limit
    if user.mfa_otp_attempts >= MFA_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Please request a new code.")

    # Increment attempts
    user.mfa_otp_attempts += 1
    session.commit()

    # Verify
    if not user.mfa_otp_hash or not verify_otp(payload.otp_code, user.mfa_otp_hash):
        raise HTTPException(status_code=401, detail="Invalid code.")

    # Success — clear OTP fields
    user.mfa_otp_hash = None
    user.mfa_otp_expires_at = None
    user.mfa_otp_attempts = 0
    session.commit()

    set_auth_cookie(response, user_id=user.id, email=user.email)
    resp = _me_response(user)
    resp.token = make_token(user_id=user.id, email=user.email)
    return resp


@router.post("/resend-otp")
def resend_otp(
    payload: ResendOtpRequest,
    session: Session = Depends(get_session),
) -> dict:
    _validate_password(payload.password)
    email = payload.email.lower().strip()

    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _send_otp_to_user(user, session)
    return {"status": "sent"}


RESET_TOKEN_TTL_MINUTES = 30


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Send a password reset link. Always returns 200 to prevent email enumeration."""
    import secrets as _secrets

    email = payload.email.lower().strip()
    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if user is not None:
        token = _secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=RESET_TOKEN_TTL_MINUTES
        )
        session.commit()
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            logger.warning(
                "Failed to send password reset email to %s",
                user.email,
                exc_info=True,
            )

    return {"status": "sent"}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> dict:
    """Reset password using a valid token."""
    _validate_password(payload.password)

    user = session.execute(
        select(User).where(User.password_reset_token == payload.token)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    if (
        user.password_reset_expires_at is None
        or datetime.now(timezone.utc) > user.password_reset_expires_at
    ):
        user.password_reset_token = None
        user.password_reset_expires_at = None
        session.commit()
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    user.password_hash = hash_password(payload.password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    session.commit()

    set_auth_cookie(response, user_id=user.id, email=user.email)
    return {"status": "ok"}


class AdminResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str


@router.post("/admin-reset-password")
def admin_reset_password(
    payload: AdminResetPasswordRequest,
    x_admin_token: str | None = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Reset any user's password. Requires ADMIN_TOKEN header."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required.")

    _validate_password(payload.new_password)
    user = session.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.password_hash = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    session.commit()
    return {"status": "ok", "email": user.email}


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return _me_response(user)
