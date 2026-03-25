"""Language model repository for data access operations."""

from typing import Any

from sqlalchemy import func, select

from devboard.agents.language_models import LLMProvider, ModelType
from devboard.db.models.language_model import LanguageModelDB
from devboard.db.repositories.base import BaseRepository


class LanguageModelRepository(BaseRepository[LanguageModelDB]):
    """Repository for language model data access operations."""

    def get_all(self) -> list[LanguageModelDB]:
        """Get all language models.

        Returns:
            List of all LanguageModelDB instances
        """
        stmt = select(LanguageModelDB)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, model_id: int) -> LanguageModelDB | None:
        """Get a language model by its integer ID.

        Args:
            model_id: The integer primary key

        Returns:
            LanguageModelDB instance if found, None otherwise
        """
        stmt = select(LanguageModelDB).where(LanguageModelDB.id == model_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_model_id(self, model_id: str) -> LanguageModelDB | None:
        """Get a language model by its provider:name string identifier.

        Args:
            model_id: String in format "provider:name" (e.g. "anthropic:claude-sonnet-4")

        Returns:
            LanguageModelDB instance if found, None otherwise
        """
        if ":" not in model_id:
            return None
        provider_str, name = model_id.split(":", 1)
        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            return None
        stmt = select(LanguageModelDB).where(
            LanguageModelDB.provider == provider,
            LanguageModelDB.name == name,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_provider(self, provider: LLMProvider) -> list[LanguageModelDB]:
        """Get all language models for a specific provider.

        Args:
            provider: The LLM provider to filter by

        Returns:
            List of LanguageModelDB instances for the provider
        """
        stmt = select(LanguageModelDB).where(LanguageModelDB.provider == provider)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_model_type(self, model_type: ModelType) -> list[LanguageModelDB]:
        """Get all language models of a specific type.

        Args:
            model_type: The model type to filter by

        Returns:
            List of LanguageModelDB instances matching the type
        """
        stmt = select(LanguageModelDB).where(LanguageModelDB.model_type == model_type)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        provider: LLMProvider,
        name: str,
        model_type: ModelType,
        full_name: str | None = None,
        bedrock_id: str | None = None,
        context_window: int | None = None,
    ) -> LanguageModelDB:
        """Create a new language model.

        Args:
            provider: The LLM provider
            name: The model name
            model_type: The model type (fast/standard/advanced)
            full_name: Optional full model identifier for external engines
            bedrock_id: Optional Bedrock model inference profile

        Returns:
            Newly created LanguageModelDB instance
        """
        model = LanguageModelDB(
            provider=provider,
            name=name,
            model_type=model_type,
            full_name=full_name,
            bedrock_id=bedrock_id,
            context_window=context_window,
        )
        self.db.add(model)
        self.db.flush()
        return model

    def update(self, model: LanguageModelDB, **fields: Any) -> LanguageModelDB:
        """Update fields on an existing language model.

        Args:
            model: The LanguageModelDB instance to update
            **fields: Field names and new values to update

        Returns:
            Updated LanguageModelDB instance
        """
        for key, value in fields.items():
            setattr(model, key, value)
        self.db.flush()
        return model

    def delete(self, model: LanguageModelDB) -> bool:
        """Delete a language model.

        Args:
            model: The LanguageModelDB instance to delete

        Returns:
            True after deletion
        """
        self.db.delete(model)
        self.db.flush()
        return True

    def count(self) -> int:
        """Count the total number of language models.

        Returns:
            Total count of language models in the database
        """
        stmt = select(func.count()).select_from(LanguageModelDB)
        result = self.db.execute(stmt).scalar_one()
        return result
