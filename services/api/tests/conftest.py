"""
Shared test fixtures for the Winnow API test suite.

Uses a Postgres test database for integration tests. Ensure the test DB exists:
  docker exec -it infra-db-1 psql -U resumematch -c "CREATE DATABASE resumematch_test;"
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set test environment BEFORE importing app
os.environ["TESTING"] = "1"
os.environ.setdefault("AUTH_SECRET", "test-secret-key")
os.environ.setdefault("AUTH_COOKIE_NAME", "rm_session")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

# Test database URL — use the same local Postgres but a test database
TEST_DB_URL = os.environ.get(
    "TEST_DB_URL",
    "postgresql+psycopg://resumematch:resumematch@localhost:5432/resumematch_test",
)
os.environ["DB_URL"] = TEST_DB_URL

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import hash_password, make_token  # noqa: E402


def _check_pgvector(eng):
    """Return True if pgvector is available in the test database."""
    with eng.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine.

    Enables pgvector if available and creates all tables.
    If pgvector is missing, replaces VECTOR columns with TEXT
    so the schema can still be created.
    """
    eng = create_engine(TEST_DB_URL)
    pgvector_ok = _check_pgvector(eng)

    # Import all models so Base.metadata knows about them
    import app.models as _models  # noqa: F401

    if not pgvector_ok:
        # Replace VECTOR columns with TEXT so tables can be created
        # and ORM queries work without pgvector
        from sqlalchemy import Text as _Text

        from app.models.candidate_profile import CandidateProfile
        from app.models.job import Job

        for model in (CandidateProfile, Job):
            tbl = model.__table__
            col = tbl.columns.get("embedding")
            if col is not None:
                col.type = _Text()

    Base.metadata.create_all(eng)

    # Create non-ORM tables referenced by cascade_delete and other services
    _extra_tables = [
        "CREATE TABLE IF NOT EXISTS mjass_application_drafts "
        "(id SERIAL PRIMARY KEY, user_id INTEGER)",
        "CREATE TABLE IF NOT EXISTS mjass_application_events "
        "(id SERIAL PRIMARY KEY, draft_id INTEGER)",
        "CREATE TABLE IF NOT EXISTS consents (id SERIAL PRIMARY KEY, user_id INTEGER)",
        "CREATE TABLE IF NOT EXISTS candidate_preferences_v1 "
        "(id SERIAL PRIMARY KEY, user_id INTEGER)",
        "CREATE TABLE IF NOT EXISTS onboarding_state "
        "(id SERIAL PRIMARY KEY, user_id INTEGER)",
        "CREATE TABLE IF NOT EXISTS parsed_resume_documents "
        "(id SERIAL PRIMARY KEY, resume_document_id INTEGER)",
    ]
    with eng.connect() as conn:
        for sql in _extra_tables:
            conn.execute(text(sql))
        conn.commit()

    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh DB session for each test, rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client with overridden DB dependency."""

    def override_get_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session):
    """Create a test user and return (user, jwt_token)."""
    from app.models.user import User

    user = User(
        email="test@winnow.dev",
        password_hash=hash_password("TestPass123!"),
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = make_token(user_id=user.id, email=user.email)
    return user, token


@pytest.fixture()
def auth_client(client, test_user):
    """Test client with auth cookie set."""
    user, token = test_user
    client.cookies.set("rm_session", token)
    return client, user


@pytest.fixture()
def admin_client(client, db_session):
    """Test client with admin user auth cookie."""
    from app.models.user import User

    admin = User(
        email="admin@winnow.dev",
        password_hash=hash_password("AdminPass123!"),
        is_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = make_token(user_id=admin.id, email=admin.email)
    client.cookies.set("rm_session", token)
    return client, admin
