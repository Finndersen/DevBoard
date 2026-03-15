from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_complete_task_with_local_merge_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_github_pr_tool,
    create_rebase_task_branch_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.sub_agent_tools import create_code_review_tool, create_task_codebase_investigation_tool
from devboard.agents.tools.task_tools import create_create_task_tool
from devboard.db.models import Task
from devboard.db.models.codebase import BranchHandling
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git_service import TaskGitService
from devboard.services.task_service import TaskService

IMPLEMENTATION_SYSTEM_PROMPT = """
You are a Task Implementation Assistant for DevBoard, helping developers implement planned tasks.

Your role is to:
- Execute the implementation plan by making code changes to the codebase
- Follow best practices and coding standards
- Create clean, tested, production-ready code

AVAILABLE CAPABILITIES:
1. CODEBASE EDITING: Use Edit/Write tools to modify code files in the codebase
2. DOCUMENT EDITING: Use dedicated or virtual tools to update task specification and implementation plan
3. INVESTIGATION: Read files, search code, run bash commands for testing/verification
   - Use `investigate_codebase` for questions requiring multi-step, multi-file investigation (e.g. understanding patterns, architecture, finding where related functionality lives). Do NOT use it to read a specific known file — use the `Read` tool directly instead.
4. BUILTIN TOOLS: Custom task management tools (e.g. complete_task_with_local_merge, create_pull_request, merge_pr_and_complete_task, rebase_task_branch) are available (possibly with the `mcp__builtin_tools__` prefix).

WORKFLOW:
- Review the implementation plan and understand requirements
- Ask for clarification when encountering ambiguity
- Create an internal to-do list of tasks to complete to track progress, based on implementation plan

Then execute in order:

1. IMPLEMENT CODE CHANGES
   - Work through the implementation plan step by step, launching sub-agents (via the `Agent` tool) to implement each step where possible
   - Update the internal to-do list as progress is made
   - If a `docs/` directory is present, investigate and update appropriate documentation sections to reflect new changes, adding or updating any missing or incorrect documentation

2. CODE REVIEW
   - For non-trivial changes, call `review_code_changes()` to perform a self-review before finalisation. You can optionally provide a `context` message to give the reviewer additional information — e.g. explaining why changes diverge from the specification or implementation plan, known limitations, or areas to focus on.
   - Thoughtfully consider the review feedback — use it in combination with your own judgement rather than blindly applying every suggestion
   - Address findings where you agree they are valid and worth doing

3. TEST & VERIFY
   - Run relevant tests to validate the changes
   - Confirm everything works as expected before finalising

IMPORTANT BEHAVIOUR GUIDELINES:
- When asked to commit, merge, or create a PR as part of a workflow action, the git status will already be provided in the prompt. Do NOT run git status, git log, or git diff to inspect the branch state — use the information already provided.
- If the user asks a question about the implementation, investigate and respond with a helpful answer and proposed changes, but DO NOT apply any changes until confirmed by the user.
- Use the Edit tool for existing files, Write tool for new files
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
- After completing changes, respond with a VERY BRIEF and concise summary of changes made.
- When creating commits, DO NOT add Claude Code attribution messages
"""


def build_task_implementation_context(task: Task) -> str:
    """Build context for task implementation agent."""
    return build_task_context(task)


class TaskImplementationAgentRole(AgentRole):
    """Role for task implementation in a codebase."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        task_git_service: TaskGitService,
        github_integration: GitHubIntegration,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
    ):
        self.task = task
        self.document_repository = document_repository
        self.agent_config_service = agent_config_service
        self.task_service = task_service
        self.task_git_service = task_git_service
        self.github_integration = github_integration
        self.conversation_repo = conversation_repo
        self.conversation_id = conversation_id

    def get_system_prompt(self) -> str:
        """Get the system prompt for task implementation role."""
        return IMPLEMENTATION_SYSTEM_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for task implementation role.

        Returns:
            List of document editing tools for specification and implementation plan.
            Note: Codebase editing tools (Edit/Write) are provided directly by the
            underlying agent (ClaudeCode), not through this role.
        """
        if not self.task.implementation_plan:
            raise ValueError(f"Task (ID: {self.task.id}) must have an implementation plan for implementation agent")

        codebase_integration = CodebaseIntegration(self.task.get_current_workspace_dir())

        tools = [
            # Tools for task specification document (uses default approval behavior)
            create_set_document_content_tool(self.task.specification, self.document_repository),
            create_document_edit_tool(self.task.specification, self.document_repository),
            # Tools for implementation plan document (never require approval)
            create_set_document_content_tool(
                self.task.implementation_plan, self.document_repository, requires_approval=False
            ),
            create_document_edit_tool(self.task.implementation_plan, self.document_repository, requires_approval=False),
            create_code_structure_search_tool(codebase_integration),
            create_directory_tree_tool(codebase_integration),
            create_task_codebase_investigation_tool(
                self.task,
                self.agent_config_service,
                conversation_repo=self.conversation_repo,
                parent_conversation_id=self.conversation_id,
            ),
            create_code_review_tool(
                self.task,
                self.agent_config_service,
                self.task_git_service,
                conversation_repo=self.conversation_repo,
                parent_conversation_id=self.conversation_id,
            ),
            # Rebase tool for updating branch with latest base branch changes
            create_rebase_task_branch_tool(self.task, self.task_git_service),
        ]

        # Add task completion tools based on codebase branch handling
        branch_handling = self.task.codebase.branch_handling
        if branch_handling == BranchHandling.GITHUB_PR.value:
            # GitHub PR workflow: create PR tool
            tools.append(create_github_pr_tool(self.task, self.github_integration, self.task_service))
        elif branch_handling == BranchHandling.LOCAL_MERGE.value:
            # Local merge workflow: complete_task_with_local_merge tool handles change summary + merge
            tools.append(create_complete_task_with_local_merge_tool(self.task, self.task_service))
        # For MANUAL branch handling, no completion tools are provided

        # Add create_task tool for creating related tasks
        tools.append(create_create_task_tool(self.task.project, self.task_service))

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task implementation role.

        Returns:
            Formatted context containing task details, specification, and implementation plan
        """
        return build_task_implementation_context(self.task)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        """List of allowed engine internal tools for this role."""
        return [
            "Read",
            "Grep",
            "Glob",
            "Edit",
            "Write",
            "Bash",
            "WebFetch",
            "WebSearch",
            "TaskCreate",
            "TaskGet",
            "TaskUpdate",
            "TaskList",
            "Agent",
            "Task",
            "Skill",
            "TodoWrite",
        ]

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Include Claude Code's built-in system prompt."""
        return True

    @property
    def include_claude_md(self) -> bool:
        """Load CLAUDE.md prompt guidance files."""
        return True
