"""Abstract base class for agent roles.

Roles encapsulate agent behavior (system prompts, tools, context) independently
of execution engines (InternalAgent, ClaudeCodeAgent).
"""

from abc import ABC, abstractmethod

from pydantic_ai import Tool


class Role(ABC):
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
