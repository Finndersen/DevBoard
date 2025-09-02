"""Base repository class and patterns for data access layer."""

from abc import ABC
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository class for data access operations."""

    def __init__(self, db_session: Session):
        """Initialize repository with database session.

        Args:
            db_session: SQLAlchemy session for database operations
        """
        self.db = db_session
