"""Service for managing language model catalog operations."""

from typing import Any

from devboard.agents.language_models import LLMProvider, ModelType
from devboard.db.models.language_model import LanguageModelDB
from devboard.db.repositories.language_model import LanguageModelRepository


class DuplicateLanguageModelError(ValueError):
    """Raised when a language model with the same provider/name already exists."""


class LanguageModelService:
    """Service for language model CRUD operations with validation."""

    def __init__(self, repository: LanguageModelRepository):
        self.repository = repository

    def list_models(self) -> list[LanguageModelDB]:
        """Return all language models."""
        return self.repository.get_all()

    def get_model(self, model_id: int) -> LanguageModelDB | None:
        """Return a language model by its integer ID."""
        return self.repository.get_by_id(model_id)

    def create_model(
        self,
        provider: LLMProvider,
        name: str,
        model_type: ModelType,
        full_name: str | None = None,
        bedrock_id: str | None = None,
        context_window: int | None = None,
    ) -> LanguageModelDB:
        """Create a new language model after validating uniqueness.

        Raises:
            DuplicateLanguageModelError: If a model with the same provider+name exists.
        """
        existing = self.repository.get_by_model_id(f"{provider}:{name}")
        if existing is not None:
            raise DuplicateLanguageModelError(
                f"A language model with provider '{provider}' and name '{name}' already exists."
            )
        return self.repository.create(
            provider=provider,
            name=name,
            model_type=model_type,
            full_name=full_name,
            bedrock_id=bedrock_id,
            context_window=context_window,
        )

    def update_model(self, model_id: int, fields: dict[str, Any]) -> LanguageModelDB | None:
        """Update an existing language model.

        Args:
            model_id: The integer PK of the model to update.
            fields: Dict of field names to new values (only explicitly provided fields).

        Returns:
            Updated model, or None if not found.

        Raises:
            DuplicateLanguageModelError: If the new provider+name combination conflicts with another model.
        """
        model = self.repository.get_by_id(model_id)
        if model is None:
            return None

        new_provider = fields.get("provider", model.provider)
        new_name = fields.get("name", model.name)

        if new_provider != model.provider or new_name != model.name:
            existing = self.repository.get_by_model_id(f"{new_provider}:{new_name}")
            if existing is not None and existing.id != model.id:
                raise DuplicateLanguageModelError(
                    f"A language model with provider '{new_provider}' and name '{new_name}' already exists."
                )

        if fields:
            return self.repository.update(model, **fields)
        return model

    def delete_model(self, model_id: int) -> bool:
        """Delete a language model by ID.

        Returns:
            True if deleted, False if not found.
        """
        model = self.repository.get_by_id(model_id)
        if model is None:
            return False
        return self.repository.delete(model)
