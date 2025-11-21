"""Database configuration and session management."""

import os
from collections.abc import Generator

import logfire
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Database URL from environment or default to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/devboard.db")

# Create engine with connection pooling
is_sqlite = "sqlite" in DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite to improve concurrent read performance
if is_sqlite:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))

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
