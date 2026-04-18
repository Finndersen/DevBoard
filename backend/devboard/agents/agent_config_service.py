"""Service for managing agent engine and model configuration."""

import logfire
from pydantic import BaseModel

from devboard.agents.config_types import AgentEngineInfo, AgentEngineModelConfig, AgentEngineModelInput, ModelInfo
from devboard.agents.engines.agent_engines import (
    AgentEngine,
    AgentEngineRegistry,
)
from devboard.agents.language_models import (
    RECOMMENDED_AGENT_MODEL_TYPES,
    LLMProvider,
    ModelType,
)
from devboard.agents.roles import AgentRoleType
from devboard.api.schemas.agents import MCPToolSummary
from devboard.db.models import MCPTool
from devboard.db.models.language_model import LanguageModelDB
from devboard.db.repositories import AgentRoleConfigRepository
from devboard.db.repositories.language_model import LanguageModelRepository
from devboard.services.config_service import ConfigService


class AgentConfiguration(BaseModel):
    """Complete agent configuration including role, config, and available options.

    Attributes:
        agent_role: The agent role this configuration applies to
        config: Current effective engine and model configuration
        custom_instructions: User-defined instructions appended to system prompt
        available_engines: List of engines available for this agent role
        enabled_mcp_tools: List of MCP tools assigned to this agent role
    """

    agent_role: AgentRoleType
    config: AgentEngineModelConfig
    custom_instructions: str | None = None
    available_engines: list[AgentEngineInfo]
    enabled_mcp_tools: list[MCPToolSummary] = []


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
    - Role-level defaults (stored in AgentRoleConfig)
    - Custom instructions and MCP tool assignments
    """

    def __init__(
        self,
        agent_role_config_repo: AgentRoleConfigRepository,
        config_service: ConfigService,
        language_model_repo: LanguageModelRepository,
        engine_registry: AgentEngineRegistry,
    ) -> None:
        """Initialize AgentConfigService.

        Args:
            agent_role_config_repo: Repository for agent role configuration
            config_service: Service for accessing LLM provider configuration
            language_model_repo: Repository for language model data
            engine_registry: Registry for agent engine information
        """
        self._agent_role_config_repo = agent_role_config_repo
        self._config_service = config_service
        self._language_model_repo = language_model_repo
        self._engine_registry = engine_registry

    def get_agent_configuration(self, agent_role: AgentRoleType) -> AgentConfiguration:
        """Get role-level configuration with effective config and available engines.

        Args:
            agent_role: The agent role to get configuration for

        Returns:
            AgentConfiguration with agent role, effective config, and available engines
        """
        # Get effective configuration
        effective_config = self.get_effective_config(agent_role)

        # Get custom instructions from role config
        role_config = self._agent_role_config_repo.get_or_create(agent_role)
        custom_instructions = role_config.custom_instructions

        # Get available engines for this role, including availability status
        available_engines = []
        for defn in self._engine_registry.get_available_engines_for_agent_role(agent_role):
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

        # Get enabled MCP tools for this role
        mcp_tools = self._agent_role_config_repo.get_enabled_tools(agent_role)
        enabled_mcp_tools = [
            MCPToolSummary(
                tool_id=tool.id,
                tool_name=tool.name,
                server_name=tool.server.name,
                description=tool.description,
            )
            for tool in mcp_tools
        ]

        return AgentConfiguration(
            agent_role=agent_role,
            config=effective_config,
            custom_instructions=custom_instructions,
            available_engines=available_engines,
            enabled_mcp_tools=enabled_mcp_tools,
        )

    def get_available_models_by_engine(self) -> AvailableModelsByEngine:
        """Get all available models grouped by engine.

        Returns:
            AvailableModelsByEngine with models organized by engine
        """
        models_by_engine: dict[str, list[ModelInfo]] = {}

        for engine_def in self._engine_registry.get_all_engines():
            # Get models available for this engine
            engine_models = self._get_available_models_for_engine(engine_def.engine)

            # Convert to ModelInfo objects
            model_infos = [
                ModelInfo(
                    id=m.model_id,
                    provider=m.provider,
                    name=m.name,
                    model_type=m.model_type,
                )
                for m in engine_models
            ]

            models_by_engine[engine_def.engine.value] = model_infos

        return AvailableModelsByEngine(models_by_engine=models_by_engine)

    def update_agent_configuration(
        self,
        agent_role: AgentRoleType,
        config: AgentEngineModelInput,
        custom_instructions: str | None = None,
    ) -> AgentConfiguration:
        """Update role-level configuration.

        Validates:
        - Engine is allowed for agent role
        - Model is available for engine (provider configured)

        Args:
            agent_role: The agent role to update configuration for
            config: The new engine and model configuration
            custom_instructions: Optional custom instructions to set

        Returns:
            Updated AgentConfiguration

        Raises:
            ValueError: If engine not allowed for role or model not available for engine
        """
        # Validate engine allowed for role
        if not self._engine_registry.validate_engine_for_agent_role(config.engine, agent_role):
            allowed_engines = self._engine_registry.get_available_engines_for_agent_role(agent_role)
            allowed_names = [e.engine.value for e in allowed_engines]
            raise ValueError(
                f"Engine '{config.engine.value}' not allowed for role '{agent_role.value}'. "
                f"Allowed engines: {', '.join(allowed_names)}"
            )

        # Get engine definition to check if model selection is required
        engine_def = self._engine_registry.get(config.engine)
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
            if not any(m.model_id == config.model_id for m in available_models):
                raise ValueError(
                    f"Model '{config.model_id}' not available for engine '{config.engine.value}'. "
                    f"Ensure the provider is configured."
                )

        # Update engine and model
        role_config = self._agent_role_config_repo.get_or_create(agent_role)
        role_config.engine = config.engine
        role_config.model_id = config.model_id
        role_config.custom_instructions = custom_instructions
        self._agent_role_config_repo.update(role_config)

        return self.get_agent_configuration(agent_role)

    def update_custom_instructions(
        self,
        agent_role: AgentRoleType,
        custom_instructions: str | None,
    ) -> AgentConfiguration:
        """Update custom instructions for a role.

        Args:
            agent_role: The agent role to update
            custom_instructions: Custom instructions text (None to clear)

        Returns:
            Updated AgentConfiguration
        """
        role_config = self._agent_role_config_repo.get_or_create(agent_role)
        role_config.custom_instructions = custom_instructions
        self._agent_role_config_repo.update(role_config)
        return self.get_agent_configuration(agent_role)

    def get_enabled_mcp_tools(self, agent_role: AgentRoleType) -> list[MCPTool]:
        """Get enabled MCP tools for a role.

        Args:
            agent_role: The agent role to get tools for

        Returns:
            List of enabled MCPTool instances
        """
        return self._agent_role_config_repo.get_enabled_tools(agent_role)

    def add_mcp_tool(self, agent_role: AgentRoleType, tool_id: int) -> None:
        """Add an MCP tool to a role's enabled tools.

        Args:
            agent_role: The agent role to add the tool to
            tool_id: The ID of the MCP tool to add
        """
        config = self._agent_role_config_repo.get_or_create(agent_role)
        self._agent_role_config_repo.add_mcp_tool(config.id, tool_id)

    def remove_mcp_tool(self, agent_role: AgentRoleType, tool_id: int) -> None:
        """Remove an MCP tool from a role's enabled tools.

        Args:
            agent_role: The agent role to remove the tool from
            tool_id: The ID of the MCP tool to remove
        """
        config = self._agent_role_config_repo.get_or_create(agent_role)
        self._agent_role_config_repo.remove_mcp_tool(config.id, tool_id)

    def get_effective_config(self, agent_role: AgentRoleType) -> AgentEngineModelConfig:
        """Resolve effective engine and model from stored config or defaults.

        Args:
            agent_role: The agent role to resolve configuration for

        Returns:
            Effective configuration with resolved engine and model
        """
        # Get stored configuration from AgentRoleConfig
        role_config = self._agent_role_config_repo.get_or_create(agent_role)

        # Resolve engine (selected or default)
        effective_engine = (
            role_config.engine
            if role_config.engine
            else self._engine_registry.get_default_engine_for_agent_role(agent_role)
        )

        # Resolve model ID (selected or default for agent role + engine)
        effective_model_id = (
            role_config.model_id
            if role_config.model_id
            else self._get_default_model_for_agent_role_and_engine(agent_role, effective_engine)
        )

        resolved_model: LanguageModelDB | None = None
        if effective_model_id:
            resolved_model = self._language_model_repo.get_by_model_id(effective_model_id)

        return AgentEngineModelConfig(
            engine=effective_engine,
            model=resolved_model,
        )

    def _get_available_models_for_engine(self, engine: AgentEngine) -> list[LanguageModelDB]:
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
            engine_def = self._engine_registry.get(engine)
            if engine_def is None:
                raise ValueError(f"Invalid engine: {engine}")
            # For external engines, return all models from the specific provider
            # (no API key filtering - these engines manage auth themselves)
            if engine_def.available_provider is None:
                # Engine supports all providers (unlikely for external engines)
                return self._language_model_repo.get_all()
            else:
                # Return models from the specific provider
                return self._language_model_repo.get_by_provider(engine_def.available_provider)

    def _get_all_available_internal_models(self) -> list[LanguageModelDB]:
        """Get all models from configured providers for the internal engine.

        Returns:
            List of LanguageModel objects from all configured providers
        """
        # Check which providers are configured
        working_providers: set[LLMProvider] = set()
        for provider_type in LLMProvider:
            config_key = f"llm.{provider_type.value}.main"
            if self._config_service.validate_config_by_key(config_key).success:
                working_providers.add(provider_type)

        # Return models from working providers
        return [m for m in self._language_model_repo.get_all() if m.provider in working_providers]

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

    def get_model_by_id(self, model_id: str) -> LanguageModelDB | None:
        return self._language_model_repo.get_by_model_id(model_id)

    def get_model_id_for_type(self, model_type: ModelType, engine: AgentEngine) -> str | None:
        """Resolve the model ID for a given model type and engine.

        Finds the first available model of the requested type for the engine.

        Returns:
            Model ID in "provider:model" format, or None if no models are available for the engine
        """
        engine_def = self._engine_registry.get(engine)
        if engine_def is None:
            raise ValueError(f"Invalid engine: {engine}")

        available = self._get_available_models_for_engine(engine)
        if not available:
            if engine_def.requires_model_selection:
                raise ValueError(
                    f"No models available for engine '{engine.value}'. Ensure at least one provider is configured."
                )
            return None

        for model in available:
            if model.model_type == model_type:
                return model.model_id

        # Fallback to first available model if no match for requested type
        logfire.warn(
            "No model found for requested type, falling back to first available",
            requested_type=model_type,
            engine=engine.value,
            fallback_model=available[0].model_id,
        )
        return available[0].model_id

    def get_model_display_name(self, model_type: ModelType, role_type: AgentRoleType) -> str | None:
        """Resolve the display name for a model type as it would be used for a given role.

        Gets the effective engine for the role, resolves the model_id for the requested type,
        and extracts the model name from the "provider:model_name" format.
        """
        config = self.get_effective_config(role_type)
        model_id = self.get_model_id_for_type(model_type, config.engine)
        if model_id is None:
            return None
        return model_id.split(":", 1)[1] if ":" in model_id else model_id

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
        engine_def = self._engine_registry.get(engine)
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
        recommended_type = RECOMMENDED_AGENT_MODEL_TYPES[agent_role]

        # Try to find a model of the recommended type
        for model in available:
            if model.model_type == recommended_type:
                return model.model_id

        # If no model of recommended type found, return first available model
        return available[0].model_id
