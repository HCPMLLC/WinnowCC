import os
import re
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, inspect, pool, text

from app.db.base import Base
import app.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

from dotenv import load_dotenv
load_dotenv()

# Patterns that are destructive to production data
_DESTRUCTIVE_PATTERNS = [
    re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+TABLE\s+(?!IF\s+EXISTS\b)", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
]

_VERSIONS_DIR = Path(__file__).parent / "versions"


def get_db_url() -> str:
    db_url = os.getenv("DB_URL", "").strip()
    if not db_url:
        raise RuntimeError("DB_URL is not set")
    return db_url


def _has_production_data(connection) -> bool:
    """Return True if the database has a users table with rows."""
    insp = inspect(connection)
    if "users" not in insp.get_table_names():
        return False
    row = connection.execute(text("SELECT EXISTS (SELECT 1 FROM users)")).scalar()
    return bool(row)


def _guard_destructive_migrations(connection) -> None:
    """Block migrations containing destructive SQL on databases with data.

    Override with ALEMBIC_ALLOW_DESTRUCTIVE=1 for intentional operations.
    """
    if os.environ.get("ALEMBIC_ALLOW_DESTRUCTIVE") == "1":
        return

    if not _has_production_data(connection):
        return

    # Scan pending migration files for destructive patterns
    script = context.get_context().script
    current_rev = context.get_context().get_current_revision()
    head_rev = script.get_current_head()
    if current_rev == head_rev:
        return  # nothing pending

    violations = []
    for rev in script.iterate_revisions(head_rev, current_rev):
        if rev.revision == current_rev:
            continue  # skip the already-applied revision
        # Find the migration file on disk
        source_path = _VERSIONS_DIR / f"{rev.revision}.py"
        # Also try matching by file stem (revisions may have descriptive filenames)
        if not source_path.exists():
            matches = list(_VERSIONS_DIR.glob(f"{rev.revision}*.py"))
            if not matches:
                # Try finding the file via the module's __file__ attribute
                mod = rev.module
                if hasattr(mod, "__file__") and mod.__file__:
                    source_path = Path(mod.__file__)
                else:
                    continue
            else:
                source_path = matches[0]

        source = source_path.read_text()
        for pattern in _DESTRUCTIVE_PATTERNS:
            if pattern.search(source):
                violations.append(
                    f"  {rev.revision}: matched {pattern.pattern!r}"
                )

    if violations:
        raise RuntimeError(
            "DESTRUCTIVE MIGRATION BLOCKED — database has production data.\n"
            "Violations:\n" + "\n".join(violations) + "\n"
            "Set ALEMBIC_ALLOW_DESTRUCTIVE=1 to override."
        )


def run_migrations_offline() -> None:
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_db_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        _guard_destructive_migrations(connection)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
