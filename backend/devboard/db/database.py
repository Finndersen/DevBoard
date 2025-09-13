"""Database configuration and session management."""

import os

import logfire
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Database URL from environment or default to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/devboard.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SessionMakerType = sessionmaker[Session]


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


def get_db():
    """Dependency to get database session."""
    with logfire.span("db.session.create"):
        db = SessionLocal()
    try:
        yield db
        logfire.info("Committing DB transaction")
        db.commit()
    except Exception:
        logfire.info("Rolling back DB transaction")
        db.rollback()
        raise
    finally:
        with logfire.span("db.session.close"):
            db.close()
