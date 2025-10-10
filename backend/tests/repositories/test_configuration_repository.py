import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Configuration
from devboard.db.repositories import ConfigurationRepository


class TestConfigurationRepository:
    """Tests for ConfigurationRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ConfigurationRepository:
        return ConfigurationRepository(db_session)

    @pytest.fixture
    def sample_config(self) -> Configuration:
        return Configuration(key="test.setting", value_json="test_value")

    def test_create_configuration(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test creating a new configuration."""
        created = repo.create(sample_config)
        assert created.key == "test.setting"
        assert created.value_json == "test_value"

    def test_get_by_key(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test getting a configuration by key."""
        repo.create(sample_config)
        retrieved = repo.get_by_key("test.setting")

        assert retrieved is not None
        assert retrieved.key == "test.setting"
        assert retrieved.value_json == "test_value"

    def test_get_by_key_not_found(self, repo: ConfigurationRepository):
        """Test getting a configuration by key when it doesn't exist."""
        result = repo.get_by_key("nonexistent.key")
        assert result is None

    def test_get_all_without_prefix(self, repo: ConfigurationRepository):
        """Test getting all configurations without prefix filter."""
        config1 = Configuration(key="app.setting1", value_json="value1")
        config2 = Configuration(key="db.setting2", value_json="value2")

        repo.create(config1)
        repo.create(config2)

        all_configs = repo.get_all()
        assert len(all_configs) == 2
        config_keys = [c.key for c in all_configs]
        assert "app.setting1" in config_keys
        assert "db.setting2" in config_keys

    def test_get_all_with_prefix(self, repo: ConfigurationRepository):
        """Test getting configurations filtered by prefix."""
        config1 = Configuration(key="app.setting1", value_json="value1")
        config2 = Configuration(key="app.setting2", value_json="value2")
        config3 = Configuration(key="db.setting", value_json="value3")

        repo.create(config1)
        repo.create(config2)
        repo.create(config3)

        app_configs = repo.get_all(prefix="app.")
        assert len(app_configs) == 2
        for config in app_configs:
            assert config.key.startswith("app.")

    def test_update_configuration(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test updating a configuration."""
        created = repo.create(sample_config)
        created.value_json = "updated_value"

        updated = repo.update(created)
        assert updated.value_json == "updated_value"

    def test_delete_by_key(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test deleting a configuration by key."""
        repo.create(sample_config)
        result = repo.delete_by_key("test.setting")

        assert result is True
        assert repo.get_by_key("test.setting") is None

    def test_delete_by_key_not_found(self, repo: ConfigurationRepository):
        """Test deleting a configuration by key when it doesn't exist."""
        result = repo.delete_by_key("nonexistent.key")
        assert result is False

    def test_cache_hit_on_repeated_get_by_key(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test that repeated calls to get_by_key use cache."""
        repo.create(sample_config)

        # Clear the cache to ensure we start fresh
        ConfigurationRepository._cache.clear()

        # First call should populate cache
        first_result = repo.get_by_key("test.setting")
        assert first_result is not None
        assert "test.setting" in ConfigurationRepository._cache

        # Second call should use cache (no DB query)
        second_result = repo.get_by_key("test.setting")
        assert second_result is not None
        assert second_result.key == first_result.key

    def test_cache_cleared_on_create(self, repo: ConfigurationRepository):
        """Test that cache is cleared when creating a configuration with existing key in cache."""
        # First, create and cache an initial configuration
        initial_config = Configuration(key="test.key", value_json="initial_value")
        repo.create(initial_config)

        # Get it to populate cache
        result = repo.get_by_key("test.key")
        assert result is not None
        assert "test.key" in ConfigurationRepository._cache

        # Update the same configuration (simulating a re-create scenario)
        result.value_json = "updated_value"
        repo.create(result)

        # Cache should still exist but be cleared after update
        # Next get_by_key should fetch fresh data
        retrieved = repo.get_by_key("test.key")
        assert retrieved is not None
        assert retrieved.value_json == "updated_value"

    def test_cache_cleared_on_update(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test that cache is updated when updating a configuration."""
        created = repo.create(sample_config)

        # Populate cache
        first_result = repo.get_by_key("test.setting")
        assert first_result is not None
        assert "test.setting" in ConfigurationRepository._cache

        # Update the configuration
        created.value_json = "updated_value"
        repo.update(created)

        # Cache should still contain the key with updated value
        assert "test.setting" in ConfigurationRepository._cache
        cached_value = ConfigurationRepository._cache["test.setting"]
        assert cached_value.value_json == "updated_value"

        # Next get_by_key should return cached updated data
        retrieved = repo.get_by_key("test.setting")
        assert retrieved is not None
        assert retrieved.value_json == "updated_value"

    def test_cache_cleared_on_delete(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test that cache is cleared when deleting a configuration."""
        repo.create(sample_config)

        # Populate cache
        first_result = repo.get_by_key("test.setting")
        assert first_result is not None
        assert "test.setting" in ConfigurationRepository._cache

        # Delete the configuration
        result = repo.delete_by_key("test.setting")
        assert result is True

        # Cache should be cleared for this key
        assert "test.setting" not in ConfigurationRepository._cache

        # Next get_by_key should return None
        retrieved = repo.get_by_key("test.setting")
        assert retrieved is None
