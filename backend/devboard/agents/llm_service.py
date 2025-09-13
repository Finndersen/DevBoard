"""Service for managing LLM providers and model availability."""

import logging
from dataclasses import dataclass
from typing import cast

from devboard.agents.types import AgentType
from devboard.config.agent_config import AgentConfig
from devboard.config.base import ConfigValidationResult
from devboard.config.llm_config import AGENT_MODEL_HIERARCHIES, PROVIDER_MODELS
from devboard.services.config_service import ConfigService

logger = logging.getLogger(__name__)


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

    def __init__(self, config_service: ConfigService):
        """Initialize LLMService with configuration service."""
        self.config_service = config_service

    def get_available_models(self) -> list[ModelInfo]:
        """Get all available models from configured providers.

        Returns:
            List of available models with provider information
        """
        available_models: list[ModelInfo] = []

        # Check which providers are configured and working
        working_providers: list[str] = []
        for provider_type in ["openai", "anthropic", "gemini"]:
            config_key = f"llm.{provider_type}.main"
            config_result = self.config_service.validate_config_by_key(config_key)
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

    def get_preferred_model_for_agent(self, agent_type: AgentType) -> str:
        """Get the preferred model for an agent based on configuration and availability.

        Args:
            agent_type: The agent type to get preferred model for

        Returns:
            Model ID if available, None if no models available
        """
        # Get agent configuration
        config_key = f"agent.{agent_type.value}.default"
        config_result = cast(
            ConfigValidationResult[AgentConfig],
            self.config_service.validate_config_by_key(config_key),
        )

        # Get available models
        available_models = self.get_available_models()
        available_model_ids = {model.id for model in available_models}

        # If user has selected a specific model and it's available, use that
        if config_result.success and config_result.config.selected_model:
            if config_result.config.selected_model in available_model_ids:
                return config_result.config.selected_model

        # Fall back to hardcoded hierarchy
        hierarchy = AGENT_MODEL_HIERARCHIES.get(agent_type, [])
        for model_id in hierarchy:
            if model_id in available_model_ids:
                return model_id

        raise ValueError(f"Could not find model configuration for agent type '{agent_type}'")
