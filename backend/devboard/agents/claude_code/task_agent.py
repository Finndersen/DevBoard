"""Task agents using Claude Code with virtual tool calling."""

import logging

from devboard.agents.claude_code.base_agent import BaseClaudeAgent
from devboard.agents.claude_code.virtual_tools import (
    EditDocumentTool,
    SetDocumentContentTool,
    VirtualTool,
)
from devboard.db.models.task import Task
from devboard.db.repositories.document import DocumentRepository

logger = logging.getLogger(__name__)


SPECIFICATION_SYSTEM_PROMPT = """
You are a Task Specification Assistant for DevBoard, helping developers craft detailed task specifications.

Your role is to help create or iteratively improve the Task Specification document (task description) based on:
- User input and requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Best practices for clear technical specifications

A task should correspond to an atomic piece of work, such as a specific feature, bug fix, or improvement.
The task specification should be clear, concise, and actionable. It should include:
- A clear, specific goal statement
- Detailed requirements and constraints
- Any relevant background information or context
- Any assumptions or limitations

BEHAVIOUR GUIDELINES:
- Discuss with the user to understand the task requirements and goals, and ask clarifying questions as needed in order to arrive at a mutual understanding, which you should articulate. Only then propose to make appropriate updates to the task specification.
- Identify and explore gaps or ambiguity in the task specification
- Raise potential issues or edge cases
- Suggest improvements or alternative approaches
- Challenge the user and be critical of ideas where appropriate
- Only make changes to the task specification when explicitly instructed by the user, or after asking and receiving confirmation.

Your responses should be concise, helpful, accurate, and focused on creating a clear, actionable specification.
"""


PLANNING_SYSTEM_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers create detailed implementation plans.

Your role is to help iteratively improve both the Task Specification and Implementation Plan based on:
- User input and technical requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Technical analysis and architecture understanding
- Best practices for implementation planning

DOCUMENT EDITING RULES:
1. Make precise find-replace edits using the edit tools
2. Use exact text matches for 'old_string' - the text must exist exactly as written
3. Preserve markdown formatting and structure
4. When adding new content, find a logical insertion point and replace with expanded content
5. For placeholder text like "[High-level approach]", replace the entire placeholder

CURRENT TASK STATE: Planning
AVAILABLE ACTIONS:
- Edit both Task Specification and Implementation Plan documents
- Research project context and codebase for technical details
- Suggest transition to Implementing state when plan is complete

Your responses should be technical, detailed, and focused on creating actionable implementation steps.
"""


class ClaudeTaskSpecificationAgent(BaseClaudeAgent):
    """Claude Code agent for task specification crafting."""

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize the task specification agent.

        Args:
            task: The task to work on
            document_repository: Repository for document operations
        """
        super().__init__(task, document_repository, plan_mode=True)

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


class ClaudeTaskPlanningAgent(BaseClaudeAgent):
    """Claude Code agent for task planning and implementation plan creation."""

    def __init__(self, task: Task, document_repository: DocumentRepository):
        """Initialize the task planning agent.

        Args:
            task: The task to work on
            document_repository: Repository for document operations
        """
        super().__init__(task, document_repository, plan_mode=True)

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
