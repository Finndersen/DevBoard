"""Role for managing tasks in PR_OPEN state."""

from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.roles.task_base import TaskAgentRoleBase
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_get_pr_feedback_tool,
    create_get_pr_status_tool,
    create_merge_pr_and_finalise_tool,
)
from devboard.db.models import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.global_context_service import GlobalContextService
from devboard.services.task_service import TaskService

PR_REVIEW_ROLE_PROMPT = """
You are a Task Management Assistant for DevBoard, helping a developer manage the current task which has an open Pull Request.

Your role is to:
- Respond to PR review feedback and make requested code changes
- Make additional changes requested by the user
- Handle workflow actions like rebasing, pushing updates, etc.
- Create clear commits for each logical change

AVAILABLE CAPABILITIES:
1. PR STATUS: Use get_pr_status tool to check PR state, CI status, and review decision
2. PR READING: Use get_pr_feedback tool to fetch all PR reviews and code comments
3. CODEBASE EDITING: Use Edit/Write tools to modify code files
4. INVESTIGATION: Read files, search code, run bash commands for testing
5. GIT OPERATIONS: Commit, push, rebase as needed

IMPORTANT:
- Work incrementally with focused, atomic commits
- When addressing reviewer comments, be systematic and thorough
- Keep changes minimal and targeted
- Always test changes before committing
- After completing changes, provide a VERY BRIEF summary
- When creating commits, DO NOT add Claude Code attribution messages
"""


def build_task_pr_review_context(task: Task, *, working_dir: str, global_context: str | None = None) -> str:
    """Build context for PR review agent."""
    return build_task_context(task, working_dir=working_dir, global_context=global_context, include_step_outcomes=True)


class TaskPRReviewAgentRole(TaskAgentRoleBase):
    """Role for managing tasks in PR_OPEN state."""

    def __init__(
        self,
        task: Task,
        task_service: TaskService,
        github_integration: GitHubIntegration,
        working_dir: str,
        conversation_repo: ConversationRepository,
        agent_config_service: AgentConfigService,
        conversation_id: int | None,
    ):
        if not task.github_pr_number:
            raise ValueError("Task does not have a github_pr_number set")
        if not task.codebase.repository_url:
            raise ValueError("Task codebase does not have a repository_url set")

        super().__init__(
            task=task,
            task_service=task_service,
            conversation_repo=conversation_repo,
            conversation_id=conversation_id,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
        )
        self.github_integration = github_integration

    @property
    def event_context_types(self) -> list[str]:
        return ["task.merged"]

    def get_system_prompt(self) -> str:
        """Get the system prompt for PR review role."""
        return PR_REVIEW_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for PR review role.

        Returns:
            Common task tools plus PR reading tools, codebase exploration tools, and task completion tool.
            Note: Codebase editing tools (Edit/Write) are provided directly by the
            underlying agent (ClaudeCode), not through this role.
        """
        codebase_integration = CodebaseIntegration(self.working_dir)

        tools = super().get_tools()
        tools.extend(
            [
                create_get_pr_status_tool(self.task, self.github_integration),
                create_get_pr_feedback_tool(self.task, self.github_integration),
                create_code_structure_search_tool(codebase_integration),
                create_directory_tree_tool(codebase_integration),
                create_merge_pr_and_finalise_tool(self.task, self.task_service, self.github_integration),
            ]
        )
        return tools

    async def get_context_content(self) -> str:
        gc = GlobalContextService().get().content or None
        return build_task_pr_review_context(self.task, working_dir=self.working_dir, global_context=gc)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return ["Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch"]

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Include Claude Code's built-in system prompt."""
        return True
