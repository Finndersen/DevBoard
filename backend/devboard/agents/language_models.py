from dataclasses import dataclass
from enum import StrEnum

from devboard.agents.types import AgentType


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelType(StrEnum):
    """Types of language models."""

    REASONING = "reasoning"
    FAST = "fast"


@dataclass
class LanguageModel:
    provider: LLMProvider
    name: str
    type: ModelType

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.name}"


# Define all available language models with capability classification
ALL_MODELS = [
    # OpenAI Models
    LanguageModel(provider=LLMProvider.OPENAI, name="gpt-5", type=ModelType.REASONING),
    LanguageModel(provider=LLMProvider.OPENAI, name="gpt-4.1", type=ModelType.REASONING),
    LanguageModel(provider=LLMProvider.OPENAI, name="gpt-5-mini", type=ModelType.FAST),
    LanguageModel(provider=LLMProvider.OPENAI, name="gpt-5-nano", type=ModelType.FAST),
    # Anthropic Models
    LanguageModel(
        provider=LLMProvider.ANTHROPIC,
        name="claude-sonnet-4-0",
        type=ModelType.REASONING,
    ),
    LanguageModel(provider=LLMProvider.ANTHROPIC, name="claude-opus-4-1", type=ModelType.REASONING),
    LanguageModel(
        provider=LLMProvider.ANTHROPIC,
        name="claude-3-7-sonnet-latest",
        type=ModelType.REASONING,
    ),
    LanguageModel(
        provider=LLMProvider.ANTHROPIC,
        name="claude-3-5-haiku-latest",
        type=ModelType.FAST,
    ),
    # Google Models
    LanguageModel(provider=LLMProvider.GOOGLE, name="gemini-2.5-pro", type=ModelType.REASONING),
    LanguageModel(provider=LLMProvider.GOOGLE, name="gemini-2.5-flash", type=ModelType.FAST),
    LanguageModel(provider=LLMProvider.GOOGLE, name="gemini-2.5-flash-lite", type=ModelType.FAST),
]


class LLMRepository:
    """Repository for managing language model definitions and queries."""

    def __init__(self, models: list[LanguageModel]) -> None:
        """Initialize repository with language models."""
        self._models = {model.id: model for model in models}

    def get_model_by_id(self, model_id: str) -> LanguageModel:
        """Get a language model by its ID.

        Args:
            model_id: Model ID in format "provider:model_name"

        Returns:
            LanguageModel instance or None if not found
        """
        if model_id not in self._models:
            raise ValueError(f"Model ID '{model_id}' not found.")
        return self._models[model_id]

    def get_models_by_type(self, model_type: ModelType) -> list[LanguageModel]:
        """Get all models of a specific type.

        Args:
            model_type: The model type to filter by

        Returns:
            List of LanguageModel instances matching the type
        """
        return [model for model in self._models.values() if model.type == model_type]

    def get_models_for_provider(self, provider: LLMProvider) -> list[LanguageModel]:
        """Get all models for a specific provider.

        Args:
            provider: The LLM provider to filter by

        Returns:
            List of LanguageModel instances for the provider
        """
        return [model for model in self._models.values() if model.provider == provider]

    def get_all_models(self) -> list[LanguageModel]:
        """Get all available language models.

        Returns:
            List of all LanguageModel instances
        """
        return list(self._models.values())

    def get_recommended_model_type_for_agent(self, agent_type: AgentType) -> ModelType:
        """Get the recommended model type for an agent type.

        Args:
            agent_type: The agent type to get recommendation for

        Returns:
            Recommended ModelType for the agent
        """
        return RECOMMENDED_AGENT_MODEL_TYPES.get(agent_type, ModelType.REASONING)


# Recommended model types for different agent types
RECOMMENDED_AGENT_MODEL_TYPES = {
    AgentType.PROJECT: ModelType.REASONING,
    AgentType.TASK_SPECIFICATION: ModelType.REASONING,
    AgentType.TASK_PLANNING: ModelType.REASONING,
    AgentType.TASK_IMPLEMENTATION: ModelType.REASONING,
    AgentType.INVESTIGATION: ModelType.FAST,
}
# Global default LLM repository instance
default_llm_repository = LLMRepository(ALL_MODELS)
