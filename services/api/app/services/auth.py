import hashlib
import hmac
import logging
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User

logger = logging.getLogger(__name__)

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
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)  # e.g., ".winnowcc.ai" in production
SESSION_DAYS = int(
    os.getenv("AUTH_SESSION_DAYS") or os.getenv("AUTH_TOKEN_EXPIRES_DAYS") or "7"
)

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
_OTP_HMAC_KEY = JWT_SECRET.encode("utf-8")


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
    """Return (plaintext_code, hmac_hex_digest)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    digest = hmac.new(_OTP_HMAC_KEY, code.encode("utf-8"), hashlib.sha256).hexdigest()
    return code, digest


def verify_otp(code: str, otp_hash: str) -> bool:
    try:
        digest = hmac.new(
            _OTP_HMAC_KEY, code.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, otp_hash)
    except Exception:
        return False


# -----------------------
# JWT + cookie helpers
# -----------------------
def _hash_jti(jti: str) -> str:
    """SHA-256 hash of a JTI for storage (don't store raw JTIs)."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def make_token(*, user_id: int, email: str, token_version: int = 0) -> tuple[str, str]:
    """Create a JWT with a unique JTI claim. Returns (token, jti)."""
    jti = uuid.uuid4().hex
    now = datetime.now(UTC)
    exp = now + timedelta(days=SESSION_DAYS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
        "ver": token_version,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG), jti


def create_session(
    db_session: Session,
    *,
    user_id: int,
    jti: str,
    device_info: str | None = None,
    ip_address: str | None = None,
    expires_at: datetime,
) -> None:
    """Insert a UserSession row for the given JTI."""
    from app.models.session import UserSession

    session_row = UserSession(
        user_id=user_id,
        token_hash=_hash_jti(jti),
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db_session.add(session_row)
    db_session.flush()


def set_auth_cookie(
    response: Response,
    *,
    user_id: int,
    email: str,
    request: Request | None = None,
    db_session: Session | None = None,
    token_version: int = 0,
) -> str:
    """Set the auth cookie and optionally create a DB session row.

    Returns the raw JWT token (useful for mobile responses).
    """
    token, jti = make_token(
        user_id=user_id, email=email, token_version=token_version
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax" if COOKIE_DOMAIN else ("none" if COOKIE_SECURE else "lax"),
        secure=COOKIE_SECURE,
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=60 * 60 * 24 * SESSION_DAYS,
    )

    # Create DB session if caller provides both request and db_session
    if db_session is not None:
        ip = _extract_ip(request) if request else None
        ua = _extract_user_agent(request) if request else None
        expires = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
        create_session(
            db_session,
            user_id=user_id,
            jti=jti,
            device_info=ua,
            ip_address=ip,
            expires_at=expires,
        )
        # Update last login info on user
        from sqlalchemy import update

        db_session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(UTC), last_login_ip=ip)
        )
        db_session.commit()

    return token


def clear_auth_cookie(
    response: Response,
    *,
    token: str | None = None,
    db_session: Session | None = None,
) -> None:
    """Delete the auth cookie and optionally revoke the DB session."""
    response.delete_cookie(key=COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
    if token and db_session:
        try:
            payload = decode_token(token)
            jti = payload.get("jti")
            if jti:
                revoke_session(db_session, jti=jti, reason="user_logout")
        except HTTPException:
            pass  # Token already invalid, just clear the cookie


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid session.") from None


def _extract_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _extract_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("User-Agent", "")
    return ua[:512] if ua else None


# -----------------------
# Session validation
# -----------------------
def _get_redis():
    """Get Redis connection, return None if unavailable."""
    try:
        from redis import Redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
    except Exception:
        return None


def _validate_session(db_session: Session, payload: dict, user: User) -> None:
    """Validate the JWT's session is still active (not revoked)."""
    jti = payload.get("jti")
    if not jti:
        # Legacy tokens without JTI — allow but don't track
        return

    token_version = payload.get("ver", 0)
    if user.token_version != token_version:
        raise HTTPException(status_code=401, detail="Session invalidated.")

    token_hash = _hash_jti(jti)

    # Check Redis cache first
    redis = _get_redis()
    cache_key = f"session:{token_hash}"
    if redis:
        try:
            cached = redis.get(cache_key)
            if cached == "valid":
                _throttled_activity_update(redis, db_session, token_hash)
                return
            if cached == "revoked":
                raise HTTPException(status_code=401, detail="Session revoked.")
        except HTTPException:
            raise
        except Exception:
            pass  # Redis down, fall through to DB

    # DB lookup
    from app.models.session import UserSession

    sess = db_session.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).scalar_one_or_none()

    if sess is None:
        raise HTTPException(status_code=401, detail="Session not found.")
    if sess.revoked_at is not None:
        if redis:
            try:
                redis.setex(cache_key, 300, "revoked")
            except Exception:
                pass
        raise HTTPException(status_code=401, detail="Session revoked.")

    # Cache as valid
    if redis:
        try:
            redis.setex(cache_key, 300, "valid")
        except Exception:
            pass

    _throttled_activity_update(redis, db_session, token_hash)


