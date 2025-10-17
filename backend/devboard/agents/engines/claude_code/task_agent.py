"""Task agents using Claude Code with virtual tool calling."""

from devboard.agents.engines.claude_code.base_agent import (
    ClaudeCodeAgent,
    create_set_document_content_function,
)
from devboard.agents.engines.claude_code.client import ClaudeCodeToolFunc
from devboard.agents.engines.claude_code.virtual_tools import (
    EditDocumentTool,
    SetDocumentContentTool,
    VirtualTool,
)
from devboard.agents.language_models import LanguageModel
from devboard.agents.roles.task_implementation import IMPLEMENTATION_SYSTEM_PROMPT, build_task_implementation_context
from devboard.agents.roles.task_planning import PLANNING_ROLE_PROMPT, build_task_planning_context
from devboard.agents.roles.task_specification import SPECIFICATION_ROLE_PROMPT, build_task_specification_context
from devboard.db.models.task import Task
from devboard.db.repositories.document import DocumentRepository


class ClaudeTaskSpecificationAgent(ClaudeCodeAgent):
    """Claude Code agent for task specification crafting."""

    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get the list of virtual tools for task specification agent.

        Provides edit tool always, and set_content tool only when document has content.

        Returns:
            List of VirtualTool instances
        """
        tools: list[VirtualTool] = [
            EditDocumentTool(
                document=self.task.specification,
                document_repo=self.document_repo,
            ),
        ]

        # Only provide virtual set_content tool if document has content (requires approval)
        if self.task.specification.content.strip():
            tools.append(
                SetDocumentContentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        return tools

    def _get_function_tools(self) -> list[ClaudeCodeToolFunc] | None:
        """Get regular function tools for task specification agent.

        Provides set_content function tool only for blank documents (no approval path).

        Returns:
            List of regular function tools or None
        """
        # Only provide no-approval function tool if document is blank
        if not self.task.specification.content.strip():
            return [
                create_set_document_content_function(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            ]

        return None

    def _get_role_description(self) -> str:
        """Get the role description for task specification agent.

        Returns:
            Role description string
        """
        return SPECIFICATION_ROLE_PROMPT

    def _get_state_context(self) -> str:
        """Get the current state/context for task specification agent.

        Returns:
            State/context string
        """
        return build_task_specification_context(self.task)


class ClaudeTaskPlanningAgent(ClaudeCodeAgent):
    """Claude Code agent for task planning and implementation plan creation."""

    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get the list of virtual tools for task planning agent.

        Provides edit tools always, and set_content tools only when documents have content.

        Returns:
            List of VirtualTool instances
        """
        tools: list[VirtualTool] = [
            EditDocumentTool(
                document=self.task.specification,
                document_repo=self.document_repo,
            ),
            EditDocumentTool(
                document=self.task.implementation_plan,
                document_repo=self.document_repo,
            ),
        ]

        # Only provide virtual set_content tool if specification has content (requires approval)
        if self.task.specification.content.strip():
            tools.append(
                SetDocumentContentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        # Only provide virtual set_content tool if plan has content (requires approval)
        if self.task.implementation_plan.content.strip():
            tools.append(
                SetDocumentContentTool(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )

        return tools

    def _get_function_tools(self) -> list[ClaudeCodeToolFunc] | None:
        """Get regular function tools for task planning agent.

        Provides set_content function tools only for blank documents (no approval path).

        Returns:
            List of regular function tools or None
        """
        tools: list[ClaudeCodeToolFunc] = []

        # Provide no-approval function tool for blank specification
        if not self.task.specification.content.strip():
            tools.append(
                create_set_document_content_function(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        # Provide no-approval function tool for blank implementation plan
        if not self.task.implementation_plan.content.strip():
            tools.append(
                create_set_document_content_function(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )

        return tools if tools else None

    def _get_role_description(self) -> str:
        """Get the role description for task planning agent.

        Returns:
            Role description string
        """
        return PLANNING_ROLE_PROMPT

    def _get_state_context(self) -> str:
        """Get the current state/context for task planning agent.

        Returns:
            State/context string
        """
        return build_task_planning_context(self.task)


class ClaudeImplementationAgent(ClaudeCodeAgent):
    """Claude Code agent for task implementation and code execution.

    This agent uses Claude Code's native Edit/Write tools for codebase changes,
    plus virtual tools for updating task documents. It operates in the codebase
    directory with full file editing capabilities.

    Requires the task to have an associated codebase.
    """

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        model: LanguageModel,
    ):
        """Initialize the implementation agent.

        Args:
            task: The task this agent is working on
            document_repository: Repository for document operations
            model: Language model instance
            plan_mode: Whether to enable plan mode in Claude Code

        Raises:
            ValueError: If task does not have an associated codebase
        """
        # Validate codebase exists before initializing
        if not task.codebase:
            raise ValueError(
                f"Task '{task.title}' (ID: {task.id}) must have an associated codebase for implementation agent"
            )

        # Initialize base agent (it will access task.codebase.local_path when creating client)
        super().__init__(
            task=task,
            document_repository=document_repository,
            model=model,
            include_builtin_system_prompt=True,
            include_claude_md=True,
        )

    def _get_virtual_tools(self) -> list[VirtualTool]:
        """Get virtual tools for editing task documents.

        Provides edit tools always, and set_content tools only when documents have content.

        Returns:
            List of VirtualTool instances
        """
        tools: list[VirtualTool] = [
            EditDocumentTool(
                document=self.task.specification,
                document_repo=self.document_repo,
            ),
        ]

        # Only provide virtual set_content tool if specification has content (requires approval)
        if self.task.specification.content.strip():
            tools.append(
                SetDocumentContentTool(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        # Add implementation plan tools if it exists
        if self.task.implementation_plan:
            tools.append(
                EditDocumentTool(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )

            # Only provide virtual set_content tool if plan has content (requires approval)
            if self.task.implementation_plan.content.strip():
                tools.append(
                    SetDocumentContentTool(
                        document=self.task.implementation_plan,
                        document_repo=self.document_repo,
                    )
                )

        return tools

    def _get_function_tools(self) -> list[ClaudeCodeToolFunc] | None:
        """Get regular function tools for implementation agent.

        Provides set_content function tools only for blank documents (no approval path).

        Returns:
            List of regular function tools or None
        """
        tools: list[ClaudeCodeToolFunc] = []

        # Provide no-approval function tool for blank specification
        if not self.task.specification.content.strip():
            tools.append(
                create_set_document_content_function(
                    document=self.task.specification,
                    document_repo=self.document_repo,
                )
            )

        # Provide no-approval function tool for blank implementation plan
        if self.task.implementation_plan and not self.task.implementation_plan.content.strip():
            tools.append(
                create_set_document_content_function(
                    document=self.task.implementation_plan,
                    document_repo=self.document_repo,
                )
            )

        return tools if tools else None

    def _get_role_description(self) -> str:
        """Get the role description for implementation agent.

        Returns:
            Role description string
        """
        return IMPLEMENTATION_SYSTEM_PROMPT

    def _get_state_context(self) -> str:
        """Get the current state/context for implementation agent.

        Returns:
            State/context string
        """
        return build_task_implementation_context(self.task)

    def _get_allowed_builtin_tools(self) -> list[str] | None:
        """Get allowed Claude Code tools for implementation agent.

        Extends base tools with Edit and Write for codebase modifications.

        Returns:
            List of allowed tool names
        """
        return [
            "Read",
            "Grep",
            "Glob",
            "Bash",
            "WebFetch",
            "WebSearch",
            "Edit",  # For editing existing files
            "Write",  # For creating new files
        ]
