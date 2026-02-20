import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User

# -----------------------
# Config
# -----------------------
JWT_ALG = "HS256"
# Support legacy env names used in .env.example/README.
JWT_SECRET = (os.getenv("AUTH_JWT_SECRET") or os.getenv("AUTH_SECRET") or "").strip()
if not JWT_SECRET:
    raise RuntimeError("AUTH_SECRET environment variable must be set")
COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "rm_session").strip()
COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = int(
    os.getenv("AUTH_SESSION_DAYS") or os.getenv("AUTH_TOKEN_EXPIRES_DAYS") or "7"
)

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------
# Password hashing
# -----------------------
def hash_password(password: str) -> str:
    # bcrypt only uses first 72 bytes; enforce a safe max for user clarity
    pw = (password or "").strip()
    if len(pw.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes).")
    return _PWD_CONTEXT.hash(pw)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PWD_CONTEXT.verify(password, password_hash)
    except Exception:
        return False


# -----------------------
# OTP helpers
# -----------------------
def generate_otp() -> tuple[str, str]:
    """Return (plaintext_code, bcrypt_hash)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    return code, _PWD_CONTEXT.hash(code)


def verify_otp(code: str, otp_hash: str) -> bool:
    try:
        return _PWD_CONTEXT.verify(code, otp_hash)
    except Exception:
        return False


# -----------------------
# JWT + cookie helpers
# -----------------------
def make_token(*, user_id: int, email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=SESSION_DAYS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def set_auth_cookie(response: Response, *, user_id: int, email: str) -> None:
    token = make_token(user_id=user_id, email=email)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
        max_age=60 * 60 * 24 * SESSION_DAYS,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid session.")


# -----------------------
# FastAPI dependency
# -----------------------
def get_current_user(
    session: Session = Depends(get_session),
    rm_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> User:
    if not rm_session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    payload = decode_token(rm_session)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid session.")

    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session.")

    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


def require_onboarded_user(user: User = Depends(get_current_user)) -> User:
    if not user.onboarding_completed_at:
        raise HTTPException(status_code=403, detail="Complete onboarding first.")
    return user


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def require_employer(user: User = Depends(get_current_user)) -> User:
    """Require the user to have employer role."""
    if user.role not in ("employer", "both", "admin"):
        raise HTTPException(status_code=403, detail="Employer role required.")
    return user


def get_employer_profile(
    user: User = Depends(require_employer),
    session: Session = Depends(get_session),
):
    """Get the EmployerProfile for the authenticated employer user."""
    from app.models.employer import EmployerProfile

    profile = session.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Employer profile not found.")
    return profile


def require_recruiter(user: User = Depends(get_current_user)) -> User:
    """Require the user to have recruiter role."""
    if user.role not in ("recruiter", "both", "admin"):
        raise HTTPException(status_code=403, detail="Recruiter role required.")
    return user


def get_recruiter_profile(
    user: User = Depends(require_recruiter),
    session: Session = Depends(get_session),
):
    """Get the RecruiterProfile for the authenticated recruiter user."""
    from app.models.recruiter import RecruiterProfile

    profile = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Recruiter profile not found.")
    return profile
