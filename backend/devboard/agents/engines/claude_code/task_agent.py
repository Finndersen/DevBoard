"""Task agents using Claude Code with virtual tool calling."""

import logging

from devboard.agents.engines.claude_code.base_agent import ClaudeCodeAgent
from devboard.agents.engines.claude_code.virtual_tools import (
    EditDocumentTool,
    SetDocumentContentTool,
    VirtualTool,
)
from devboard.agents.roles.task_planning import PLANNING_SYSTEM_PROMPT
from devboard.agents.roles.task_specification import SPECIFICATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ClaudeTaskSpecificationAgent(ClaudeCodeAgent):
    """Claude Code agent for task specification crafting."""

    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get the list of virtual tools for task specification agent.

        Returns appropriate tools based on document state.

        Returns:
            List of VirtualTool instances
        """
        tools: list[VirtualTool] = []

        # Specification document tools based on its state
        if not self.task.specification.content or not self.task.specification.content.strip():
            # Document is empty - provide set_content tool
            tools.append(
                SetDocumentContentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )
        else:
            # Document has content - provide edit tool
            tools.append(
                EditDocumentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        return tools

    def _get_role_description(self) -> str:
        """Get the role description for task specification agent.

        Returns:
            Role description string
        """
        return SPECIFICATION_SYSTEM_PROMPT

    def _get_state_context(self) -> str:
        """Get the current state/context for task specification agent.

        Returns:
            State/context string
        """
        return f"""
CURRENT STATE:
Task Name: {self.task.title}
Task Status: {self.task.status.value}

Task Specification Document (current live state):
```markdown
{self.task.specification.content or "<EMPTY>"}
```
"""


class ClaudeTaskPlanningAgent(ClaudeCodeAgent):
    """Claude Code agent for task planning and implementation plan creation."""

    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get the list of virtual tools for task planning agent.

        Returns appropriate tools based on document states.

        Returns:
            List of VirtualTool instances
        """
        tools: list[VirtualTool] = []

        # Specification document tools based on its state
        if not self.task.specification.content or not self.task.specification.content.strip():
            # Document is empty - provide set_content tool
            tools.append(
                SetDocumentContentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )
        else:
            # Document has content - provide edit tool
            tools.append(
                EditDocumentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        # Implementation plan document tools based on its state
        if not self.task.implementation_plan.content or not self.task.implementation_plan.content.strip():
            # Document is empty - provide set_content tool
            tools.append(
                SetDocumentContentTool(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )
        else:
            # Document has content - provide edit tool
            tools.append(
                EditDocumentTool(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )

        return tools

    def _get_role_description(self) -> str:
        """Get the role description for task planning agent.

        Returns:
            Role description string
        """
        return PLANNING_SYSTEM_PROMPT

    def _get_state_context(self) -> str:
        """Get the current state/context for task planning agent.

        Returns:
            State/context string
        """
        return f"""
CURRENT STATE:
Task Name: {self.task.title}
Task Status: {self.task.status.value}

Task Specification Document (current live state):
```markdown
{self.task.specification.content or "<EMPTY>"}
```

Task Implementation Plan Document (current live state):
```markdown
{self.task.implementation_plan.content or "<EMPTY>"}
```
"""
