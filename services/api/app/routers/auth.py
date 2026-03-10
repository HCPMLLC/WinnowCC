import logging
import os
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.services.auth import (
    clear_auth_cookie,
    generate_otp,
    get_current_user,
    hash_password,
    make_token,
    set_auth_cookie,
    verify_otp,
    verify_password,
)
from app.services.email import (
    send_mfa_otp_email,
    send_mfa_otp_sms,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET", "")

MFA_OTP_TTL_MINUTES = 10
MFA_MAX_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
SIGNUP_ALLOWED_ROLES = {"candidate", "employer", "recruiter"}


class AuthRequest(BaseModel):
    email: EmailStr
    password: str
    role: str | None = None  # optional; used during signup only


class MeResponse(BaseModel):
    user_id: int
    email: EmailStr
    first_name: str | None = None
    onboarding_complete: bool
    is_admin: bool = False
    role: str = "candidate"
    token: str | None = None


class LoginResponse(BaseModel):
    requires_mfa: bool = False
    mfa_delivery_method: str | None = None
    has_phone: bool | None = None
    user_id: int | None = None
    email: str | None = None
    first_name: str | None = None
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
    delivery_method: str | None = None  # "email" or "sms"


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


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
                "Use 72 bytes or fewer "
                "(roughly <=72 ASCII characters; "
                "fewer if using emojis/"
                "special characters)."
            ),
        )


def _me_response(user: User) -> MeResponse:
    return MeResponse(
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        onboarding_complete=bool(user.onboarding_completed_at),
        is_admin=user.is_admin,
        role=user.role,
    )


