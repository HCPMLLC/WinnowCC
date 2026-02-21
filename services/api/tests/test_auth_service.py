import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.user import User
from app.services import auth as auth_service


def _make_request(*, headers=None):
    """Create a minimal Starlette Request for testing get_current_user."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__])
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setattr(auth_service, "JWT_SECRET", "test-secret")
    monkeypatch.setattr(auth_service, "JWT_ALG", "HS256")
    monkeypatch.setattr(auth_service, "COOKIE_NAME", "rm_session")
    monkeypatch.setattr(auth_service, "SESSION_DAYS", 7)


def test_hash_and_verify_password() -> None:
    hashed = auth_service.hash_password("password123")
    assert auth_service.verify_password("password123", hashed)
    assert not auth_service.verify_password("nope", hashed)


def test_hash_password_rejects_long_input() -> None:
    with pytest.raises(HTTPException) as exc:
        auth_service.hash_password("a" * 73)
    assert exc.value.status_code == 400


def test_decode_token_invalid_raises() -> None:
    with pytest.raises(HTTPException) as exc:
        auth_service.decode_token("bad-token")
    assert exc.value.status_code == 401


def test_make_token_roundtrip() -> None:
    token = auth_service.make_token(user_id=5, email="a@b.com")
    payload = auth_service.decode_token(token)
    assert payload["sub"] == "5"
    assert payload["email"] == "a@b.com"


def test_set_auth_cookie_sets_cookie_header() -> None:
    response = Response()
    auth_service.set_auth_cookie(response, user_id=1, email="a@b.com")
    set_cookie = response.headers.get("set-cookie", "")
    assert auth_service.COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_set_auth_cookie_secure_and_max_age(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "COOKIE_SECURE", True)
    monkeypatch.setattr(auth_service, "SESSION_DAYS", 1)
    response = Response()
    auth_service.set_auth_cookie(response, user_id=1, email="a@b.com")
    set_cookie = response.headers.get("set-cookie", "")
    assert "Secure" in set_cookie
    assert "Max-Age=86400" in set_cookie


def test_get_current_user_ok(session) -> None:
    user = User(email="a@b.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    token = auth_service.make_token(user_id=user.id, email=user.email)

    req = _make_request()
    current = auth_service.get_current_user(
        request=req, session=session, rm_session=token
    )
    assert current.id == user.id


def test_get_current_user_via_bearer(session) -> None:
    """Bearer token auth works (mobile app path)."""
    user = User(email="bearer@b.com", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)
    token = auth_service.make_token(user_id=user.id, email=user.email)

    req = _make_request(headers={"authorization": f"Bearer {token}"})
    current = auth_service.get_current_user(
        request=req, session=session, rm_session=None
    )
    assert current.id == user.id


def test_get_current_user_missing_cookie(session) -> None:
    req = _make_request()
    with pytest.raises(HTTPException) as exc:
        auth_service.get_current_user(request=req, session=session, rm_session=None)
    assert exc.value.status_code == 401


def test_get_current_user_missing_user(session) -> None:
    token = auth_service.make_token(user_id=999, email="a@b.com")
    req = _make_request()
    with pytest.raises(HTTPException) as exc:
        auth_service.get_current_user(request=req, session=session, rm_session=token)
    assert exc.value.status_code == 401


def test_require_onboarded_user_blocks() -> None:
    user = User(email="a@b.com", password_hash="x")
    with pytest.raises(HTTPException) as exc:
        auth_service.require_onboarded_user(user)
    assert exc.value.status_code == 403
