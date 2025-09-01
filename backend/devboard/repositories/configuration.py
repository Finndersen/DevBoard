"""Configuration repository for configuration data access operations."""

from sqlalchemy import select

from devboard.db.models import Configuration
from devboard.repositories.base import BaseRepository


class ConfigurationRepository(BaseRepository[Configuration]):
    """Repository for configuration data access operations."""

    def get_by_key(self, key: str) -> Configuration | None:
        """Get a configuration by its key.

        Args:
            key: The configuration key to search for

        Returns:
            Configuration instance if found, None otherwise
        """
        stmt = select(Configuration).where(Configuration.key == key)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(self, prefix: str = None) -> list[Configuration]:
        """Get all configurations, optionally filtered by key prefix.

        Args:
            prefix: Optional key prefix to filter by

        Returns:
            List of configurations
        """
        stmt = select(Configuration)
        if prefix:
            stmt = stmt.where(Configuration.key.startswith(prefix))
        return list(self.db.execute(stmt).scalars().all())

    def create(self, config: Configuration) -> Configuration:
        """Create a new configuration.

        Args:
            config: Configuration instance to create

        Returns:
            Created configuration with assigned ID
        """
        self.db.add(config)
        self.db.flush()  # Get the ID without committing
        return config

    def update(self, config: Configuration) -> Configuration:
        """Update an existing configuration.

        Args:
            config: Configuration instance to update

        Returns:
            Updated configuration
        """
        self.db.merge(config)
        return config

    def delete_by_key(self, key: str) -> bool:
        """Delete a configuration by its key.

        Args:
            key: The configuration key to delete

        Returns:
            True if configuration was deleted, False if not found
        """
        config = self.get_by_key(key)
        if config:
            self.db.delete(config)
            return True
        return False