def _normalize_phone_e164(phone: str) -> str:
    """Ensure a US phone number is in E.164 format (+1XXXXXXXXXX)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _prepare_otp(
    user: User,
    session: Session,
    delivery_method: str | None = None,
) -> tuple[str, str, str, str]:
    """Generate an OTP, persist hash + expiry, return (code, method, dest, email).

    DB work happens here (must run before the response).
    The actual send is deferred to a BackgroundTask via ``_do_send_otp``.
    """
    method = delivery_method or user.mfa_delivery_method or "sms"
    # Fall back to email if SMS requested but no phone on file
    if method == "sms" and not user.phone:
        method = "email"

    code, otp_hash = generate_otp()
    user.mfa_otp_hash = otp_hash
    user.mfa_otp_expires_at = datetime.now(UTC) + timedelta(minutes=MFA_OTP_TTL_MINUTES)
    user.mfa_otp_attempts = 0
    # Capture destination + email before commit (avoids lazy-load issues)
    dest = _normalize_phone_e164(user.phone) if method == "sms" else user.email
    email = user.email
    session.commit()

    return code, method, dest, email


def _do_send_otp(
    code: str, method: str, dest: str, user_id: int, fallback_email: str | None = None
) -> None:
    """Send the OTP via email or SMS.  Runs as a BackgroundTask.

    When *method* is ``"sms"`` and delivery fails, automatically retries
    via email using *fallback_email* so the user isn't locked out.
    """
    try:
        if method == "sms":
            send_mfa_otp_sms(dest, code)
        else:
            send_mfa_otp_email(dest, code)
    except Exception:
        logger.warning(
            "Failed to send MFA OTP via %s to user %s",
            method,
            user_id,
            exc_info=True,
        )
        # Fall back to email when SMS fails
        if method == "sms" and fallback_email:
            try:
                logger.info("Falling back to email OTP for user %s", user_id)
                send_mfa_otp_email(fallback_email, code)
            except Exception:
                logger.error(
                    "Email fallback also failed for user %s",
                    user_id,
                    exc_info=True,
                )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=MeResponse)
@limiter.limit("5/minute")
def signup(
    request: Request,
    response: Response,
    payload: AuthRequest = Body(...),
    session: Session = Depends(get_session),
) -> MeResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    existing = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Determine role (default to candidate)
    role = payload.role if payload.role in SIGNUP_ALLOWED_ROLES else "candidate"

    user = User(email=email, password_hash=hash_password(payload.password), role=role)
    # Employer/recruiter accounts require MFA
    if role in ("employer", "recruiter"):
        user.mfa_required = True
    session.add(user)
    session.commit()
    session.refresh(user)

    # Phase 2: Contact-Account Recognition — notify recruiters if this
    # email matches any of their CRM contacts or pipeline candidates.
    try:
        from app.services.recruiter_service import check_signup_email_matches

        check_signup_email_matches(session, email, user.id, role)
        session.commit()
    except Exception:
        logger.warning(
            "Contact-account recognition failed for %s", email, exc_info=True
        )

    set_auth_cookie(response, user_id=user.id, email=user.email)
    resp = _me_response(user)
    resp.token = make_token(user_id=user.id, email=user.email)
    return resp


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    bg: BackgroundTasks,
    payload: AuthRequest = Body(...),
    session: Session = Depends(get_session),
) -> LoginResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # --- MFA gate ---
    if user.mfa_required:
        code, method_used, dest, user_email = _prepare_otp(user, session)
        bg.add_task(_do_send_otp, code, method_used, dest, user.id, user_email)
        return LoginResponse(
            requires_mfa=True,
            mfa_delivery_method=method_used,
            has_phone=bool(user.phone),
            email=user.email,
        )

    # No MFA — normal login
    set_auth_cookie(response, user_id=user.id, email=user.email)
    token = make_token(user_id=user.id, email=user.email)
    return LoginResponse(
        requires_mfa=False,
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        onboarding_complete=bool(user.onboarding_completed_at),
        is_admin=user.is_admin,
        role=user.role,
        token=token,
    )


@router.post("/verify-otp", response_model=MeResponse)
@limiter.limit("10/minute")
def verify_otp_endpoint(
    request: Request,
    response: Response,
    payload: VerifyOtpRequest = Body(...),
    session: Session = Depends(get_session),
) -> MeResponse:
    email = payload.email.lower().strip()
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid request.")

    # Check expiry
    if user.mfa_otp_expires_at is None or datetime.now(UTC) > user.mfa_otp_expires_at:
        raise HTTPException(
            status_code=401, detail="Code expired. Please request a new one."
        )

    # Check attempt limit
    if user.mfa_otp_attempts >= MFA_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429, detail="Too many attempts. Please request a new code."
        )

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
@limiter.limit("3/minute")
def resend_otp(
    request: Request,
    bg: BackgroundTasks,
    payload: ResendOtpRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    _validate_password(payload.password)
    email = payload.email.lower().strip()

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    requested = payload.delivery_method
    if requested and requested in ("email", "sms"):
        user.mfa_delivery_method = requested
        session.commit()

    code, method_used, dest, user_email = _prepare_otp(
        user, session, delivery_method=requested
    )
    bg.add_task(_do_send_otp, code, method_used, dest, user.id, user_email)
    return {"status": "sent", "delivery_method": method_used}


RESET_TOKEN_TTL_MINUTES = 30


@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: ForgotPasswordRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    """Send a password reset link. Always returns 200 to prevent email enumeration."""
    import secrets as _secrets

    email = payload.email.lower().strip()
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is not None:
        token = _secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.now(UTC) + timedelta(
            minutes=RESET_TOKEN_TTL_MINUTES
        )
        session.commit()
        background_tasks.add_task(send_password_reset_email, user.email, token)

    return {"status": "sent"}


@router.post("/reset-password")
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    response: Response,
    payload: ResetPasswordRequest = Body(...),
    session: Session = Depends(get_session),
) -> dict:
    """Reset password using a valid token."""
    _validate_password(payload.password)

    user = session.execute(
        select(User).where(User.password_reset_token == payload.token)
    ).scalar_one_or_none()

    if user is None or (
        user.password_reset_expires_at is None
        or datetime.now(UTC) > user.password_reset_expires_at
    ):
        # Clear expired token if user was found
        if user is not None:
            user.password_reset_token = None
            user.password_reset_expires_at = None
            session.commit()
        raise HTTPException(
            status_code=400, detail="Invalid or expired reset link."
        )

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


class AdminSetMfaRequest(BaseModel):
    email: EmailStr
    mfa_required: bool


@router.post("/admin-set-mfa")
def admin_set_mfa(
    payload: AdminSetMfaRequest,
    x_admin_token: str | None = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Enable or disable MFA for any user. Requires ADMIN_TOKEN header."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required.")

    user = session.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.mfa_required = payload.mfa_required
    if not payload.mfa_required:
        user.mfa_otp_hash = None
        user.mfa_otp_expires_at = None
        user.mfa_otp_attempts = 0
    session.commit()
    return {"status": "ok", "email": user.email, "mfa_required": user.mfa_required}


ALLOWED_ROLES = {"candidate", "employer", "recruiter", "both", "admin"}


class AdminSetRoleRequest(BaseModel):
    email: EmailStr
    role: str | None = None
    is_admin: bool | None = None


@router.post("/admin-set-role")
def admin_set_role(
    payload: AdminSetRoleRequest,
    x_admin_token: str | None = Header(None),
    session: Session = Depends(get_session),
) -> dict:
    """Update a user's role and/or admin flag. Requires ADMIN_TOKEN header."""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or not x_admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="Admin access required.")

    if payload.role is not None and payload.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(ALLOWED_ROLES))}",
        )

    user = session.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.role is not None:
        user.role = payload.role
        user.mfa_required = payload.role in ("employer", "recruiter", "both")
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    session.commit()
    return {
        "status": "ok",
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin,
    }


