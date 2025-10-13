"""Agent engine definitions and management.

This module defines the available agent engines (execution frameworks) and their
capabilities, following the pattern established in language_models.py.

An AgentEngine represents the underlying technology/framework that powers an agent
(e.g., PydanticAI, Claude Code, Gemini CLI), which is separate from the AgentRole
(role/purpose like PROJECT, TASK_SPECIFICATION, etc.).
"""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from devboard.agents.language_models import LLMProvider
from devboard.agents.roles.types import AgentRole


class AgentEngine(StrEnum):
    """Available agent execution engines."""

    INTERNAL = "internal"
    CLAUDE_CODE = "claude_code"
    GEMINI_CLI = "gemini_cli"


@dataclass
class AgentEngineDefinition:
    """Definition of an agent engine with its capabilities.

    Attributes:
        engine: The engine identifier
        display_name: Human-readable name for UI display
        description: Brief description of the engine's purpose
        available_provider: Single LLM provider this engine supports (None = all configured providers)
        supports_tool_approval: Whether engine requires explicit tool approval
        stores_messages_in_db: Whether messages are stored in database vs external
    """

    engine: AgentEngine
    display_name: str
    description: str
    available_provider: LLMProvider | None  # None means all configured providers


# Global registry of all engines with their capabilities
ALL_ENGINES: list[AgentEngineDefinition] = [
    AgentEngineDefinition(
        engine=AgentEngine.INTERNAL,
        display_name="Internal",
        description="Internal agent framework",
        available_provider=None,  # Supports all configured providers
    ),
    AgentEngineDefinition(
        engine=AgentEngine.CLAUDE_CODE,
        display_name="Claude Code",
        description="Anthropic's official CLI agent",
        available_provider=LLMProvider.ANTHROPIC,  # Only supports Anthropic models
    ),
    AgentEngineDefinition(
        engine=AgentEngine.GEMINI_CLI,
        display_name="Gemini CLI",
        description="Google's Gemini command-line interface",
        available_provider=LLMProvider.GOOGLE,  # Only supports Google models
    ),
]


# Engine restrictions by agent role
# PROJECT, SPECIFICATION, and PLANNING require tool approval (PydanticAI only)
# IMPLEMENTATION can use any external engine for full capabilities
# First engine in the list is the recommended one for each role
ALLOWED_ENGINES_BY_AGENT_ROLE: dict[AgentRole, list[AgentEngine]] = {
    AgentRole.PROJECT: [AgentEngine.INTERNAL],
    AgentRole.TASK_SPECIFICATION: [AgentEngine.INTERNAL, AgentEngine.CLAUDE_CODE],
    AgentRole.TASK_PLANNING: [AgentEngine.INTERNAL, AgentEngine.CLAUDE_CODE],
    AgentRole.TASK_IMPLEMENTATION: [AgentEngine.CLAUDE_CODE, AgentEngine.GEMINI_CLI],
    AgentRole.INVESTIGATION: [AgentEngine.INTERNAL],
}


class AgentEngineRepository:
    """Repository for querying agent engine capabilities."""

    def __init__(self, engines: list[AgentEngineDefinition]) -> None:
        """Initialize repository with engine definitions."""
        self._engines = {defn.engine: defn for defn in engines}

    def get_engine_definition(self, engine: AgentEngine) -> AgentEngineDefinition:
        """Get definition for a specific engine.

        Args:
            engine: The engine to get definition for

        Returns:
            AgentEngineDefinition for the engine

        Raises:
            ValueError: If engine is not found
        """
        if engine not in self._engines:
            raise ValueError(f"Unknown engine: {engine}")
        return self._engines[engine]

    def get_available_engines_for_agent_role(self, agent_role: AgentRole) -> list[AgentEngineDefinition]:
        """Get all engines allowed for a given agent role.

        Args:
            agent_role: The agent role to get allowed engines for

        Returns:
            List of AgentEngineDefinition instances allowed for the agent role
        """
        allowed = ALLOWED_ENGINES_BY_AGENT_ROLE.get(agent_role, [])
        return [self._engines[engine] for engine in allowed if engine in self._engines]

    def get_default_engine_for_agent_role(self, agent_role: AgentRole) -> AgentEngine:
        """Get recommended engine for a given agent role.

        Args:
            agent_role: The agent role to get recommendation for

        Returns:
            Recommended AgentEngine for the agent role
        """
        return ALLOWED_ENGINES_BY_AGENT_ROLE[agent_role][0]

    def validate_engine_for_agent_role(self, engine: AgentEngine, agent_role: AgentRole) -> bool:
        """Check if engine is allowed for given agent role.

        Args:
            engine: The engine to validate
            agent_role: The agent role to validate against

        Returns:
            True if engine is allowed for agent role, False otherwise
        """
        allowed = ALLOWED_ENGINES_BY_AGENT_ROLE.get(agent_role, [])
        return engine in allowed

    def get_available_provider_for_engine(self, engine: AgentEngine) -> LLMProvider | None:
        """Get the available provider for an engine.

        Args:
            engine: The engine to get provider for

        Returns:
            LLMProvider enum, or None if engine supports all providers
        """
        defn = self.get_engine_definition(engine)
        return defn.available_provider

    def get_all_engines(self) -> list[AgentEngineDefinition]:
        """Get all available engine definitions.

        Returns:
            List of all AgentEngineDefinition instances
        """
        return list(self._engines.values())


# Global default agent engine repository instance
default_agent_engine_repository = AgentEngineRepository(ALL_ENGINES)


class AgentEngineInfo(BaseModel):
    """Information about an agent engine.

    Attributes:
        engine: The agent execution engine value (e.g., "internal", "claude_code")
        display_name: Human-readable name for display in UI
        description: Description of what the engine does
    """

    engine: AgentEngine
    display_name: str
    description: str
