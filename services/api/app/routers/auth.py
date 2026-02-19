from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.user import User
from app.services.auth import (
    clear_auth_cookie,
    get_current_user,
    hash_password,
    set_auth_cookie,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    user_id: int
    email: EmailStr
    onboarding_complete: bool
    is_admin: bool = False
    role: str = "candidate"


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


@router.post("/signup", response_model=MeResponse)
def signup(payload: AuthRequest, response: Response, session: Session = Depends(get_session)) -> MeResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)

    set_auth_cookie(response, user_id=user.id, email=user.email)

    return MeResponse(user_id=user.id, email=user.email, onboarding_complete=bool(user.onboarding_completed_at), is_admin=user.is_admin, role=user.role)


@router.post("/login", response_model=MeResponse)
def login(payload: AuthRequest, response: Response, session: Session = Depends(get_session)) -> MeResponse:
    _validate_password(payload.password)

    email = payload.email.lower().strip()

    user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    set_auth_cookie(response, user_id=user.id, email=user.email)

    return MeResponse(user_id=user.id, email=user.email, onboarding_complete=bool(user.onboarding_completed_at), is_admin=user.is_admin, role=user.role)


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_auth_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user_id=user.id, email=user.email, onboarding_complete=bool(user.onboarding_completed_at), is_admin=user.is_admin, role=user.role)
