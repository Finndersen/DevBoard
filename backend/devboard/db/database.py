"""Database configuration and session management."""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import logfire
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Database URL from environment, defaulting to a repo-relative dev/test database.
# The real application database (~/.devboard/data/devboard.db) is only used when
# DATABASE_URL is explicitly set — see start.sh. Defaulting to a repo-relative path
# means each worktree/checkout gets its own isolated database.
_default_db_dir = Path(__file__).resolve().parents[2] / "data"
_default_db_dir.mkdir(parents=True, exist_ok=True)
_DEFAULT_DATABASE_URL = f"sqlite:///{_default_db_dir / 'devboard.db'}"

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)

# Create engine with connection pooling
is_sqlite = "sqlite" in DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_pre_ping=True,
)


def _configure_sqlite_connection(dbapi_connection: Any, connection_record: Any) -> None:
    """Configure SQLite connection settings on first connect."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# Enable WAL mode for SQLite to improve concurrent read performance
if is_sqlite:
    event.listen(engine, "connect", _configure_sqlite_connection)


def _log_sql_query(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any) -> None:
    logfire.debug("SQL: {statement}", statement=statement)


event.listen(engine, "before_cursor_execute", _log_sql_query)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

SessionMakerType = sessionmaker[Session]


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def get_db() -> Generator[Session]:
    """Dependency to get database session."""
    with logfire.span("db.session.create"):
        db = SessionLocal()
    try:
        yield db
        logfire.debug("Committing DB transaction")
        db.commit()
    except Exception:
        logfire.debug("Rolling back DB transaction")
        db.rollback()
        raise
    finally:
        logfire.debug("Closing DB session")
        db.close()
