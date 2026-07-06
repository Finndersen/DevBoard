"""Abstract base class for agent roles.

Roles encapsulate agent behavior (system prompts, tools, context) independently
of execution engines (InternalAgent, ClaudeCodeAgent).
"""

from abc import ABC, abstractmethod

from pydantic_ai import Tool


class AgentRole(ABC):
    """Abstract base class defining agent behavior independent of execution engine.

    Roles encapsulate:
    - System prompts and behavioral guidelines
    - Tool definitions (in engine-agnostic PydanticAI format)
    - Context assembly logic

    The Role interface is engine-agnostic. Each agent engine (Internal/ClaudeCode)
    is responsible for converting the PydanticAI tools to their native format.
    """

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the complete system prompt for this role.

        Should include:
        - Role description and behavioral guidelines
        - Any role-specific instructions
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[Tool]:
        """Get tool definitions in engine-agnostic PydanticAI format.

        Returns:
            List of PydanticAI Tool objects.
            Each agent engine converts these to their native format:
            - InternalAgent uses them directly
            - ClaudeCodeAgent converts them to virtual tools (if requires approval)
              or function tools (if no approval required)
        """
        pass

    @abstractmethod
    async def get_context_content(self) -> str:
        """Get context content to be provided as initial user message.

        Should return formatted string containing:
        - Current state (task/project details, status, etc.)
        - Document content (specifications, plans, etc.)
        - Any other relevant context
        """
        pass

    def get_initial_instructions(self) -> str | None:
        """Per-conversation operational instructions injected once on the first message.

        Use for workflow steps, procedural guidance, and state-dependent instructions
        that vary per conversation but remain stable within one. Keeping these out of
        the system prompt allows the system prompt to stay static and benefit from
        prompt caching across all conversations of the same agent type.

        Returns None by default; roles override to provide instructions.
        """
        return None

    @property
    def event_context_types(self) -> list[str]:
        """Event types to auto-inject as context on each user message.

        Returns an empty list by default; roles override to opt in to event injection.
        """
        return []

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role.
        TODO: Maybe have a "write_allowed" flag or something instead of specifying tool names here"""
        return []

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Whether to include the built-in system prompt for the engine (e.g. built-in Claude Code prompt)."""
        return False

    @property
    def load_extra_mcp_servers(self) -> bool:
        """Whether to load Claude.ai connector plugins and user-level MCP servers.

        Sub-agent roles should override to False for a controlled, minimal tool environment.
        """
        return True
