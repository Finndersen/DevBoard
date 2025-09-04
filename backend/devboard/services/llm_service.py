"""Service for managing LLM providers and model availability."""

import logging
from dataclasses import dataclass
from enum import Enum

from devboard.config.llm_config import AGENT_MODEL_HIERARCHIES, PROVIDER_MODELS
from devboard.services.config_service import config_service

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Available agent types in the system."""

    QA = "qa"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    INVESTIGATION = "investigation"


@dataclass
class ModelInfo:
    """Information about an available LLM model."""

    provider: str  # Provider name (e.g., "openai")
    name: str  # Model name (e.g., "gpt-4.1")

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.name}"


class LLMService:
    """Service for LLM provider management and testing."""

    def get_available_models(self) -> list[ModelInfo]:
        """Get all available models from configured providers.

        Returns:
            List of available models with provider information
        """
        available_models = []

        # Check which providers are configured and working
        working_providers = []
        for provider_type in ["openai", "anthropic", "google"]:
            config_key = f"llm.{provider_type}.main"
            config_result = config_service.validate_config(config_key)
            if config_result.success:
                working_providers.append(provider_type)

        # Get models from working providers
        for provider_type in working_providers:
            provider_models = PROVIDER_MODELS.get(provider_type, [])
            for model_name in provider_models:
                available_models.append(
                    ModelInfo(
                        provider=provider_type,
                        name=model_name,
                    )
                )

        return available_models

    def get_preferred_model_for_agent(self, agent_type: AgentType) -> str | None:
        """Get the preferred model for an agent based on configuration and availability.

        Args:
            agent_type: The agent type to get preferred model for

        Returns:
            Model ID if available, None if no models available
        """
        # Get agent configuration
        config_key = f"agent.{agent_type.value}.default"
        config_result = config_service.validate_config(config_key)

        # Get available models
        available_models = self.get_available_models()
        available_model_ids = {model.id for model in available_models}

        # If user has selected a specific model and it's available, use that
        if config_result.success and config_result.config.selected_model:
            if config_result.config.selected_model in available_model_ids:
                return config_result.config.selected_model

        # Fall back to hardcoded hierarchy
        hierarchy = AGENT_MODEL_HIERARCHIES.get(agent_type.value, [])
        for model_id in hierarchy:
            if model_id in available_model_ids:
                return model_id

        return None


# Global LLM service instance
llm_service = LLMService()
