"""Service for managing LLM providers and model availability."""

import logging
from typing import cast

from devboard.agents.language_models import LanguageModel, LLMProvider, llm_repository
from devboard.agents.types import AgentType
from devboard.api.schemas import ModelInfo
from devboard.config.agent_config import AgentConfig
from devboard.config.base import ConfigValidationResult
from devboard.services.config_service import ConfigService

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM provider management and testing."""

    def __init__(self, config_service: ConfigService):
        """Initialize LLMService with configuration service."""
        self.config_service = config_service
        self.repository = llm_repository

    def get_available_models(self) -> list[ModelInfo]:
        """Get all available models from configured providers.

        Returns:
            List of available models with provider information
        """
        available_models: list[ModelInfo] = []

        # Check which providers are configured and working
        working_providers: set[LLMProvider] = set()
        for provider_type in LLMProvider:
            config_key = f"llm.{provider_type.value}.main"
            config_result = self.config_service.validate_config_by_key(config_key)
            if config_result.success:
                working_providers.add(provider_type)

        # Get models from working providers using repository
        for model in self.repository.get_all_models():
            if model.provider in working_providers:
                available_models.append(
                    ModelInfo(
                        id=model.id,
                        provider=model.provider.value,
                        name=model.name,
                        model_type=model.type,
                    )
                )

        return available_models

    def get_preferred_model_for_agent(self, agent_type: AgentType) -> LanguageModel:
        """Get the preferred model for an agent based on configuration and availability.

        Args:
            agent_type: The agent type to get preferred model for

        Returns:
            Model ID if available, raises ValueError if no models available
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
            selected_model_id = config_result.config.selected_model
            if selected_model_id in available_model_ids:
                return llm_repository.get_model_by_id(selected_model_id)

        # Fall back to recommended model type for this agent
        recommended_type = self.repository.get_recommended_model_type_for_agent(agent_type)

        # Get available models of the recommended type
        for model_info in available_models:
            model = self.repository.get_model_by_id(model_info.id)
            if model and model.type == recommended_type:
                return model

        raise ValueError(f"Could not find model configuration for agent type '{agent_type}'")

    def set_agent_model(self, agent_type: AgentType, model_id: str | None) -> str:
        """Set the preferred model for an agent type.

        Args:
            agent_type: The agent type to update
            model_id: The model ID to set, or None to use default recommendations

        Returns:
            The effective model ID that will be used

        Raises:
            ValueError: If the specified model is not available or doesn't exist
        """
        # Validate that the model exists and is available if a specific one is requested
        if model_id is not None:
            # Check that the model exists in the repository
            model = self.repository.get_model_by_id(model_id)
            if model is None:
                raise ValueError(f"Model '{model_id}' does not exist")

            # Check that the model is available (provider is configured)
            available_models = self.get_available_models()
            available_model_ids = {model.id for model in available_models}

            if model_id not in available_model_ids:
                raise ValueError(f"Model '{model_id}' is not available (provider not configured)")

        # Update the agent configuration
        config_key = f"agent.{agent_type.value}.default"
        config_data = {"selected_model": model_id}
        self.config_service.update_configuration(config_key, config_data)

        return model_id
