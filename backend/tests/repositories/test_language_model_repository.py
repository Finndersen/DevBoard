"""Tests for LanguageModelRepository."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from devboard.agents.language_models import LLMProvider, ModelType
from devboard.db.repositories import LanguageModelRepository


class TestLanguageModelRepository:
    """Tests for LanguageModelRepository CRUD and query operations."""

    @pytest.fixture
    def repo(self, db_session: Session) -> LanguageModelRepository:
        return LanguageModelRepository(db_session)

    def test_create_model(self, repo: LanguageModelRepository):
        """Test creating a new language model."""
        model = repo.create(
            provider=LLMProvider.ANTHROPIC,
            name="claude-sonnet-4",
            model_type=ModelType.STANDARD,
            full_name="claude-sonnet-4-20250514",
        )
        assert model.id is not None
        assert model.provider == LLMProvider.ANTHROPIC
        assert model.name == "claude-sonnet-4"
        assert model.model_type == ModelType.STANDARD
        assert model.full_name == "claude-sonnet-4-20250514"
        assert model.bedrock_id is None
        assert model.model_id == "anthropic:claude-sonnet-4"

    def test_create_model_minimal(self, repo: LanguageModelRepository):
        """Test creating a model with only required fields."""
        model = repo.create(
            provider=LLMProvider.OPENAI,
            name="gpt-4",
            model_type=ModelType.STANDARD,
        )
        assert model.id is not None
        assert model.full_name is None
        assert model.bedrock_id is None

    def test_create_model_with_bedrock_id(self, repo: LanguageModelRepository):
        """Test creating a model with a Bedrock ID."""
        model = repo.create(
            provider=LLMProvider.ANTHROPIC,
            name="claude-sonnet-bedrock",
            model_type=ModelType.STANDARD,
            bedrock_id="eu.anthropic.claude-sonnet-v1:0",
        )
        assert model.bedrock_id == "eu.anthropic.claude-sonnet-v1:0"

    def test_get_by_id(self, repo: LanguageModelRepository):
        """Test getting a model by integer ID."""
        created = repo.create(
            provider=LLMProvider.GOOGLE,
            name="gemini-2.5-pro",
            model_type=ModelType.STANDARD,
        )
        retrieved = repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "gemini-2.5-pro"

    def test_get_by_id_not_found(self, repo: LanguageModelRepository):
        """Test getting a model by ID when it does not exist."""
        result = repo.get_by_id(99999)
        assert result is None

    def test_get_by_model_id(self, repo: LanguageModelRepository):
        """Test getting a model by provider:name string."""
        repo.create(
            provider=LLMProvider.OPENAI,
            name="gpt-5",
            model_type=ModelType.STANDARD,
        )
        result = repo.get_by_model_id("openai:gpt-5")
        assert result is not None
        assert result.provider == LLMProvider.OPENAI
        assert result.name == "gpt-5"

    def test_get_by_model_id_not_found(self, repo: LanguageModelRepository):
        """Test getting a model by model_id string when it does not exist."""
        result = repo.get_by_model_id("openai:nonexistent-model")
        assert result is None

    def test_get_by_model_id_invalid_format(self, repo: LanguageModelRepository):
        """Test that an invalid model_id string (no colon) returns None."""
        result = repo.get_by_model_id("invalid-no-colon")
        assert result is None

    def test_get_by_model_id_invalid_provider(self, repo: LanguageModelRepository):
        """Test that an unknown provider in model_id returns None."""
        result = repo.get_by_model_id("unknownprovider:some-model")
        assert result is None

    def test_get_all(self, repo: LanguageModelRepository):
        """Test getting all language models."""
        repo.create(provider=LLMProvider.OPENAI, name="gpt-all-1", model_type=ModelType.FAST)
        repo.create(provider=LLMProvider.ANTHROPIC, name="claude-all-1", model_type=ModelType.ADVANCED)
        repo.create(provider=LLMProvider.GOOGLE, name="gemini-all-1", model_type=ModelType.STANDARD)

        all_models = repo.get_all()
        names = [m.name for m in all_models]
        assert "gpt-all-1" in names
        assert "claude-all-1" in names
        assert "gemini-all-1" in names

    def test_get_by_provider(self, repo: LanguageModelRepository):
        """Test filtering models by provider."""
        repo.create(provider=LLMProvider.OPENAI, name="gpt-provider-1", model_type=ModelType.FAST)
        repo.create(provider=LLMProvider.OPENAI, name="gpt-provider-2", model_type=ModelType.STANDARD)
        repo.create(provider=LLMProvider.ANTHROPIC, name="claude-provider-1", model_type=ModelType.ADVANCED)

        openai_models = repo.get_by_provider(LLMProvider.OPENAI)
        openai_names = [m.name for m in openai_models]
        assert "gpt-provider-1" in openai_names
        assert "gpt-provider-2" in openai_names
        assert all(m.provider == LLMProvider.OPENAI for m in openai_models)

    def test_get_by_model_type(self, repo: LanguageModelRepository):
        """Test filtering models by type."""
        repo.create(provider=LLMProvider.OPENAI, name="gpt-type-fast", model_type=ModelType.FAST)
        repo.create(provider=LLMProvider.ANTHROPIC, name="claude-type-advanced", model_type=ModelType.ADVANCED)
        repo.create(provider=LLMProvider.GOOGLE, name="gemini-type-fast", model_type=ModelType.FAST)

        fast_models = repo.get_by_model_type(ModelType.FAST)
        fast_names = [m.name for m in fast_models]
        assert "gpt-type-fast" in fast_names
        assert "gemini-type-fast" in fast_names
        assert all(m.model_type == ModelType.FAST for m in fast_models)

    def test_update_model(self, repo: LanguageModelRepository):
        """Test updating fields on a language model."""
        model = repo.create(
            provider=LLMProvider.OPENAI,
            name="gpt-update-test",
            model_type=ModelType.STANDARD,
        )
        updated = repo.update(model, full_name="gpt-update-test-full", model_type=ModelType.ADVANCED)
        assert updated.full_name == "gpt-update-test-full"
        assert updated.model_type == ModelType.ADVANCED

    def test_delete_model(self, repo: LanguageModelRepository):
        """Test deleting a language model."""
        model = repo.create(
            provider=LLMProvider.OPENAI,
            name="gpt-delete-test",
            model_type=ModelType.FAST,
        )
        model_id = model.id
        result = repo.delete(model)
        assert result is True
        assert repo.get_by_id(model_id) is None

    def test_count(self, repo: LanguageModelRepository):
        """Test counting language models."""
        initial_count = repo.count()
        repo.create(provider=LLMProvider.OPENAI, name="gpt-count-1", model_type=ModelType.FAST)
        repo.create(provider=LLMProvider.OPENAI, name="gpt-count-2", model_type=ModelType.FAST)
        assert repo.count() == initial_count + 2

    def test_unique_constraint_provider_name(self, repo: LanguageModelRepository, db_session):
        """Test that duplicate (provider, name) pairs are rejected."""
        repo.create(provider=LLMProvider.OPENAI, name="gpt-unique", model_type=ModelType.STANDARD)
        db_session.flush()

        with pytest.raises(IntegrityError):
            repo.create(provider=LLMProvider.OPENAI, name="gpt-unique", model_type=ModelType.FAST)
            db_session.flush()

    def test_model_id_property(self, repo: LanguageModelRepository):
        """Test that model_id property returns correct provider:name format."""
        model = repo.create(
            provider=LLMProvider.ANTHROPIC,
            name="claude-haiku-4-5",
            model_type=ModelType.FAST,
        )
        assert model.model_id == "anthropic:claude-haiku-4-5"
