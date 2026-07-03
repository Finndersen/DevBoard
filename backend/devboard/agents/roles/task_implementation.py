from pydantic_ai import Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.execution.registry import get_execution_manager
from devboard.agents.roles.context_helpers import build_task_context
from devboard.agents.roles.task_base import TaskAgentRoleBase
from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_document_edit_tool,
    create_github_pr_tool,
    create_merge_branch_and_finalise_tool,
    create_rebase_task_branch_tool,
    create_set_document_content_tool,
)
from devboard.agents.tools.implementation_plan_tools import (
    create_execute_implementation_step_tool,
    create_get_implementation_plan_overview_tool,
    create_read_implementation_step_details_tool,
)
from devboard.agents.tools.sub_agent_tools import create_code_review_tool
from devboard.db.models import Task
from devboard.db.models.codebase import BranchHandling
from devboard.db.repositories import ConversationRepository, DocumentRepository, LogEntryRepository
from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.global_context_service import GlobalContextService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_implementation_plan import TaskImplementationPlanService
from devboard.services.task_service import TaskService

_PROMPT_BASE = """
You are a Task Implementation Assistant for DevBoard, helping a developer implement the current task.

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
5. SUB-AGENTS (Agent tool): Launch sub-agents for broad implementation steps that span multiple files.
   Each sub-agent should handle an entire implementation step, not a sub-step.
   Do NOT use sub-agents for small-scoped or single-file changes — make those edits directly.

WORKFLOW:
- Activate relevant skills: review available skills in your context and activate any relevant to this work (software-development, coding conventions, testing strategy, etc.) using the `Skill` tool before executing any steps.
- Review the implementation plan and understand requirements
- Ask for clarification when encountering ambiguity

Then execute in order:

{implement_section}

2. CODE REVIEW (if a `code_review` step is in the plan)
   - After executing the `code_review` step, read its findings from the step outcome
   - Address all raised issues - Use your own judgement on each suggestion to either state why is invalid/not necessary, or make changes to resolve it
   - Make any required changes either directly or via sub-agent if substantial

3. TEST & VERIFY
   - Run relevant tests to validate the changes
   - Confirm everything works as expected before finalising

IMPORTANT BEHAVIOUR GUIDELINES:
{behaviour_guidelines}
- When asked to commit, merge, or create a PR as part of a workflow action, the git status will already be provided in the prompt. Do NOT run git status, git log, or git diff to inspect the branch state — use the information already provided.
- If the user asks a question about the implementation, investigate and respond with a helpful answer and proposed changes, but DO NOT apply any changes until confirmed by the user.
- Use the Edit tool for existing files, Write tool for new files
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
- After completing changes, respond with a VERY BRIEF and concise summary of changes made.
- When creating commits, DO NOT add Claude Code attribution messages
- When committing changes, stage and commit in a single command: `git add -A && git commit -m "message"`. Using `git add -A` is safe in task worktrees since build artifacts are gitignored. Do NOT list individual files separately with `git add`.
"""

_STRUCTURED_PLAN_IMPLEMENT_SECTION = """\
1. IMPLEMENT CODE CHANGES
   - Use the `execute_implementation_step` tool to execute each step — do NOT implement steps directly
     with Edit/Write tools. This ensures step statuses are tracked in the plan.
   - Do NOT use `read_implementation_step_details` before executing steps — each step execution sub-agent
     is automatically provided the full step details and all required context
   - Consult the EXECUTION GRAPH in the task context to identify which steps can run in parallel
   - Execute independent steps concurrently by calling `execute_implementation_step` for each in a
     single message (multiple tool calls); wait for dependencies to complete before proceeding
   - If a step fails or gets stuck, you can retry it by calling `execute_implementation_step` again
   - If a `docs/` directory is present, investigate and update appropriate documentation sections\
"""

_STRUCTURED_PLAN_BEHAVIOUR_GUIDELINES = """\
- ALWAYS use `execute_implementation_step` for every plan step — never bypass it by editing directly\
"""


def _build_system_prompt() -> str:
    return _PROMPT_BASE.format(
        implement_section=_STRUCTURED_PLAN_IMPLEMENT_SECTION,
        behaviour_guidelines=_STRUCTURED_PLAN_BEHAVIOUR_GUIDELINES,
    )


