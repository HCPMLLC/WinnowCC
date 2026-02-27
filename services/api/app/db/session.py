import os
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        db_url = os.getenv("DB_URL", "").strip()
        if not db_url:
            raise RuntimeError("DB_URL is not set")
        # Differentiate pool sizes: workers need fewer connections than the API.
        is_worker = os.getenv("WINNOW_PROCESS_TYPE") == "worker"
        _ENGINE = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=2 if is_worker else 3,
            max_overflow=3 if is_worker else 7,
            pool_timeout=10,
            pool_recycle=1800,
        )
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SESSION_FACTORY


def get_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
