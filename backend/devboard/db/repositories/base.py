"""Base repository class and patterns for data access layer."""

from typing import TypeVar

import logfire
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository[T]:
    """Base repository class for data access operations."""

    def __init__(self, db_session: Session):
        """Initialize repository with database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session

    def commit(self):
        """
        Commit changes to the database.
        Commits all changes in the DB session, not just for this repository.
        """
        logfire.info("Committing DB transaction")
        self.db.commit()