def _throttled_activity_update(
    redis, db_session: Session, token_hash: str
) -> None:
    """Update last_active_at at most once per 5 minutes."""
    from app.models.session import UserSession

    throttle_key = f"session_activity:{token_hash}"
    should_update = True

    if redis:
        try:
            if redis.get(throttle_key):
                should_update = False
            else:
                redis.setex(throttle_key, 300, "1")
        except Exception:
            pass

    if should_update:
        try:
            from sqlalchemy import update

            db_session.execute(
                update(UserSession)
                .where(UserSession.token_hash == token_hash)
                .values(last_active_at=datetime.now(UTC))
            )
            db_session.commit()
        except Exception:
            logger.debug("Failed to update session activity", exc_info=True)


def revoke_session(db_session: Session, *, jti: str, reason: str) -> None:
    """Revoke a single session by JTI."""
    from app.models.session import UserSession

    token_hash = _hash_jti(jti)
    sess = db_session.execute(
        select(UserSession).where(UserSession.token_hash == token_hash)
    ).scalar_one_or_none()
    if sess and not sess.revoked_at:
        sess.revoked_at = datetime.now(UTC)
        sess.revoke_reason = reason
        db_session.commit()

    # Invalidate cache
    redis = _get_redis()
    if redis:
        try:
            redis.delete(f"session:{token_hash}")
        except Exception:
            pass


def revoke_all_sessions(
    db_session: Session, *, user_id: int, except_jti: str | None = None, reason: str
) -> int:
    """Revoke all sessions for a user. Returns count revoked."""
    from app.models.session import UserSession

    now = datetime.now(UTC)
    query = select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None),
    )
    sessions = db_session.execute(query).scalars().all()

    except_hash = _hash_jti(except_jti) if except_jti else None
    count = 0
    redis = _get_redis()

    for sess in sessions:
        if except_hash and sess.token_hash == except_hash:
            continue
        sess.revoked_at = now
        sess.revoke_reason = reason
        count += 1
        if redis:
            try:
                redis.delete(f"session:{sess.token_hash}")
            except Exception:
                pass

    db_session.commit()
    return count


# -----------------------
# FastAPI dependency
# -----------------------
def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    rm_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    authorization: str | None = Header(default=None),
) -> User:
    # Accept Bearer token (mobile) or cookie (web)
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif rm_session:
        token = rm_session

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    payload = decode_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid session.")

    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session.") from None

    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    # Validate session if JTI present
    _validate_session(session, payload, user)

    return user


def require_onboarded_user(user: User = Depends(get_current_user)) -> User:
    if not user.onboarding_completed_at:
        raise HTTPException(status_code=403, detail="Complete onboarding first.")
    return user


def require_admin_user(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")

    # Admin IP allowlist check
    from app.services.ip_protection import check_admin_ip

    ip = _extract_ip(request)
    if not check_admin_ip(ip):
        raise HTTPException(status_code=403, detail="IP not allowed for admin access.")

    return user


def get_client_platform(request: Request) -> str:
    """Return the client platform from the X-Client-Platform header."""
    return request.headers.get("X-Client-Platform", "web")


def require_employer(user: User = Depends(get_current_user)) -> User:
    """Require the user to have employer role."""
    if user.role not in ("employer", "both", "admin"):
        raise HTTPException(status_code=403, detail="Employer role required.")
    return user


def get_employer_profile(
    request: Request,
    user: User = Depends(require_employer),
    session: Session = Depends(get_session),
):
    """Get the EmployerProfile for the authenticated employer user.

    Auto-creates a starter profile if the user has employer role but no
    profile row (e.g. profile lost to a destructive migration).
    Enforces employer IP allowlist if configured.
    """
    from app.models.employer import EmployerProfile

    profile = session.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        domain = (user.email or "").split("@")[-1].split(".")[0].title() or "My Company"
        profile = EmployerProfile(user_id=user.id, company_name=domain)
        session.add(profile)
        session.commit()
        session.refresh(profile)

    # Enforce employer IP allowlist
    if profile.ip_allowlist:
        from app.services.ip_protection import check_employer_ip_allowed

        ip = _extract_ip(request)
        if not check_employer_ip_allowed(profile, ip):
            raise HTTPException(
                status_code=403,
                detail="Access denied. Your IP is not in the employer allowlist.",
            )

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
    """Get the RecruiterProfile for the authenticated recruiter user.

    Auto-creates a trial profile if the user has recruiter role but no
    profile row (e.g. profile lost to a destructive migration).
    """
    from app.models.recruiter import RecruiterProfile

    profile = session.execute(
        select(RecruiterProfile).where(RecruiterProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        # Derive company name from email domain as a placeholder
        domain = (user.email or "").split("@")[-1].split(".")[0].title() or "My Company"
        profile = RecruiterProfile(user_id=user.id, company_name=domain)
        profile.start_trial()
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile
