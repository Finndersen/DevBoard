"""Service for managing agent engine and model configuration."""

from typing import cast

from pydantic import BaseModel

from devboard.agents.config_types import AgentEngineInfo, AgentEngineModelConfig, ModelInfo
from devboard.agents.engines.agent_engines import (
    AgentEngine,
    AgentEngineRegistry,
)
from devboard.agents.language_models import (
    LanguageModel,
    LLMProvider,
    LLMRegistry,
)
from devboard.agents.roles import AgentRoleType
from devboard.config.agent_config import AgentConfig
from devboard.config.base import ConfigValidationResult
from devboard.services.config_service import ConfigService


class AgentConfiguration(BaseModel):
    """Complete agent configuration including role, config, and available options.

    Attributes:
        agent_role: The agent role this configuration applies to
        config: Current effective engine and model configuration
        available_engines: List of engines available for this agent role
    """

    agent_role: AgentRoleType
    config: AgentEngineModelConfig
    available_engines: list[AgentEngineInfo]


class AvailableModelsByEngine(BaseModel):
    """All available models grouped by engine.

    Attributes:
        models_by_engine: Dictionary mapping engine names to lists of models
    """

    models_by_engine: dict[str, list[ModelInfo]]


class AgentConfigService:
    """Service for managing agent engine and model configuration.

    This service handles the configuration hierarchy:
    - Agent Role → Agent Engine → Model
    - Role-level defaults (stored in AgentConfig)
    - Conversation-level snapshots (stored on Conversation model)
    """

    def __init__(
        self,
        config_service: ConfigService,
        llm_registry: LLMRegistry,
        engine_registry: AgentEngineRegistry,
    ) -> None:
        """Initialize AgentConfigService.

        Args:
            config_service: Service for accessing configuration
            llm_registry: Registry for LLM/model information
            engine_registry: Registry for agent engine information
        """
        self.config_service = config_service
        self.llm_registry = llm_registry
        self.engine_registry = engine_registry

    def get_agent_configuration(self, agent_role: AgentRoleType) -> AgentConfiguration:
        """Get role-level configuration with effective config and available engines.

        Args:
            agent_role: The agent role to get configuration for

        Returns:
            AgentConfiguration with agent role, effective config, and available engines
        """
        # Get effective configuration
        effective_config = self.get_effective_config(agent_role)

        # Get available engines for this role, including availability status
        available_engines = []
        for defn in self.engine_registry.get_available_engines_for_agent_role(agent_role):
            is_available, unavailable_reason = self._check_engine_availability(defn.engine)
            available_engines.append(
                AgentEngineInfo(
                    engine=defn.engine,
                    display_name=defn.display_name,
                    description=defn.description,
                    requires_model_selection=defn.requires_model_selection,
                    is_available=is_available,
                    unavailable_reason=unavailable_reason,
                )
            )

        return AgentConfiguration(
            agent_role=agent_role,
            config=effective_config,
            available_engines=available_engines,
        )

    def get_available_models_by_engine(self) -> AvailableModelsByEngine:
        """Get all available models grouped by engine.

        Returns:
            AvailableModelsByEngine with models organized by engine
        """
        models_by_engine: dict[str, list[ModelInfo]] = {}

        for engine_def in self.engine_registry.get_all_engines():
            # Get models available for this engine
            engine_models = self._get_available_models_for_engine(engine_def.engine)

            # Convert to ModelInfo objects
            model_infos = [
                ModelInfo(
                    id=m.id,
                    provider=m.provider,
                    name=m.name,
                    model_type=m.type,
                )
                for m in engine_models
            ]

            models_by_engine[engine_def.engine.value] = model_infos

        return AvailableModelsByEngine(models_by_engine=models_by_engine)

    def update_agent_configuration(
        self,
        agent_role: AgentRoleType,
        config: AgentEngineModelConfig,
    ) -> AgentConfiguration:
        """Update role-level configuration.

        Validates:
        - Engine is allowed for agent role
        - Model is available for engine (provider configured)

        Args:
            agent_role: The agent role to update configuration for
            config: The new engine and model configuration

        Returns:
            Updated AgentConfiguration

        Raises:
            ValueError: If engine not allowed for role or model not available for engine
        """
        # Validate engine allowed for role
        if not self.engine_registry.validate_engine_for_agent_role(config.engine, agent_role):
            allowed_engines = self.engine_registry.get_available_engines_for_agent_role(agent_role)
            allowed_names = [e.engine.value for e in allowed_engines]
            raise ValueError(
                f"Engine '{config.engine.value}' not allowed for role '{agent_role.value}'. "
                f"Allowed engines: {', '.join(allowed_names)}"
            )

        # Get engine definition to check if model selection is required
        engine_def = self.engine_registry.get(config.engine)
        if engine_def is None:
            raise ValueError(f"Invalid engine: {config.engine}")

        # Validate model selection based on engine requirements
        if config.model_id is None:
            # None model_id is only allowed for engines that don't require selection
            if engine_def.requires_model_selection:
                raise ValueError(
                    f"Engine '{config.engine.value}' requires explicit model selection. "
                    f"Please select a model from the available options."
                )
        else:
            # If model_id is provided, validate it's available for the engine
            available_models = self._get_available_models_for_engine(config.engine)
            if not any(m.id == config.model_id for m in available_models):
                raise ValueError(
                    f"Model '{config.model_id}' not available for engine '{config.engine.value}'. "
                    f"Ensure the provider is configured."
                )

        # Update AgentConfig
        config_key = f"agent.{agent_role.value}.default"
        config_data = {
            "selected_engine": config.engine.value,
            "selected_model": config.model_id,
        }
        self.config_service.update_configuration(config_key, config_data)

        return self.get_agent_configuration(agent_role)

    def get_effective_config(self, agent_role: AgentRoleType) -> AgentEngineModelConfig:
        """Resolve effective engine and model from stored config or defaults.

        Args:
            agent_role: The agent role to resolve configuration for

        Returns:
            Effective configuration with resolved engine and model
        """
        # Get stored configuration
        config_key = f"agent.{agent_role.value}.default"
        config_result = cast(
            ConfigValidationResult[AgentConfig],
            self.config_service.validate_config_by_key(config_key),
        )
        config = config_result.config if config_result.success else None

        # Resolve engine (selected or default)
        effective_engine = (
            config.selected_engine
            if config and config.selected_engine
            else self.engine_registry.get_default_engine_for_agent_role(agent_role)
        )

        # Resolve model (selected or default for agent role + engine)
        effective_model = (
            config.selected_model
            if config and config.selected_model
            else self._get_default_model_for_agent_role_and_engine(agent_role, effective_engine)
        )

        return AgentEngineModelConfig(
            engine=effective_engine,
            model_id=effective_model,
        )

    def _get_available_models_for_engine(self, engine: AgentEngine) -> list[LanguageModel]:
        """Get models available for a specific engine.

        For INTERNAL engine:
        - Returns models from all configured providers (filters by API key)

        For external engines (CLAUDE_CODE, GEMINI_CLI):
        - Returns all models from engine's supported provider
        - No API key filtering (these engines manage auth themselves)

        Args:
            engine: The engine to get available models for

        Returns:
            List of LanguageModel objects available for the engine
        """
        if engine == AgentEngine.INTERNAL:
            # For INTERNAL engine, return all configured models (API key check)
            # None means all providers are supported
            return self._get_all_available_internal_models()
        else:
            # Get engine's supported provider
            engine_def = self.engine_registry.get(engine)
            if engine_def is None:
                raise ValueError(f"Invalid engine: {engine}")
            # For external engines, return all models from the specific provider
            # (no API key filtering - these engines manage auth themselves)
            if engine_def.available_provider is None:
                # Engine supports all providers (unlikely for external engines)
                return self.llm_registry.get_all_models()
            else:
                # Return models from the specific provider
                return self.llm_registry.get_models_for_provider(engine_def.available_provider)

    def _get_all_available_internal_models(self) -> list[LanguageModel]:
        """Get all models from configured providers for the internal engine.

        Returns:
            List of LanguageModel objects from all configured providers
        """
        # Check which providers are configured
        working_providers: set[LLMProvider] = set()
        for provider_type in LLMProvider:
            config_key = f"llm.{provider_type.value}.main"
            if self.config_service.validate_config_by_key(config_key).success:
                working_providers.add(provider_type)

        # Return models from working providers
        return [model for model in self.llm_registry.get_all_models() if model.provider in working_providers]

    def _check_engine_availability(self, engine: AgentEngine) -> tuple[bool, str | None]:
        """Check if an engine is available for use.

        Args:
            engine: The engine to check availability for

        Returns:
            Tuple of (is_available, unavailable_reason). If available, reason is None.
        """
        if engine == AgentEngine.INTERNAL:
            available_models = self._get_all_available_internal_models()
            if not available_models:
                return False, "No LLM providers configured. Add an API key in Settings."
        return True, None

    def _get_default_model_for_agent_role_and_engine(
        self, agent_role: AgentRoleType, engine: AgentEngine
    ) -> str | None:
        """Get default model for an agent role and engine.

        Selects the first available model of the recommended type for the agent role.
        For engines that don't require model selection, returns None (use engine default).

        Args:
            agent_role: The agent role to get default model for
            engine: The engine to get default model for

        Returns:
            Model ID in "provider:model" format, or None if engine doesn't require selection

        Raises:
            ValueError: If no models are available for an engine that requires selection
        """
        # Get engine definition to check if model selection is required
        engine_def = self.engine_registry.get(engine)
        if engine_def is None:
            raise ValueError(f"Invalid engine: {engine}")

        # If engine doesn't require model selection, return None (use engine default)
        if not engine_def.requires_model_selection:
            return None

        # Get available models for this engine
        available = self._get_available_models_for_engine(engine)
        if not available:
            raise ValueError(
                f"No models available for engine '{engine.value}'. Ensure at least one provider is configured."
            )

        # Get recommended model type for this agent role
        recommended_type = self.llm_registry.get_recommended_model_type_for_agent(agent_role)

        # Try to find a model of the recommended type
        for model in available:
            if model.type == recommended_type:
                return model.id

        # If no model of recommended type found, return first available model
        return available[0].id