class TaskImplementationAgentRole(TaskAgentRoleBase):
    """Role for task implementation in a codebase."""

    def __init__(
        self,
        task: Task,
        document_repository: DocumentRepository,
        agent_config_service: AgentConfigService,
        task_service: TaskService,
        github_integration: GitHubIntegration,
        conversation_repo: ConversationRepository,
        conversation_id: int | None,
        plan_service: TaskImplementationPlanService,
        working_dir: str,
    ):
        super().__init__(
            task=task,
            task_service=task_service,
            conversation_repo=conversation_repo,
            conversation_id=conversation_id,
            agent_config_service=agent_config_service,
            working_dir=working_dir,
        )
        self.document_repository = document_repository
        self.github_integration = github_integration
        self.plan_service = plan_service

    def get_system_prompt(self) -> str:
        """Get the system prompt for task implementation role."""
        return _build_system_prompt()

    def get_tools(self) -> list[Tool]:
        """Get tools for task implementation role."""
        if self.task.implementation_plan_structured is None:
            raise ValueError(
                f"Task (ID: {self.task.id}) must have a structured implementation plan. Tasks with legacy document-based plans must be migrated to the structured format."
            )

        codebase_integration = CodebaseIntegration(self.working_dir)

        log_entry_repo = LogEntryRepository(self.document_repository.db)
        event_emitter = SystemEventEmitter(log_entry_repo)

        tools = super().get_tools()

        tools.extend(
            [
                # Tools for task specification document (uses default approval behavior)
                create_set_document_content_tool(
                    self.task.specification,
                    self.document_repository,
                    document_parent=self.task,
                    system_event_emitter=event_emitter,
                ),
                create_document_edit_tool(
                    self.task.specification,
                    self.document_repository,
                    document_parent=self.task,
                    system_event_emitter=event_emitter,
                ),
            ]
        )

        # Structured implementation plan tools
        tools.extend(
            [
                create_execute_implementation_step_tool(
                    self.task,
                    self.plan_service,
                    self.agent_config_service,
                    self.conversation_repo,
                    self.conversation_id,
                    self.working_dir,
                    execution_manager=get_execution_manager(),
                ),
                create_read_implementation_step_details_tool(self.task, self.plan_service),
                create_get_implementation_plan_overview_tool(self.task),
            ]
        )

        tools.extend(
            [
                create_code_structure_search_tool(codebase_integration),
                create_directory_tree_tool(codebase_integration),
                create_code_review_tool(
                    self.task,
                    self.agent_config_service,
                    conversation_repo=self.conversation_repo,
                    parent_conversation_id=self.conversation_id,
                    working_dir=self.working_dir,
                    execution_manager=get_execution_manager(),
                ),
                create_rebase_task_branch_tool(self.task),
            ]
        )

        # Add task completion tools based on codebase branch handling
        branch_handling = self.task.codebase.branch_handling
        if branch_handling == BranchHandling.GITHUB_PR.value:
            # GitHub PR workflow: create PR tool
            tools.append(create_github_pr_tool(self.task, self.github_integration, self.task_service))
        elif branch_handling == BranchHandling.DIRECT_MERGE.value:
            # Direct merge workflow: merge_branch_and_finalise tool handles change summary + merge
            tools.append(create_merge_branch_and_finalise_tool(self.task, self.task_service))
        # For MANUAL branch handling, no completion tools are provided

        return tools

    async def get_context_content(self) -> str:
        """Get context content for task implementation role.

        Returns:
            Formatted context containing task details, specification, and implementation plan.
            Step statuses are excluded from the plan — use get_implementation_plan_overview tool
            to check current step statuses during execution.
        """
        gc = GlobalContextService().get().content or None
        return build_task_context(
            self.task,
            working_dir=self.working_dir,
            global_context=gc,
            include_project_specification=False,
            include_step_status=False,
        )

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
            "ToolSearch",
        ]

    @property
    def include_builtin_system_prompt(self) -> bool:
        """Include Claude Code's built-in system prompt."""
        return True
