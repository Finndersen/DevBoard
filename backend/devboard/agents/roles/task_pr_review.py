"""Role for managing tasks in PR_OPEN state."""

from pydantic_ai import Tool

from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_get_pr_feedback_tool,
    create_get_pr_status_tool,
    create_merge_pr_and_complete_task_tool,
)
from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.github import GitHubIntegration
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


def build_task_pr_review_context(task: Task, *, working_dir: str) -> str:
    """Build context for PR review agent."""
    return build_task_context(task, working_dir=working_dir, include_step_outcomes=True)


class TaskPRReviewAgentRole(AgentRole):
    """Role for managing tasks in PR_OPEN state."""

    def __init__(
        self,
        task: Task,
        task_service: TaskService,
        github_integration: GitHubIntegration,
        working_dir: str,
        conversation_repo: ConversationRepository | None = None,
    ):
        if not task.github_pr_number:
            raise ValueError("Task does not have a github_pr_number set")
        if not task.codebase.repository_url:
            raise ValueError("Task codebase does not have a repository_url set")

        self.task = task
        self._task_service = task_service
        self._github_integration = github_integration
        self._working_dir = working_dir
        self._conversation_repo = conversation_repo

    def get_system_prompt(self) -> str:
        """Get the system prompt for PR review role."""
        return PR_REVIEW_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for PR review role.

        Returns:
            List of PR reading tools, codebase exploration tools, task completion tool,
            and create_task tool.
            Note: Codebase editing tools (Edit/Write) are provided directly by the
            underlying agent (ClaudeCode), not through this role.
        """
        codebase_integration = CodebaseIntegration(self._working_dir)

        return [
            create_get_pr_status_tool(self.task, self._github_integration),
            create_get_pr_feedback_tool(self.task, self._github_integration),
            create_code_structure_search_tool(codebase_integration),
            create_directory_tree_tool(codebase_integration),
            create_merge_pr_and_complete_task_tool(self.task, self._task_service, self._github_integration),
            create_create_task_tool(self.task.project, self._task_service, self._conversation_repo),
        ]

    async def get_context_content(self) -> str:
        return build_task_pr_review_context(self.task, working_dir=self._working_dir)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role.

        Same as implementation role - needs full codebase editing capabilities.
        """
        return ["Read", "Edit", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "Task", "Agent", "Write"]

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Include Claude Code's built-in system prompt."""
        return True

    @property
    def include_claude_md(self) -> bool:
        """Load CLAUDE.md prompt guidance files."""
        return True