@router.post("/oauth/callback", response_model=MeResponse)
async def oauth_callback(
    payload: OAuthCallbackRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> MeResponse:
    """Exchange an Auth0 authorization code for a session."""
    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID or not AUTH0_CLIENT_SECRET:
        raise HTTPException(
            status_code=503, detail="OAuth is not configured on this server."
        )

    # Exchange authorization code for access token
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    async with httpx.AsyncClient() as http:
        token_resp = await http.post(
            token_url,
            json={
                "grant_type": "authorization_code",
                "client_id": AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "code": payload.code,
                "redirect_uri": payload.redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="OAuth token exchange failed.")

        access_token = token_resp.json().get("access_token")

        # Fetch user info
        userinfo_resp = await http.get(
            f"https://{AUTH0_DOMAIN}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    userinfo = userinfo_resp.json()
    email = userinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=400, detail="Email not provided by OAuth provider."
        )
    email = email.lower().strip()
    sub = userinfo.get("sub", "")

    # Find or create user
    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None:
        user = User(
            email=email, password_hash="", oauth_provider="auth0", oauth_sub=sub
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        # Link OAuth fields only if not already linked
        if not user.oauth_provider:
            user.oauth_provider = "auth0"
            user.oauth_sub = sub
            session.commit()

    set_auth_cookie(response, user_id=user.id, email=user.email)
    resp = _me_response(user)
    resp.token = make_token(user_id=user.id, email=user.email)
    return resp


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return _me_response(user)


class SetMfaDeliveryRequest(BaseModel):
    delivery_method: str  # "email" or "sms"


@router.post("/mfa-delivery")
def set_mfa_delivery(
    payload: SetMfaDeliveryRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Set the user's preferred MFA OTP delivery method."""
    if payload.delivery_method not in ("email", "sms"):
        raise HTTPException(
            status_code=422, detail="delivery_method must be 'email' or 'sms'."
        )
    if payload.delivery_method == "sms" and not user.phone:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot use SMS delivery — no phone "
                "number on file. Update your "
                "profile first."
            ),
        )
    user.mfa_delivery_method = payload.delivery_method
    session.commit()
    return {"status": "ok", "delivery_method": user.mfa_delivery_method}
