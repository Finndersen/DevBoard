"""Configuration repository for configuration data access operations."""

import logfire
from sqlalchemy import select

from devboard.db.models import Configuration
from devboard.db.repositories.base import BaseRepository


class ConfigurationRepository(BaseRepository[Configuration]):
    """Repository for configuration data access operations.

    Implements a class-level cache for configurations accessed by key
    to improve performance when frequently accessing the same configurations.
    """

    _cache: dict[str, Configuration] = {}

    def _set_in_cache(self, config: Configuration) -> None:
        """Store a configuration object in the cache after making it session-independent.

        This ensures the object can be accessed outside of the session context
        without triggering DetachedInstanceError.

        Args:
            config: Configuration instance to cache
        """
        # Remove the object from the session if it's still attached
        # Check if object is in the session before expunging
        if config in self.db:
            self.db.expunge(config)

        # Store in the class-level cache
        ConfigurationRepository._cache[config.key] = config

    def get_by_key(self, key: str) -> Configuration | None:
        """Get a configuration by its key.

        Uses class-level cache to avoid repeated database queries for the same key.

        Args:
            key: The configuration key to search for

        Returns:
            Configuration instance if found, None otherwise
        """
        # Check cache first
        if key in ConfigurationRepository._cache:
            logfire.debug(f"Configuration cache hit for key:{key}")
            return ConfigurationRepository._cache[key]

        # Cache miss - fetch from database
        logfire.info(f"Fetching configuration with key:{key}")
        stmt = select(Configuration).where(Configuration.key == key)
        result = self.db.execute(stmt).scalar_one_or_none()

        # Store in cache
        if result is not None:
            self._set_in_cache(result)
        return result

    def get_all(self, prefix: str | None = None) -> list[Configuration]:
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

        # Store in cache
        self._set_in_cache(config)
        return config

    def update(self, config: Configuration) -> Configuration:
        """Update an existing configuration.

        Args:
            config: Configuration instance to update

        Returns:
            Updated configuration
        """
        self.db.merge(config)

        # Store in cache
        self._set_in_cache(config)

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
            # Clear cache entry for this key
            if key in ConfigurationRepository._cache:
                del ConfigurationRepository._cache[key]
            return True
        return False
